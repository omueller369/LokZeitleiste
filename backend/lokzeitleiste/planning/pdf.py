"""Farbige Monatskalender und Jahresmatrix für den administrativen Plan."""
from ..localization import source as _text_source
import calendar
from datetime import date
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
from ..version import SOFTWARE_TITLE, SOFTWARE_VERSION
from .palette import COLORS,base_key,background_key
from .calendar_layout import YEAR_COLUMNS,year_slots

MONTHS = ["", _text_source('server_planning_pdf.text_e3e144a75b27'), _text_source('server_planning_pdf.text_742d257d7283'), _text_source('server_planning_pdf.text_86ac4d676251'), _text_source('server_planning_pdf.text_4afe6ea150d5'), _text_source('server_planning_pdf.text_d77b6bd0886e'), _text_source('server_planning_pdf.text_130d0a280e7e'), _text_source('server_planning_pdf.text_161f3271aeb4'), _text_source('server_planning_pdf.text_a66d8970e569'), _text_source('server_planning_pdf.text_cd559ea0abca'), _text_source('server_planning_pdf.text_4e1056bfe86b'), _text_source('server_planning_pdf.text_9de6fe1d7265'), _text_source('server_planning_pdf.text_4bd7dd175722')]
CODES = {_text_source('server_planning_pdf.text_eb8f579b6931'): "A", _text_source('server_planning_pdf.text_35d3a889824d'): "U", _text_source('server_planning_pdf.text_e79aa42d7d18'): "R", _text_source('server_planning_pdf.text_52e37a639da5'): "?", _text_source('server_planning_pdf.text_ecda07db6e0b'):"F", _text_source('server_planning_pdf.text_fd7058ac0c38'):"WE"}
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
                            topMargin=30, bottomMargin=42, title=_text_source('server_planning_pdf.text_af6151b026c9'))
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        if hasattr(style, "fontName"):
            style.fontName = "PlanSans-Bold" if style.fontName == "Helvetica-Bold" else "PlanSans"
    styles.add(ParagraphStyle("PlanHeader", fontName="PlanSans-Bold", fontSize=8, leading=11, textColor=colors.white))
    styles.add(ParagraphStyle("PlanCell", fontName="PlanSans", fontSize=8, leading=10, textColor=DARK))
    title = f"{_text_source('server_planning_pdf.text_d95c5b67c2c6')}{plan['year']}" if yearly else f"{_text_source('server_planning_pdf.text_7389dea602ec')}{MONTHS[plan['month']]} {plan['year']}"
    metadata=Table([[Paragraph(title,styles['Heading2'])],
                    [Paragraph(f"Tf {escape(name)}{_text_source('server_planning_pdf.text_5bfdf41234f1')}{escape(personnel_number)}",styles[_text_source('server_planning_pdf.text_a7248eeb45eb')])]],colWidths=[doc.width])
    metadata.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.4,colors.HexColor('#bdcdd7')),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#EEF4F8')),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    story=[metadata,Spacer(1,12)]
    sums = plan["totals"] if yearly else plan
    summary = [[_text_source('server_planning_pdf.text_aa40f92f3d03'), _text_source('server_planning_pdf.text_be197acfa59b'), _text_source('server_planning_pdf.text_3c1bdf2670ef')],
               [str(sums["work_days"]), str(sums["vacation_days"]), str(sums["rest_days"])],
               [_text_source('server_planning_pdf.text_06e66d1ebcb5'), _text_source('server_planning_pdf.text_4b015cafb095'), _text_source('server_planning_pdf.text_38d7ebf3d44e')],
               [clock(sums["work_target_minutes"]) + " h", clock(sums["vacation_minutes"]) + " h",
                clock(sums["target_minutes"]) + " h"]]
    summary=[[Paragraph(str(value),styles[_text_source('server_planning_pdf.text_a7248eeb45eb')]) for value in row] for row in summary]
    summary_table = Table(summary, colWidths=[doc.width / 3] * 3)
    summary_table.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), "PlanSans"),("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EEF4F8")),
                                      ("TEXTCOLOR", (0, 0), (-1, -1), DARK), ("FONTSIZE", (0, 0), (-1, -1), 10),
                                      ("FONTNAME", (0, 1), (-1, 1), "PlanSans-Bold"),
                                      ("FONTNAME", (0, 3), (-1, 3), "PlanSans-Bold"),
                                      ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
    story += [summary_table,Spacer(1,6),Paragraph(display(_text_source('server_planning_pdf.text_57810709233e'))+": "+display(_text_source('server_planning_pdf.text_9eae8e7efb47') if plan["complete"] else _text_source('server_planning_pdf.text_dc064924c3bb')),styles[_text_source('server_planning_pdf.text_a7248eeb45eb')]),Spacer(1,12)]
    legend_kinds=[k for k in CODES if k!=_text_source('server_planning_pdf.text_52e37a639da5')]
    legend = [[Paragraph(f"{CODES[k]} - {k}",styles["PlanCell"]) for k in legend_kinds]]
    table = Table(legend, colWidths=[doc.width / len(legend_kinds)] * len(legend_kinds), rowHeights=34)
    table.setStyle(TableStyle([("BACKGROUND", (i, 0), (i, 0), colors.HexColor("#" + COLORS[k])) for i, k in enumerate(legend_kinds)] + [("FONTNAME", (0, 0), (-1, -1), "PlanSans")] +
                             [("TEXTCOLOR", (0, 0), (-1, -1), DARK), ("FONTSIZE", (0, 0), (-1, -1), 10),
                              ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story += [table, Spacer(1, 14)]
    if yearly:
        styles.add(ParagraphStyle("YearCell",parent=styles["PlanCell"],fontSize=7,leading=8,alignment=1))
        header = [_text_source('server_planning_pdf.text_2933070469a2')] + [str(i+1) for i in range(YEAR_COLUMNS)] + ["A", "U", "R", _text_source('server_planning_pdf.text_6e96b1407290')]
        rows = [header]
        fills = []
        diagonal = {}
        for row, month in enumerate(plan["months"], start=1):
            cells = [MONTHS[month["month"]]]
            for column,item in enumerate(year_slots(month),start=1):
                if item:
                    kind = _text_source('server_planning_pdf.text_ecda07db6e0b') if item.get("is_holiday") else item["kind"]
                    code=("GT" if item.get("shift")=="border_day" and kind==_text_source('server_planning_pdf.text_eb8f579b6931') else "GN" if item.get("shift")=="border_night" and kind==_text_source('server_planning_pdf.text_eb8f579b6931') else CODES[kind])+("/"+CODES[item["kind"]] if kind==_text_source('server_planning_pdf.text_ecda07db6e0b') and item["kind"]!=_text_source('server_planning_pdf.text_52e37a639da5') else "")
                    note=' '.join(item.get('note','').split())
                    available=(doc.width-223)/YEAR_COLUMNS-2
                    while note and pdfmetrics.stringWidth(note,'PlanSans',7)>available:
                        note=note[:-2].rstrip()+'…' if len(note)>1 else ''
                    weekday=display((_text_source('server_planning_pdf.text_b703fc6aeb9c'),_text_source('server_planning_pdf.text_c2e102ca1f11'),_text_source('server_planning_pdf.text_76c93ad154a5'),_text_source('server_planning_pdf.text_b15c4daa80ba'),_text_source('server_planning_pdf.text_5815ddf1ffb1'),_text_source('server_planning_pdf.text_7c22aad82322'),_text_source('server_planning_pdf.text_a5984592501e'))[date.fromisoformat(item['date']).weekday()])[:2]
                    cells.append(Paragraph(code+'<br/>'+escape(weekday)+'<br/>'+escape(note or '______'),styles["YearCell"]))
                    if kind==_text_source('server_planning_pdf.text_ecda07db6e0b') and item["kind"]!=_text_source('server_planning_pdf.text_52e37a639da5'):diagonal[(column,row)]=base_key(item)
                    fills.append(("BACKGROUND", (column, row), (column, row), colors.HexColor("#" + COLORS[background_key(item)])))
                else:
                    cells.append("")
                    fills.append(("BACKGROUND", (column, row), (column, row), colors.HexColor("#CDD4DA")))
            cells += [str(month[k]) for k in ("work_days", "vacation_days", "rest_days")]
            cells.append(clock(month["target_minutes"]))
            rows.append(cells)
        widths = [78] + [(doc.width - 223) / YEAR_COLUMNS] * YEAR_COLUMNS + [25] * 3 + [70]
        rows=[[Paragraph(str(value),styles['PlanHeader'] if r==0 else styles['PlanCell']) if isinstance(value,str) else value for value in row] for r,row in enumerate(rows)]
        table = DiagonalTable(rows,diagonal_cells=diagonal,colWidths=widths, rowHeights=[26] + [34] * len(plan["months"]), repeatRows=1)
        table.setStyle(TableStyle(fills + [("LEFTPADDING",(1,0),(YEAR_COLUMNS,-1),1),("RIGHTPADDING",(1,0),(YEAR_COLUMNS,-1),1),("FONTNAME", (0, 0), (-1, -1), "PlanSans"),("BACKGROUND", (0, 0), (-1, 0), DARK),
                   ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("TEXTCOLOR", (0, 1), (-1, -1), DARK),
                   ("FONTNAME", (0, 0), (-1, 0), "PlanSans-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
                   ("ALIGN", (1, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                   ("GRID", (0, 0), (-1, -1), .4, colors.white)]))
        story.append(table)
    else:
        rows = [[_text_source('server_planning_pdf.text_b703fc6aeb9c'), _text_source('server_planning_pdf.text_c2e102ca1f11'), _text_source('server_planning_pdf.text_76c93ad154a5'), _text_source('server_planning_pdf.text_b15c4daa80ba'), _text_source('server_planning_pdf.text_5815ddf1ffb1'), _text_source('server_planning_pdf.text_7c22aad82322'), _text_source('server_planning_pdf.text_a5984592501e')]]
        fills = []
        diagonal = {}
        for row, week in enumerate(calendar.Calendar().monthdayscalendar(plan["year"], plan["month"]), start=1):
            cells = []
            for col, day in enumerate(week):
                if not day:
                    cells.append("")
                    continue
                item = plan["days"][day - 1]
                kind = _text_source('server_planning_pdf.text_ecda07db6e0b') if item.get("is_holiday") else item["kind"]
                if kind==_text_source('server_planning_pdf.text_ecda07db6e0b') and item["kind"]!=_text_source('server_planning_pdf.text_52e37a639da5'):diagonal[(col,row)]=base_key(item)
                status=CODES[kind]+("/"+CODES[item["kind"]] if kind==_text_source('server_planning_pdf.text_ecda07db6e0b') and item["kind"]!=_text_source('server_planning_pdf.text_52e37a639da5') else "")
                hours = clock(item["target_minutes"])+" h" if item["target_minutes"] else "0:00 h" if kind in (_text_source('server_planning_pdf.text_e79aa42d7d18'),_text_source('server_planning_pdf.text_ecda07db6e0b')) else _text_source('server_planning_pdf.text_64509e1af49c')
                duty=("<br/>GT 09:00-21:00" if item.get("shift")=="border_day" else "<br/>GN 21:00-09:00 +1" if item.get("shift")=="border_night" else "")
                cells.append(Paragraph(f"<b>{day:02d}</b><br/>{status} - {kind}<br/>{hours}{duty}", styles["PlanCell"]))
                fills.append(("BACKGROUND", (col, row), (col, row), colors.HexColor("#" + COLORS[background_key(item)])))
            rows.append(cells)
        rows=[[Paragraph(str(value),styles['PlanHeader'] if r==0 else styles['PlanCell']) if isinstance(value,str) else value for value in row] for r,row in enumerate(rows)]
        table = DiagonalTable(rows,diagonal_cells=diagonal,colWidths=[doc.width / 7] * 7, rowHeights=[25] + [60] * (len(rows) - 1))
        table.setStyle(TableStyle(fills + [("FONTNAME", (0, 0), (-1, -1), "PlanSans"),("BACKGROUND", (0, 0), (-1, 0), DARK), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                   ("FONTSIZE", (0, 0), (-1, 0), 9), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                   ("LEFTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 6),
                   ("GRID", (0, 0), (-1, -1), 1, colors.white)]))
        story.append(table)
    information=[[_text_source('server_planning_pdf.text_ecda07db6e0b'),_text_source('server_planning_pdf.text_15af5090e04b')],
                 [_text_source('server_planning_pdf.text_d1e972bc4bd8'),_text_source('server_planning_pdf.text_becfda4ee0af')],
                 [_text_source('server_planning_pdf.text_98deca758e26'),f"{sums['holiday_days']}{_text_source('server_planning_pdf.text_f6131d43a16f')}"]]
    if not yearly:
        for item in plan['days']:
            if item.get('is_holiday'):information.append([item['date'],f"{_text_source('server_planning_pdf.text_6ae474f9b0ec')}{item['holiday_name']}{_text_source('server_planning_pdf.text_862ada3acf12')}"])
            if item.get('note'):information.append([item['date'],item['note']])
    info=Table([[Paragraph(escape(str(value)),styles['PlanCell']) for value in row] for row in information],colWidths=[doc.width*.22,doc.width*.78],splitInRow=1)
    info.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.4,colors.HexColor('#bdcdd7')),('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(0,-1),colors.HexColor('#EEF4F8')),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    story += [Spacer(1,12),info]
    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("PlanSans",8)
        canvas.setFillColor(colors.HexColor('#A0A0A0'))
        canvas.drawCentredString(page[0]/2,29,SOFTWARE_TITLE+' · '+display(_text_source('server_planning_pdf.text_dd167905de0d'))+' '+SOFTWARE_VERSION)
        canvas.restoreState()
        canvas.setFont("PlanSans", 8)
        canvas.setFillColor(DARK)
        canvas.drawString(30, 16, display(_text_source('server_planning_pdf.text_8c3009c767ed')))
        canvas.drawRightString(page[0] - 30, 16, display(f"{_text_source('server_planning_pdf.text_e00b871f85fd')}{document.page}"))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
