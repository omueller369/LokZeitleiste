"""XLSX-Vertrag: Blatt Plan, Datum/Art/Notiz/Personalnummer; keine Formeln."""
from ..localization import source as _text_source
from datetime import date, datetime
from io import BytesIO
from zipfile import ZipFile

from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Font, PatternFill, GradientFill
from openpyxl.worksheet.datavalidation import DataValidation
from .schemas import DayInput
from .duties import SHIFTS
from ..i18n import translate, request_language

MAX_FILE = 2 * 1024 * 1024
MAX_UNPACKED = 20 * 1024 * 1024
from .palette import COLORS,base_key,background_key


def parse_excel(content: bytes, *, year: int, personnel_number: str) -> list[DayInput]:
    if len(content) > MAX_FILE:
        raise ValueError(_text_source('server_planning_excel.text_5498de0df917'))
    try:
        with ZipFile(BytesIO(content)) as archive:
            if len(archive.infolist()) > 500 or sum(x.file_size for x in archive.infolist()) > MAX_UNPACKED:
                raise ValueError(_text_source('server_planning_excel.text_f91e9c27de96'))
            if any(x.filename.endswith("vbaProject.bin") for x in archive.infolist()):
                raise ValueError(_text_source('server_planning_excel.text_4484bb7de2f8'))
        book = load_workbook(BytesIO(content), read_only=True, data_only=False, keep_links=False)
    except Exception as exc:
        raise ValueError(_text_source('server_planning_excel.text_eb69152ce951')) from exc
    try:
        if _text_source('server_planning_excel.text_fa8ed0bdabdd') not in book.sheetnames:
            raise ValueError(_text_source('server_planning_excel.text_7cc53f830592'))
        sheet = book[_text_source('server_planning_excel.text_fa8ed0bdabdd')]
        if (sheet.max_row or 0) > 367 or (sheet.max_column or 0) > 5:
            raise ValueError(_text_source('server_planning_excel.text_d930cd0454d1'))
        sheet.reset_dimensions()
        rows = sheet.iter_rows(max_col=6, max_row=368)
        header_row = next(rows)
        if header_row[5].value not in (None, ""):
            raise ValueError(_text_source('server_planning_excel.text_6deb5732c2c6'))
        headers = [str(c.value or "").strip() for c in header_row[:4]]
        if headers[:2] != [_text_source('server_planning_excel.text_9135882d323c'), _text_source('server_planning_excel.text_75df3579c730')] or headers[2] not in ("", _text_source('server_planning_excel.text_74b487d9d223')) or headers[3] not in ("", _text_source('server_planning_excel.text_2626695f9042')):
            raise ValueError(_text_source('server_planning_excel.text_d4d2fca45904'))
        if str(header_row[4].value or "").strip() not in ("",_text_source('server_planning_excel.text_4da394b87b08')):raise ValueError(_text_source('server_planning_excel.text_7fc7ad839563'))
        result, seen = [], set()
        for number, row in enumerate(rows, start=2):
            values = [c.value for c in row]
            if all(v in (None, "") for v in values):
                continue
            if number > 367 or values[5] not in (None, ""):
                raise ValueError(_text_source('server_planning_excel.text_d930cd0454d1'))
            shift=str(values[4] or "").strip() or None
            if shift not in (None,*SHIFTS):raise ValueError(_text_source('server_planning_excel.text_8303e6216f20'))
            values = values[:4]
            if any(c.data_type == "f" for c in row):
                raise ValueError(f"{_text_source('server_planning_excel.text_6ae1b1603eb6')}{number}{_text_source('server_planning_excel.text_71b8f93e7684')}")
            raw_date, kind, note, person = values
            if isinstance(raw_date, datetime):
                day = raw_date.date()
            elif isinstance(raw_date, date):
                day = raw_date
            elif isinstance(raw_date, str):
                try:
                    day = date.fromisoformat(raw_date.strip()) if "-" in raw_date else datetime.strptime(raw_date.strip(), "%d.%m.%Y").date()
                except ValueError as exc:
                    raise ValueError(f"{_text_source('server_planning_excel.text_6ae1b1603eb6')}{number}{_text_source('server_planning_excel.text_fa51668aa40a')}") from exc
            else:
                raise ValueError(f"{_text_source('server_planning_excel.text_6ae1b1603eb6')}{number}{_text_source('server_planning_excel.text_24f4d6fbd0a4')}")
            if day.year != year or day in seen:
                raise ValueError(f"{_text_source('server_planning_excel.text_6ae1b1603eb6')}{number}{_text_source('server_planning_excel.text_7e45c705528c')}")
            if person is not None and str(person).strip() != personnel_number:
                raise ValueError(f"{_text_source('server_planning_excel.text_6ae1b1603eb6')}{number}{_text_source('server_planning_excel.text_52e0708885cf')}")
            try:
                item = DayInput(date=day, kind=str(kind or "").strip(), note=str(note or ""),shift=shift)
            except ValueError as exc:
                raise ValueError(f"{_text_source('server_planning_excel.text_6ae1b1603eb6')}{number}{_text_source('server_planning_excel.text_54f7f6ee4f68')}") from exc
            result.append(item)
            seen.add(day)
        if not result:
            raise ValueError(_text_source('server_planning_excel.text_a9ce64fa7c7d'))
        return result
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(_text_source('server_planning_excel.text_302a6f9ea296')) from exc
    finally:
        book.close()


def template(year_plan: dict, personnel_number: str) -> bytes:
    book = Workbook()
    view = book.create_sheet(translate(_text_source('server_planning_excel.text_871dcbbcca6b')))
    view.sheet_view.rightToLeft = False
    view.append([translate(v) for v in (_text_source('server_planning_excel.text_9135882d323c'),_text_source('server_planning_excel.text_aacbdebb08dc'),_text_source('server_planning_excel.text_d7eadc594242'),_text_source('server_planning_excel.text_ecda07db6e0b'),_text_source('server_planning_excel.text_74b487d9d223'))])
    for month in year_plan['months']:
        for item in month['days']:
            view.append([date.fromisoformat(item['date']),translate(item['kind']),item['target_minutes']/60,
                         translate(item['holiday_name']) if item.get('is_holiday') else '',item['note'],translate(item.get('shift_label',''))])
            for cell in view[view.max_row]:
                if isinstance(cell.value,str):cell.data_type='s'
    for column in 'ABCDEF':view.column_dimensions[column].width=25
    view.freeze_panes='A2'
    sheet = book.active
    sheet.title = _text_source('server_planning_excel.text_fa8ed0bdabdd')
    sheet.append([_text_source('server_planning_excel.text_9135882d323c'), _text_source('server_planning_excel.text_75df3579c730'), _text_source('server_planning_excel.text_74b487d9d223'), _text_source('server_planning_excel.text_2626695f9042'),_text_source('server_planning_excel.text_4da394b87b08')])
    for month in year_plan["months"]:
        for item in month["days"]:
            sheet.append([date.fromisoformat(item["date"]), item["kind"], item["note"], personnel_number,item.get("shift","standard")])
            row = sheet.max_row
            if item.get("is_holiday"):
                sheet.cell(row,1).comment=Comment(_text_source('server_planning_excel.text_bfd80d4f15c6')+item["holiday_name"]+_text_source('server_planning_excel.text_8fe71687aba0'),"LokZeitleiste")
            sheet.cell(row, 1).number_format = "DD.MM.YYYY"
            sheet.cell(row, 4).number_format = "@"
            # Nutzereingaben bleiben Text, auch wenn sie mit '=' beginnen.
            for column in (2, 3, 4,5):
                sheet.cell(row, column).data_type = "s"
            for cell in sheet[row]:
                if item.get('is_holiday') and item['kind']!=_text_source('server_planning_excel.text_52e37a639da5'):
                    from openpyxl.styles.fills import Stop
                    cell.fill=GradientFill(type='linear',degree=45,stop=[Stop(COLORS[_text_source('server_planning_excel.text_ecda07db6e0b')],0),Stop(COLORS[_text_source('server_planning_excel.text_ecda07db6e0b')],0.499),Stop(COLORS[base_key(item)],0.5),Stop(COLORS[base_key(item)],1)])
                else:cell.fill = PatternFill("solid", fgColor=COLORS[background_key(item)])
    for cell in sheet[1]:
        cell.fill = PatternFill("solid", fgColor="173E55")
        cell.font = Font(color="FFFFFF", bold=True)
    for col, width in {"A": 16, "B": 18, "C": 45, "D": 22,"E":20}.items():
        sheet.column_dimensions[col].width = width
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    validation = DataValidation(type="list", formula1='"Arbeitstag,Urlaub,Ruhetag,Ungeplant"', allow_blank=False)
    validation.errorTitle = _text_source('server_planning_excel.text_c2d43e2c288c')
    validation.error = _text_source('server_planning_excel.text_fe355fd384a9')
    validation.showErrorMessage = True
    sheet.add_data_validation(validation)
    validation.add(f"B2:B{sheet.max_row}")
    shift_validation=DataValidation(type="list",formula1='"standard,border_day,border_night"',allow_blank=True)
    sheet.add_data_validation(shift_validation);shift_validation.add(f"E2:E{sheet.max_row}")
    info=book.create_sheet(_text_source('server_planning_excel.text_98deca758e26'))
    info.append([_text_source('server_planning_excel.text_9135882d323c'),_text_source('server_planning_excel.text_3726e734d71d'),_text_source('server_planning_excel.text_167c97688e21')])
    for month in year_plan['months']:
        for item in month['days']:
            if item.get('is_holiday'):
                info.append([date.fromisoformat(item['date']),item['holiday_name'],0])
                info.cell(info.max_row,1).number_format='DD.MM.YYYY'
                info.cell(info.max_row,2).data_type='s'
                for cell in info[info.max_row]:cell.fill=PatternFill('solid',fgColor=COLORS[_text_source('server_planning_excel.text_ecda07db6e0b')])
    info.column_dimensions['A'].width=16;info.column_dimensions['B'].width=65;info.column_dimensions['C'].width=16
    info.freeze_panes='A2'
    buffer = BytesIO()
    book.save(buffer)
    return buffer.getvalue()
