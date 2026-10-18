import io
import json
import re
from datetime import datetime,date,timezone
from zoneinfo import ZoneInfo
from calendar import monthrange
from html import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
from sqlalchemy import select

from ..models import User,TfProfile,WorkMonth,WorkEntry,DutyReport,DocumentFile,ReportDispatch
from ..i18n import translate,user_language
from ..pdf_locale import register_fonts
from ..reports.intervals import period_entries,entry_end_date,touched_months
from ..reports.daily import day_rows
from ..reports.monthly import summarize_month
from ..reports.pdf import render_receipt_pdf
from .storage import generated,today


def creation_day(value):
    if value.tzinfo is None:value=value.replace(tzinfo=timezone.utc)
    return value.astimezone(ZoneInfo('Europe/Berlin')).strftime('%Y-%m-%d')


def clock(n):return f'{int(n)//60}:{int(n)%60:02d}'


def pdf_document(title,lines,rows=None):
    register_fonts('DocumentSans')
    style=ParagraphStyle('Doc',fontName='DocumentSans',fontSize=9,leading=13)
    heading=ParagraphStyle('DocHeading',parent=style,fontName='DocumentSans-Bold',fontSize=17,leading=22,textColor=colors.HexColor('#17445b'))
    paragraph=lambda text:Paragraph(escape(str(text)).replace('\n','<br/>'),style)
    story=[Paragraph(escape(title),heading),Spacer(1,14)]+[paragraph(line) for line in lines]
    if rows:
        story.append(Spacer(1,14));table=Table([[paragraph(v) for v in row] for row in rows],repeatRows=1,hAlign='LEFT')
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dcebf4')),('GRID',(0,0),(-1,-1),.4,colors.lightgrey),('VALIGN',(0,0),(-1,-1),'TOP'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f4f7fa')])]))
        story.append(table)
    stream=io.BytesIO();SimpleDocTemplate(stream,pagesize=A4,leftMargin=34,rightMargin=34,topMargin=30,bottomMargin=30).build(story)
    return stream.getvalue()


def work_report_pdf(db,user,report):
    data=json.loads(report.payload_json);profile=db.get(TfProfile,user.id);lang=user_language(db,user.id);t=lambda s:translate(s,lang)
    from ..work_reports.schemas import train_pause_minutes
    from ..work_reports.service import report_view
    credited=report_view(db,report)['credited_minutes']
    lines=[f'{profile.first_name} {profile.last_name} · {user.username}',
        f'{t("Arbeitsbericht")}: {report.id}',f'{t("Dienstart")}: {t("Dienstschicht" if data.get("kind","Sonstige Erfassung")=="Sonstige Erfassung" else data["kind"])}',
        f'{t("Dienstbeginn")}: {data["start_at"]}',f'{t("Dienstende")}: {data["end_at"]}',
        f'{t("Arbeitszeit")}: {clock(credited)}',
        f'{t("Dokumentierte Pausen gesamt")}: {data["actual_pause"]+train_pause_minutes(data.get("train_journeys",[]))} min',
        f'{t("Ausbleibe")}: {", ".join(data.get("ausbleibe",[]))}',data.get('overrun_reason','')]
    for trip in data['trips']:
        lines += [t('Gastfahrten')+': '+f'{trip["start_station"]} {trip.get("start_station_name","")} → {trip["end_station"]} {trip.get("end_station_name","")}',
            f'{trip["start_at"]} → {trip["end_at"]} · {t({"train":"Zug","car":"Auto","taxi":"Taxi","public_transport":"ÖPNV","other":"Anderes Transportmittel"}[trip["transport"]])} {trip.get("transport_detail","")}'+(' · Sz' if trip.get('self_payer') else '')]
    for train in data.get('train_journeys',[]):
        lines += [t('Zugfahrt')+': '+train['train_number'],f'{train["start_station"]} {train.get("start_station_name","")} {train["start_at"]} → {train["end_station"]} {train.get("end_station_name","")} {train["end_at"]}']
        for event in train.get('events',[]):
            lines += [f'{event["start_at"]} → {event["end_at"]} · {t(event["reason"])} {event.get("reason_detail","")} · {event["cause"]} {event.get("cause_detail","")} · {event["station"]} {event.get("station_name","")}']
    return pdf_document(t('Arbeitsbericht'),lines)


def archive_report(db,user,report,queue_email=False,include_months=True):
    db.flush();content=work_report_pdf(db,user,report)
    generated(db,user,f'Dokumente/Arbeitsberichte/{creation_day(report.created_at)}/Arbeitsbericht-{report.id}.pdf',content,f'work-report:{report.id}')
    entry=db.get(WorkEntry,report.entry_id)
    if queue_email:
        profile=db.get(TfProfile,user.id)
        db.add(ReportDispatch(tf_user_id=user.id,work_month_id=entry.work_month_id,recipient_email=profile.email,
            filename=f'Arbeitsbericht-{report.id}.pdf',pdf_data=content,status='pending'))
    if include_months:
        for year,month in touched_months(entry.entry_date,entry_end_date(entry)):
            archive_month(db,user,year,month)


def archive_month(db,user,year,month):
    profile=db.get(TfProfile,user.id)
    if not profile:return
    state=profile.federal_state or 'BE';entries=period_entries(db,user.id,date(year,month,1),date(year,month,monthrange(year,month)[1]))
    lang=user_language(db,user.id);t=lambda s:translate(s,lang)
    summary=summarize_month(entries,year=year,month=month,federal_state=state)
    from ..accounts.tf_profiles import monthly_minutes
    lines=[f'{profile.first_name} {profile.last_name} · {user.username}',f'{year}-{month:02d}',f'{t("Sollstunden")}: {clock(monthly_minutes(db,user.id,year,month))}']
    labels={'work_without_guest':'Arbeitszeit ohne Gastfahrten','guest':'Gastfahrten gesamt','topup':'Auffüllung','vacation':'Urlaub','sick':'Krank','credited':'Angerechnete Arbeitszeit','sunday':'Sonntag','holiday':'Feiertag','night':'Nacht'}
    lines += [f'{t(label)}: {clock(summary["totals"][key])}' for key,label in labels.items()]
    rows=[[t('Datum'),t('Dienstart'),t('Angerechnete Arbeitszeit')]]+[[r['date'],t(r['type']),clock(r['credited'])] for r in summary['days']]
    folder=f'Dokumente/Monatsabrechnung/{year}-{month:02d}'
    generated(db,user,folder+'/Monatszusammenfassung.pdf',pdf_document(t('Monatszusammenfassung'),lines,rows),f'month-summary:{year}-{month:02d}')
    report=render_receipt_pdf(first_name=profile.first_name,last_name=profile.last_name,personnel_number=profile.personnel_number,
        federal_state=state,year=year,month=month,received_at=today(),rows=[r for r in day_rows(entries,state) if r.day.year==year and r.day.month==month],lang=lang,monthly=True)
    generated(db,user,folder+'/Monatsbericht.pdf',report,f'month-report:{year}-{month:02d}')


def archive_dispatch(db,dispatch):
    user=db.get(User,dispatch.tf_user_id)
    db.scalar(select(User).where(User.id==user.id).with_for_update())
    match=re.fullmatch(r'Arbeitsbericht-(\d+)\.pdf',dispatch.filename)
    if match:
        report=db.get(DutyReport,int(match[1]))
        latest=db.scalar(select(ReportDispatch.id).where(ReportDispatch.tf_user_id==user.id,ReportDispatch.filename==dispatch.filename).order_by(ReportDispatch.id.desc()).limit(1))
        if report and report.tf_user_id==user.id and latest==dispatch.id:
            generated(db,user,f'Dokumente/Arbeitsberichte/{creation_day(report.created_at)}/{dispatch.filename}',dispatch.pdf_data,f'work-report:{report.id}')
            entry=db.get(WorkEntry,report.entry_id)
            for year,month in touched_months(entry.entry_date,entry_end_date(entry)):archive_month(db,user,year,month)
    else:
        generated(db,user,f'Dokumente/Arbeitsberichte/{creation_day(dispatch.created_at)}/Eingang-{dispatch.id}.pdf',dispatch.pdf_data,f'dispatch:{dispatch.id}')
        period=db.get(WorkMonth,dispatch.work_month_id);archive_month(db,user,period.year,period.month)


def backfill_documents(db):
    from ..user_directories import user_path
    from calendar import monthrange
    # Include months reached by overnight duties, even without a WorkMonth row there.
    for user in db.scalars(select(User).where(User.role=='tf')):
        db.scalar(select(User).where(User.id==user.id).with_for_update())
        root=user_path(user.username,user.role)
        for report in db.scalars(select(DutyReport).where(DutyReport.tf_user_id==user.id)):
            stored=db.scalar(select(DocumentFile).where(DocumentFile.owner_id==user.id,DocumentFile.source_key==f'work-report:{report.id}'))
            if not stored or not (root/stored.relative_path).is_file():archive_report(db,user,report,include_months=False)
        periods={(m.year,m.month) for m in db.scalars(select(WorkMonth).where(WorkMonth.tf_user_id==user.id))}
        entries=db.scalars(select(WorkEntry).join(WorkMonth).where(WorkMonth.tf_user_id==user.id)).all()
        for entry in entries:periods.update(touched_months(entry.entry_date,entry_end_date(entry)))
        for year,month in periods:
            row=db.scalar(select(DocumentFile).where(DocumentFile.owner_id==user.id,DocumentFile.source_key==f'month-summary:{year}-{month:02d}'))
            relevant=[e for e in entries if (year,month) in touched_months(e.entry_date,entry_end_date(e))]
            updated=max((e.updated_at for e in relevant),default=None)
            report=db.scalar(select(DocumentFile).where(DocumentFile.owner_id==user.id,DocumentFile.source_key==f'month-report:{year}-{month:02d}'))
            if not row or not report or not (root/row.relative_path).is_file() or not (root/report.relative_path).is_file() or (updated and updated>row.updated_at):
                try:archive_month(db,user,year,month)
                except ValueError:
                    import logging
                    logging.getLogger(__name__).exception('Monatsarchiv enthält widersprüchliche Altdaten: Benutzer %s, %s-%s',user.id,year,month)
