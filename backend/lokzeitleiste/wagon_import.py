"""Bounded read-only XLSX wagon import; no workbook formulas are executed."""
import re
import unicodedata
from typing import Literal
from decimal import Decimal, ROUND_CEILING, InvalidOperation
from io import BytesIO
from zipfile import ZipFile
from pydantic import BaseModel, Field
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

MAX_UPLOAD = 5 * 1024 * 1024

class ImportError(ValueError):
    pass

class WagonRow(BaseModel):
    number: str = Field(pattern=r'^[0-9]{12}$')
    length: Decimal = Field(gt=0, le=100, decimal_places=3, allow_inf_nan=False)
    weight: Decimal = Field(ge=0, le=1000, decimal_places=3, allow_inf_nan=False)
    cargo: Decimal | None = Field(default=None, ge=0, le=1000, decimal_places=3, allow_inf_nan=False)
    g: Decimal | None = Field(default=None, ge=0, le=1000, decimal_places=3, allow_inf_nan=False)
    p: Decimal | None = Field(default=None, ge=0, le=1000, decimal_places=3, allow_inf_nan=False)

class WagonImport(BaseModel):
    brake_policy: Literal['standard','all_g','mixed','unchanged'] = 'standard'
    rows: list[WagonRow] = Field(min_length=1, max_length=50)
    length_total: Decimal | None = Field(default=None, gt=0, le=720, decimal_places=3, allow_inf_nan=False)
    weight_total: Decimal | None = Field(default=None, gt=0, le=5000, decimal_places=3, allow_inf_nan=False)
    g_total: Decimal | None = Field(default=None, ge=0, le=5000, decimal_places=3, allow_inf_nan=False)
    p_total: Decimal | None = Field(default=None, ge=0, le=5000, decimal_places=3, allow_inf_nan=False)
    cargo_total: Decimal | None = Field(default=None, ge=0, le=5000, decimal_places=3, allow_inf_nan=False)
    reported_length_total: Decimal | None = Field(default=None, ge=0, max_digits=15, decimal_places=3, allow_inf_nan=False)
    reported_weight_total: Decimal | None = Field(default=None, ge=0, max_digits=15, decimal_places=3, allow_inf_nan=False)
    reported_cargo_total: Decimal | None = Field(default=None, ge=0, max_digits=15, decimal_places=3, allow_inf_nan=False)
    columns: dict[str, str] = Field(default_factory=dict)
    reported_g_total: Decimal | None = Field(default=None, ge=0, max_digits=15, decimal_places=3, allow_inf_nan=False)
    reported_p_total: Decimal | None = Field(default=None, ge=0, max_digits=15, decimal_places=3, allow_inf_nan=False)
    sheet: str = Field(max_length=100)
    first_row: int = Field(ge=1, le=2000)
    last_row: int = Field(ge=1, le=2000)
    total_row: int | None = Field(default=None, ge=1, le=2000)

    def detected_mode(self):
        g_only=lambda row:row.g is not None and row.p in (None,0) and (row.g>0 or row.p is None)
        p_only=lambda row:row.p is not None and row.g in (None,0) and (row.p>0 or row.g is None)
        if all(g_only(row) for row in self.rows):return 'G'
        if all(p_only(row) for row in self.rows):return 'P'
        if len(self.rows)>5 and all(g_only(row) for row in self.rows[:5]) and all(p_only(row) for row in self.rows[5:]):return 'G+P'
        return None

    def summary_differences(self):
        differences=[]
        for field in ('length','cargo','weight','p','g'):
            reported=getattr(self,'reported_'+field+'_total');computed=getattr(self,field+'_total')
            if reported is not None and (computed is None or reported.to_integral_value(rounding=ROUND_CEILING)!=computed.to_integral_value(rounding=ROUND_CEILING)):
                differences.append(dict(column=field.upper() if field in ('g','p') else self.columns.get(field,field),unit='m' if field=='length' else 't',reported=reported,computed=computed))
        return differences

    def active_policy(self, mode):
        expected='G' if self.brake_policy=='all_g' else 'G+P'
        return self.brake_policy if mode==expected else 'standard'

    def row_brake(self, row, position, mode):
        policy=self.active_policy(mode)
        if policy=='all_g':
            value=row.g if row.g is not None and (row.g!=0 or row.p is None) else row.p
            position_mode='G'
        elif policy=='unchanged':
            if row.g is not None and row.p in (None,0):position_mode,value='G',row.g
            elif row.p is not None and row.g in (None,0):position_mode,value='P',row.p
            else:raise ImportError('format')
        else:
            position_mode=('G' if position<5 else 'P') if mode=='G+P' else mode
            value=getattr(row,position_mode.lower())
        if value is None:raise ImportError('missing_brake')
        return position_mode,value

    def brake_components(self, mode):
        if mode not in ('G','P','G+P'):raise ImportError('mode')
        g=p=Decimal(0)
        for index,row in enumerate(self.rows):
            position,value=self.row_brake(row,index,mode)
            if position=='G':g+=value
            else:p+=value
        policy=self.active_policy(mode)
        g_counted=g*Decimal('.75') if mode=='G+P' and policy!='unchanged' else g
        long_train=sum((row.length for row in self.rows),Decimal(0))>500
        p_counted=p*Decimal('.95') if mode=='G+P' and policy!='unchanged' and long_train else p
        return dict(g=g,g_counted=g_counted,p=p,p_counted=p_counted,total=g_counted+p_counted)

    def column_totals(self, mode=None):
        totals={field:getattr(self,field+'_total') for field in ('length','cargo','weight','p','g')}
        if mode and self.active_policy(mode)=='all_g':
            totals.update(g=self.brake_components(mode)['g'],p=Decimal(0))
        return [dict(column=self.columns[field],unit='m' if field=='length' else 't',total=totals[field])
                for field in ('length','cargo','weight','p','g') if field in self.columns]

    def values(self, mode):
        components=self.brake_components(mode)
        raw_length=sum((row.length for row in self.rows),Decimal(0))
        brake=components['total']
        if mode in ('G','P') and self.active_policy(mode)=='standard':
            supplied=getattr(self,mode.lower()+'_total')
            if supplied is not None:
                if supplied.to_integral_value(rounding=ROUND_CEILING)!=brake.to_integral_value(rounding=ROUND_CEILING):
                    raise ImportError('format')
                brake=supplied
        ceil = lambda v: int(v.to_integral_value(rounding=ROUND_CEILING))
        for supplied, measured in [(self.length_total, raw_length), (self.weight_total, sum((r.weight for r in self.rows), Decimal(0)))]:
            if supplied is not None and ceil(supplied) != ceil(measured): raise ImportError('format')
        values = dict(count=len(self.rows), length=ceil(self.length_total if self.length_total is not None else raw_length),
                      weight=ceil(self.weight_total if self.weight_total is not None else sum((r.weight for r in self.rows), Decimal(0))), brake=ceil(brake))
        if not (10 <= values['length'] <= 720 and 100 <= values['weight'] <= 5000 and 100 <= values['brake'] <= 5000):
            raise ImportError('range')
        return values


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or '').lower()) if not unicodedata.combining(c))


def number(value, optional=False):
    if value is None or str(value).strip() == '':
        if optional: return None
        raise ImportError('format')
    try:
        text=re.sub(r'\s','',str(value))
        if ',' in text and '.' in text:
            grouping='.' if text.rfind(',')>text.rfind('.') else ','
            decimal=',' if grouping=='.' else '.'
            if not re.fullmatch(r'[+]?\d{1,3}(?:'+re.escape(grouping)+r'\d{3})+'+re.escape(decimal)+r'\d+',text):raise ImportError('format')
            text=text.replace(grouping,'')
        result = Decimal(text.replace(',', '.'))
    except InvalidOperation:
        raise ImportError('format')
    if not result.is_finite() or result < 0: raise ImportError('format')
    return result


def parse(content):
    if len(content) > MAX_UPLOAD: raise ImportError('file')
    try:
        with ZipFile(BytesIO(content)) as archive:
            items = archive.infolist()
            if len(items) > 1000 or sum(x.file_size for x in items) > 20 * 1024 * 1024 or any('vbaproject' in x.filename.lower() for x in items):
                raise ImportError('file')
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True, keep_links=False)
        try:
            candidates = []
            for sheet in workbook.worksheets:
                if sheet.max_row > 2000 or sheet.max_column > 64: raise ImportError('file')
                rows = list(sheet.iter_rows(values_only=True))
                for idx, row in enumerate(rows[:50]):
                    labels = [normalized(v) for v in row]
                    def locate(predicate):
                        found = [i for i, text in enumerate(labels) if predicate(text)]
                        return found[0] if len(found) == 1 else None
                    columns = dict(pos=locate(lambda s:s.strip() == 'pos.'),
                                   number=locate(lambda s:'fahrzeugnummer' in s or 'nr pojazdu' in s),
                                   length=locate(lambda s:'lup' in s or 'długosc ze zderzakami' in s),
                                   weight=locate(lambda s:'gesamt' in s and 'gewicht' in s or 'masa całkowita' in s))
                    if all(v is not None for v in columns.values()): candidates.append((sheet.title, rows, idx, columns))
            if len(candidates) != 1: raise ImportError('format')
            title, rows, header, cols = candidates[0]
            cargo_columns=[i for i,v in enumerate(rows[header]) if re.search(r'ladungs\s*-?\s*gewicht|masa ładunku',normalized(v))]
            if len(cargo_columns)>1:raise ImportError('format')
            if cargo_columns:cols['cargo']=cargo_columns[0]
            if header + 1 >= len(rows): raise ImportError('format')
            sub = [str(v or '').strip().upper() for v in rows[header+1]]
            if sub.count('G') != 1 or sub.count('P') != 1: raise ImportError('format')
            cols.update(g=sub.index('G'), p=sub.index('P'))
            cell = lambda row, col: row[col] if col < len(row) else None
            stations = {}
            for i, row in enumerate(rows[:header]):
                for c, value in enumerate(row):
                    label = normalized(value)
                    field = 'station_from' if 'gultig ab' in label else 'station_to' if 'gultig bis' in label else None
                    if field and i + 1 < len(rows): stations[field] = str(cell(rows[i+1], c) or '').strip()
            if not all(stations.get(k) for k in ('station_from', 'station_to')): raise ImportError('format')
            # Explicitly agreed first-word destination, while preserving full origin.
            stations['station_to'] = stations['station_to'].split()[0]
            result = []; total = None; total_index = None; source_rows = []
            for i in range(header + 2, len(rows)):
                row = rows[i]
                if any(normalized(v).strip().startswith(('summe', 'suma', 'total')) for v in row if v is not None):
                    total, total_index = row, i + 1; break
                pos = cell(row, cols['pos']); vehicle = cell(row, cols['number'])
                if pos is None and vehicle is None: continue
                if not str(pos or '').strip().isdigit(): raise ImportError('format')
                position = int(pos)
                digits = re.sub(r'[\s-]', '', str(vehicle or ''))
                if not re.fullmatch(r'[0-9]{12}', digits): raise ImportError('format')
                result.append((position, WagonRow(number=digits, **{key:number(cell(row,cols[key]), key in ('g','p','cargo')) for key in ('length','weight','g','p','cargo') if key in cols})))
                source_rows.append(i+1)
            if not result or len(result) > 50: raise ImportError('range')
            result.sort(key=lambda item:item[0])
            if [p for p,_ in result] != list(range(1,len(result)+1)) or len({r.number for _,r in result}) != len(result): raise ImportError('format')
            totals = {key+'_total':number(cell(total,cols[key]),True) if total is not None else None for key in ('length','weight','g','p','cargo') if key in cols}
            # Excel SUM can omit numbers stored as text. Use all parsed individual
            # numeric values; retain the source summaries for explicit preview warnings.
            for field in ('length','cargo','weight','p','g'):
                if field not in cols:continue
                totals['reported_'+field+'_total']=totals[field+'_total']
                present=[getattr(row,field) for _,row in result if getattr(row,field) is not None]
                totals[field+'_total']=sum(present,Decimal(0)) if present or field=='cargo' else None
            imported = WagonImport(rows=[row for _,row in result],columns={field:get_column_letter(cols[field]+1) for field in ('length','cargo','weight','p','g') if field in cols},sheet=title,first_row=min(source_rows),last_row=max(source_rows),total_row=total_index,**totals)
            return dict(**stations,first_vehicle=imported.rows[0].number,last_vehicle=imported.rows[-1].number,wagon_import=imported)
        finally:
            workbook.close()
    except ImportError:
        raise
    except Exception as error:
        raise ImportError('format') from error
