"""Bounded read-only XLSX wagon import; no workbook formulas are executed."""
import re
import unicodedata
from decimal import Decimal, ROUND_CEILING, InvalidOperation
from io import BytesIO
from zipfile import ZipFile
from pydantic import BaseModel, Field
from openpyxl import load_workbook

MAX_UPLOAD = 5 * 1024 * 1024

class ImportError(ValueError):
    pass

class WagonRow(BaseModel):
    number: str = Field(pattern=r'^[0-9]{12}$')
    length: Decimal = Field(gt=0, le=100, decimal_places=3, allow_inf_nan=False)
    weight: Decimal = Field(ge=0, le=1000, decimal_places=3, allow_inf_nan=False)
    g: Decimal | None = Field(default=None, ge=0, le=1000, decimal_places=3, allow_inf_nan=False)
    p: Decimal | None = Field(default=None, ge=0, le=1000, decimal_places=3, allow_inf_nan=False)

class WagonImport(BaseModel):
    rows: list[WagonRow] = Field(min_length=1, max_length=50)
    length_total: Decimal | None = Field(default=None, gt=0, le=720, decimal_places=3, allow_inf_nan=False)
    weight_total: Decimal | None = Field(default=None, gt=0, le=5000, decimal_places=3, allow_inf_nan=False)
    g_total: Decimal | None = Field(default=None, ge=0, le=5000, decimal_places=3, allow_inf_nan=False)
    p_total: Decimal | None = Field(default=None, ge=0, le=5000, decimal_places=3, allow_inf_nan=False)
    sheet: str = Field(max_length=100)
    first_row: int = Field(ge=1, le=2000)
    last_row: int = Field(ge=1, le=2000)
    total_row: int | None = Field(default=None, ge=1, le=2000)

    def values(self, mode):
        if mode not in ('G', 'P', 'G+P'):
            raise ImportError('mode')
        raw_length = sum((row.length for row in self.rows), Decimal(0))
        if mode == 'G+P':
            g_rows, p_rows = self.rows[:5], self.rows[5:]
            if any(row.g is None for row in g_rows) or any(row.p is None for row in p_rows):
                raise ImportError('missing_brake')
            g = sum((row.g for row in g_rows), Decimal(0))
            p = sum((row.p for row in p_rows), Decimal(0))
            brake = g * Decimal('.75') + p * (Decimal('.95') if raw_length > 500 else Decimal(1))
        else:
            field = mode.lower()
            if any(getattr(row, field) is None for row in self.rows):
                raise ImportError('missing_brake')
            brake = getattr(self, field + '_total')
            if brake is None:
                brake = sum((getattr(row, field) for row in self.rows), Decimal(0))
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
        result = Decimal(str(value).strip().replace('\u00a0', '').replace(' ', '').replace(',', '.'))
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
                result.append((position, WagonRow(number=digits, **{key:number(cell(row,cols[key]), key in ('g','p')) for key in ('length','weight','g','p')})))
                source_rows.append(i+1)
            if not result or len(result) > 50: raise ImportError('range')
            result.sort(key=lambda item:item[0])
            if [p for p,_ in result] != list(range(1,len(result)+1)) or len({r.number for _,r in result}) != len(result): raise ImportError('format')
            totals = {key+'_total':number(cell(total,cols[key]),True) if total is not None else None for key in ('length','weight','g','p')}
            imported = WagonImport(rows=[row for _,row in result],sheet=title,first_row=min(source_rows),last_row=max(source_rows),total_row=total_index,**totals)
            return dict(**stations,first_vehicle=imported.rows[0].number,last_vehicle=imported.rows[-1].number,wagon_import=imported)
        finally:
            workbook.close()
    except ImportError:
        raise
    except Exception as error:
        raise ImportError('format') from error
