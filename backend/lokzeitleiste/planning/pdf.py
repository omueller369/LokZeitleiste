"""Farbige Monatskalender und Jahresmatrix für den administrativen Plan."""
import calendar
from pathlib import Path
import reportlab
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, A3, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from .excel import COLORS

MONTHS = ["", "Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
CODES = {"Arbeitstag": "A", "Urlaub": "U", "Ruhetag": "R", "Ungeplant": "?", "Feiertag":"F"}
DARK = colors.HexColor("#173E55")

from ..pdf_locale import register_fonts, LocalizedParagraph as Paragraph
from ..i18n import display
register_fonts('PlanSans')


class DiagonalTable(Table):
    def __init__(self,*args,diagonal_cells=None,**kwargs):
        self.diagonal_cells=diagonal_cells or {}
        super().__init__(*args,**kwargs)

    def _drawCell(self,cellval,cellstyle,pos,size):
        kind=self.diagonal_cells.get(pos)
        if kind:
            x,y=pos;w,h=size
            canvas=self.canv;canvas.saveState();canvas.setFillColor(colors.HexColor('#'+COLORS[kind]))
            path=canvas.beginPath();path.moveTo(x,y);path.lineTo(x+w,y);path.lineTo(x+w,y+h);path.close()
            canvas.drawPath(path,fill=1,stroke=0);canvas.restoreState()
        super()._drawCell(cellval,cellstyle,pos,size)

    def draw(self):
        # ReportLab passes positions instead of row/column indices to _drawCell.
        original=self.diagonal_cells
        self.diagonal_cells={(self._colpositions[c],self._rowpositions[r+1]):kind for (c,r),kind in original.items()}
        try:super().draw()
        finally:self.diagonal_cells=original


def clock(minutes):
    return f"{minutes // 60}:{minutes % 60:02d}"


def render_plan_pdf(plan: dict, *, name: str, personnel_number: str, yearly=False) -> bytes:
    buffer = BytesIO()
    page = landscape(A3) if yearly else A4
    doc = SimpleDocTemplate(buffer, pagesize=page, rightMargin=30, leftMargin=30,
                            topMargin=30, bottomMargin=30, title="LokZeitleiste Arbeitszeitplan")
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        if hasattr(style, "fontName"):
            style.fontName = "PlanSans-Bold" if style.fontName == "Helvetica-Bold" else "PlanSans"
    styles.add(ParagraphStyle("PlanHeader", fontName="PlanSans-Bold", fontSize=8, leading=11, textColor=colors.white))
    styles.add(ParagraphStyle("PlanCell", fontName="PlanSans", fontSize=9, leading=13, textColor=DARK))
    title = f"Jahresplan {plan['year']}" if yearly else f"Monatsplan {MONTHS[plan['month']]} {plan['year']}"
    story = [Paragraph("LokZeitleiste · " + title, styles["Title"]),
             Paragraph(f"Tf {escape(name)} · Personalnummer {escape(personnel_number)}", styles["Normal"]), Spacer(1, 12)]
    sums = plan["totals"] if yearly else plan
    summary = [["Erforderliche Arbeitstage", "Urlaubstage", "Ruhetage", "Ungeplant"],
               [str(sums["work_days"]), str(sums["vacation_days"]), str(sums["rest_days"]), str(sums["unplanned_days"])],
               ["Arbeitssoll", "Urlaubsgutschrift", "Soll inkl. Urlaub", "Planstatus"],
               [clock(sums["work_target_minutes"]) + " h", clock(sums["vacation_minutes"]) + " h",
                clock(sums["target_minutes"]) + " h", "Vollständig" if plan["complete"] else "Unvollständig"]]
    summary=[[Paragraph(str(value),styles['Normal']) for value in row] for row in summary]
    summary_table = Table(summary, colWidths=[doc.width / 4] * 4, rowHeights=[34, 28, 34, 28])
    summary_table.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), "PlanSans"),("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EEF4F8")),
                                      ("TEXTCOLOR", (0, 0), (-1, -1), DARK), ("FONTSIZE", (0, 0), (-1, -1), 10),
                                      ("FONTNAME", (0, 1), (-1, 1), "PlanSans-Bold"),
                                      ("FONTNAME", (0, 3), (-1, 3), "PlanSans-Bold"),
                                      ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
    story += [summary_table, Spacer(1, 12)]
    legend = [[Paragraph(f"{CODES[k]} - {k}",styles["PlanCell"]) for k in CODES]]
    table = Table(legend, colWidths=[doc.width / len(CODES)] * len(CODES), rowHeights=34)
    table.setStyle(TableStyle([("BACKGROUND", (i, 0), (i, 0), colors.HexColor("#" + COLORS[k])) for i, k in enumerate(CODES)] + [("FONTNAME", (0, 0), (-1, -1), "PlanSans")] +
                             [("TEXTCOLOR", (0, 0), (-1, -1), DARK), ("FONTSIZE", (0, 0), (-1, -1), 10),
                              ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story += [table, Spacer(1, 14)]
    if yearly:
        header = ["Monat"] + [str(i) for i in range(1, 32)] + ["A", "U", "R", "?", "Soll h"]
        rows = [header]
        fills = []
        diagonal = {}
        for row, month in enumerate(plan["months"], start=1):
            cells = [MONTHS[month["month"]]]
            for column in range(1, 32):
                if column <= len(month["days"]):
                    item=month["days"][column-1]
                    kind = "Feiertag" if item.get("is_holiday") else item["kind"]
                    cells.append(CODES[kind]+("/"+CODES[item["kind"]] if kind=="Feiertag" and item["kind"]!="Ungeplant" else ""))
                    if kind=="Feiertag" and item["kind"]!="Ungeplant":diagonal[(column,row)]=item["kind"]
                    fills.append(("BACKGROUND", (column, row), (column, row), colors.HexColor("#" + COLORS[kind])))
                else:
                    cells.append("")
                    fills.append(("BACKGROUND", (column, row), (column, row), colors.HexColor("#CDD4DA")))
            cells += [str(month[k]) for k in ("work_days", "vacation_days", "rest_days", "unplanned_days")]
            cells.append(clock(month["target_minutes"]))
            rows.append(cells)
        widths = [78] + [(doc.width - 248) / 31] * 31 + [25] * 4 + [70]
        rows=[[Paragraph(str(value),styles['PlanHeader'] if r==0 else styles['PlanCell']) if isinstance(value,str) else value for value in row] for r,row in enumerate(rows)]
        table = DiagonalTable(rows,diagonal_cells=diagonal,colWidths=widths, rowHeights=[26] + [30] * 12, repeatRows=1)
        table.setStyle(TableStyle(fills + [("FONTNAME", (0, 0), (-1, -1), "PlanSans"),("BACKGROUND", (0, 0), (-1, 0), DARK),
                   ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("TEXTCOLOR", (0, 1), (-1, -1), DARK),
                   ("FONTNAME", (0, 0), (-1, 0), "PlanSans-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
                   ("ALIGN", (1, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                   ("GRID", (0, 0), (-1, -1), .4, colors.white)]))
        story.append(table)
    else:
        rows = [["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]]
        fills = []
        diagonal = {}
        for row, week in enumerate(calendar.Calendar().monthdayscalendar(plan["year"], plan["month"]), start=1):
            cells = []
            for col, day in enumerate(week):
                if not day:
                    cells.append("")
                    continue
                item = plan["days"][day - 1]
                kind = "Feiertag" if item.get("is_holiday") else item["kind"]
                if kind=="Feiertag" and item["kind"]!="Ungeplant":diagonal[(col,row)]=item["kind"]
                status=CODES[kind]+("/"+CODES[item["kind"]] if kind=="Feiertag" and item["kind"]!="Ungeplant" else "")
                hours = "8:00 h" if item["target_minutes"] else "0:00 h" if kind in ("Ruhetag","Feiertag") else "Offen"
                cells.append(Paragraph(f"<b>{day:02d}</b><br/>{status} - {kind}<br/>{hours}", styles["PlanCell"]))
                fills.append(("BACKGROUND", (col, row), (col, row), colors.HexColor("#" + COLORS[kind])))
            rows.append(cells)
        rows=[[Paragraph(str(value),styles['PlanHeader'] if r==0 else styles['PlanCell']) if isinstance(value,str) else value for value in row] for r,row in enumerate(rows)]
        table = DiagonalTable(rows,diagonal_cells=diagonal,colWidths=[doc.width / 7] * 7, rowHeights=[25] + [66] * (len(rows) - 1))
        table.setStyle(TableStyle(fills + [("FONTNAME", (0, 0), (-1, -1), "PlanSans"),("BACKGROUND", (0, 0), (-1, 0), DARK), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                   ("FONTSIZE", (0, 0), (-1, 0), 9), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                   ("LEFTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 6),
                   ("GRID", (0, 0), (-1, -1), 1, colors.white)]))
        story.append(table)
    story += [Spacer(1, 12), Paragraph("Berliner gesetzliche Feiertage = 0 h Soll, auch bei eingetragenem Arbeitstag oder Urlaub. "
              "Diagonale Farbe: Feiertag und gespeicherte Tagesart (F/A, F/U, F/R). Sonst: Urlaub = 8 h, Ruhetag = 0 h. Ungeplante Nichtfeiertage bleiben offen.", styles["Normal"])]
    story += [Spacer(1,8), Paragraph(f"Feiertage Berlin: {sums['holiday_days']} Tage mit 0 h Soll.",styles["Normal"])]
    if not yearly:
        for item in plan["days"]:
            if item.get("is_holiday"):
                story.append(Paragraph(f"{item['date']}: Feiertag - {escape(item['holiday_name'])} (0 h Soll)",styles["Normal"]))
        notes = [d for d in plan["days"] if d["note"]]
        if notes:
            story += [Spacer(1, 12), Paragraph("Notizen", styles["Heading2"])]
            for item in notes:
                story.append(Paragraph(f"{item['date']}: {escape(item['note'])}", styles["Normal"]))
    def footer(canvas, document):
        canvas.setFont("PlanSans", 8)
        canvas.setFillColor(DARK)
        canvas.drawString(30, 16, display("Administrativer Plan · aktueller gespeicherter Stand"))
        canvas.drawRightString(page[0] - 30, 16, display(f"Seite {document.page}"))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
