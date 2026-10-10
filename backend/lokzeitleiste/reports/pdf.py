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
                       received_at: datetime, rows: list[DayRow], lang: str | None = None) -> bytes:
    token=request_language.set(lang or request_language.get())
    try:
        return _render_receipt_pdf(first_name=first_name,last_name=last_name,personnel_number=personnel_number,federal_state=federal_state,year=year,month=month,received_at=received_at,rows=rows)
    finally:
        request_language.reset(token)


def _render_receipt_pdf(*, first_name, last_name, personnel_number, federal_state, year, month, received_at, rows):
    stream = BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=landscape(A4),
                            leftMargin=14 * mm, rightMargin=14 * mm,
                            topMargin=13 * mm, bottomMargin=13 * mm,
                            title="LokZeitleiste - Tabellarische Eingangsbestätigung")
    heading = ParagraphStyle("heading", fontName="ReceiptSans-Bold", fontSize=12, leading=15, textColor=INK)
    body = ParagraphStyle("body", fontName="ReceiptSans", fontSize=8.2, leading=11, textColor=INK)
    small = ParagraphStyle("small", parent=body, fontSize=7.4, leading=9.5)
    center = ParagraphStyle("center", parent=body, alignment=TA_CENTER)
    def p(value, style=body):
        return Paragraph(escape(str(value)), style)
    story = []
    metadata = Table([
        [p("LokZeitleiste - Eingangsbestätigung", heading), p(f"Monat: {month:02d}/{year}")],
        [p(f"Tf: {first_name} {last_name}"), p(f"Personalnummer: {personnel_number}")],
        [p(f"Eingang: {received_at:%d.%m.%Y %H:%M} Uhr"), p(f"Feiertagskalender: DE-{federal_state}")],
    ], colWidths=[135 * mm, 134 * mm])
    metadata.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PALE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd9df")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dce5e9")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([metadata, Spacer(1, 8 * mm)])
    headers = ["Datum", "Art", "Beginn", "Ende", "Pause", "Arbeit", "Gastfahrt", "Sonntag", "Feiertag", "Nacht"]
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
        table_data.append([p("Tagessumme" + (f" ({holiday_names})" if holiday_names else ""), small),
                           "", "", "", p(_clock(subtotal["pause"]), center),
                           p(_clock(subtotal["work"]), center), p(_clock(subtotal["guest"]), center),
                           p(_clock(subtotal["sunday"]), center), p(_clock(subtotal["holiday"]), center),
                           p(_clock(subtotal["night"]), center)])
        span_rows.append(len(table_data) - 1)
    if not rows:
        table_data.append([p("Keine Einträge empfangen."), "", "", "", "", "", "", "", "", ""])
        span_rows.append(1)
    summed = totals(rows)
    table_data.append([p("Summe der Übermittlung", small), "", "", "",
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
    notes = Table([[p("Bestätigung der empfangenen Daten - keine Entgelt- oder Tarifabrechnung.", small)],
                   [p("Arbeitszeit = Zugfahrt, Bereitschaft und Sonstige Erfassung abzüglich Pause. Gastfahrt ist enthalten und separat ausgewiesen.", small)],
                   [p("Mangels genauer Zeitlage liegt die Pause rechnerisch am Ende, Gastfahrt am Beginn des Zeitraums. Sonntag, Feiertag und Nacht (22:00-06:00 Uhr) sind damit vorläufig; Zeitwechsel werden nicht gesondert bewertet.", small)]],
                  colWidths=[269 * mm])
    notes.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE),
                               ("BOX", (0, 0), (-1, -1), .4, colors.HexColor("#cbd9df")),
                               ("TOPPADDING", (0, 0), (-1, -1), 4),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story.append(notes)
    doc.build(story)
    return stream.getvalue()
