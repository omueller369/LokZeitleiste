from ..localization import source as _text_source
from datetime import datetime
from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .daily import DayRow, grouped_days, totals
from ..pdf_locale import register_fonts, LocalizedParagraph as Paragraph
from ..i18n import request_language
register_fonts("ReceiptSans")


INK = colors.HexColor("#183247")
PALE = colors.HexColor("#edf3f5")


def _clock(minutes: int) -> str:
    return f"{minutes // 60}:{minutes % 60:02d}"


def render_receipt_pdf(*, first_name: str, last_name: str, personnel_number: str,
                       federal_state: str, year: int, month: int,
                       received_at: datetime, rows: list[DayRow], lang: str | None = None, monthly: bool = False) -> bytes:
    token=request_language.set(lang or request_language.get())
    try:
        return _render_receipt_pdf(first_name=first_name,last_name=last_name,personnel_number=personnel_number,federal_state=federal_state,year=year,month=month,received_at=received_at,rows=rows,monthly=monthly)
    finally:
        request_language.reset(token)


def _render_receipt_pdf(*, first_name, last_name, personnel_number, federal_state, year, month, received_at, rows, monthly=False):
    stream = BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=landscape(A4),
                            leftMargin=14 * mm, rightMargin=14 * mm,
                            topMargin=13 * mm, bottomMargin=13 * mm,
                            title=_text_source('server_reports_pdf.text_6953ff7703d4') if monthly else _text_source('server_reports_pdf.text_bb3b918a4a6a'))
    heading = ParagraphStyle("heading", fontName="ReceiptSans-Bold", fontSize=12, leading=15, textColor=INK)
    body = ParagraphStyle("body", fontName="ReceiptSans", fontSize=8.2, leading=11, textColor=INK)
    small = ParagraphStyle("small", parent=body, fontSize=7.4, leading=9.5)
    center = ParagraphStyle("center", parent=body, alignment=TA_CENTER)
    def p(value, style=body):
        return Paragraph(escape(str(value)), style)
    story = []
    metadata = Table([
        [p(_text_source('server_reports_pdf.text_6953ff7703d4') if monthly else _text_source('server_reports_pdf.text_10e132e72625'), heading), p(f"{_text_source('server_reports_pdf.text_7c00e2248e91')}{month:02d}/{year}")],
        [p(f"Tf: {first_name} {last_name}"), p(f"{_text_source('server_reports_pdf.text_068e16029c9b')}{personnel_number}")],
        [p(f"{('Erstellt' if monthly else 'Eingang')}: {received_at:%d.%m.%Y %H:%M}{_text_source('server_reports_pdf.text_4e2866d1f2b9')}"), p(f"{_text_source('server_reports_pdf.text_9051770073ea')}{federal_state}")],
    ], colWidths=[135 * mm, 134 * mm])
    metadata.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PALE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd9df")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dce5e9")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([metadata, Spacer(1, 8 * mm)])
    headers = [_text_source('server_reports_pdf.text_9135882d323c'), _text_source('server_reports_pdf.text_75df3579c730'), _text_source('server_reports_pdf.text_0d95fd6a769f'), _text_source('server_reports_pdf.text_2ddcd606c872'), _text_source('server_reports_pdf.text_858e4ba7a29f'), _text_source('server_reports_pdf.text_3f0828ad8bfa'), _text_source('server_reports_pdf.text_7c4d852aa578'), _text_source('server_reports_pdf.text_a5984592501e'), _text_source('server_reports_pdf.text_ecda07db6e0b'), _text_source('server_reports_pdf.text_0af3584be783')]
    widths = [23, 53, 20, 20, 20, 23, 27, 26, 26, 26]
    widths = [x * mm for x in widths]
    table_data = [[p(h, ParagraphStyle("header-" + h, parent=center, fontName="ReceiptSans-Bold",
                                      textColor=colors.white, fontSize=7.4)) for h in headers]]
    span_rows = []
    for day, day_items in grouped_days(rows):
        holiday_names = ", ".join(sorted({row.holiday_name for row in day_items if row.holiday_name}))
        for row in day_items:
            table_data.append([
                p(day.strftime("%d.%m.%Y"), small), p(row.kind, small),
                p(row.start.strftime("%H:%M"), center), p(row.end.strftime("%H:%M"), center),
                p(_clock(row.pause), center), p(_clock(row.work), center),
                p(_clock(row.guest), center), p(_clock(row.sunday), center),
                p(_clock(row.holiday), center), p(_clock(row.night), center),
            ])
        subtotal = totals(day_items)
        table_data.append([p(_text_source('server_reports_pdf.text_656074ac61ab') + (f" ({holiday_names})" if holiday_names else ""), small),
                           "", "", "", p(_clock(subtotal["pause"]), center),
                           p(_clock(subtotal["work"]), center), p(_clock(subtotal["guest"]), center),
                           p(_clock(subtotal["sunday"]), center), p(_clock(subtotal["holiday"]), center),
                           p(_clock(subtotal["night"]), center)])
        span_rows.append(len(table_data) - 1)
    if not rows:
        table_data.append([p(_text_source('server_reports_pdf.text_3845608540cd')), "", "", "", "", "", "", "", "", ""])
        span_rows.append(1)
    summed = totals(rows)
    table_data.append([p(_text_source('server_reports_pdf.text_e7f8fdae50a1') if monthly else _text_source('server_reports_pdf.text_6a76ba13ab68'), small), "", "", "",
                       *[p(_clock(summed[k]), center) for k in
                         ("pause", "work", "guest", "sunday", "holiday", "night")]])
    total_row = len(table_data) - 1
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), INK), ("GRID", (0, 0), (-1, -1), .25, colors.HexColor("#d4dfe3")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("BACKGROUND", (0, total_row), (-1, total_row), PALE),
    ]
    for row_no in span_rows:
        style.extend([("SPAN", (0, row_no), (3, row_no)),
                      ("BACKGROUND", (0, row_no), (-1, row_no), PALE)])
    style.append(("SPAN", (0, total_row), (3, total_row)))
    table = Table(table_data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle(style))
    story.extend([table, Spacer(1, 5 * mm)])
    notes = Table([[p(_text_source('server_reports_pdf.text_cc3c8b1a37a8'), small)],
                   [p(_text_source('server_reports_pdf.text_573f12e57765'), small)],
                   [p(_text_source('server_reports_pdf.text_a915d0043f31'), small)]],
                  colWidths=[269 * mm])
    notes.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE),
                               ("BOX", (0, 0), (-1, -1), .4, colors.HexColor("#cbd9df")),
                               ("TOPPADDING", (0, 0), (-1, -1), 4),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story.append(notes)
    doc.build(story)
    return stream.getvalue()
