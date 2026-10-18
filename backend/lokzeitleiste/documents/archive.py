import io
import json
import re
from datetime import datetime,date,timezone
from zoneinfo import ZoneInfo
from calendar import monthrange
from html import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
from sqlalchemy import select,or_

from ..models import User,TfProfile,WorkMonth,WorkEntry,DutyReport,DocumentFile,ReportDispatch,DocumentRenderState
from ..i18n import translate,user_language
from ..pdf_locale import register_fonts
from ..reports.intervals import period_entries,entry_end_date,touched_months
from ..reports.daily import day_rows
from ..reports.monthly import summarize_month
from ..reports.pdf import render_receipt_pdf
from .storage import generated,today,relocate


def report_folder(report):
    # Report timestamps are local duty times; never use upload/creation time.
    start=datetime.fromisoformat(json.loads(report.payload_json)['start_at'])
    if start.tzinfo is not None:start=start.astimezone(ZoneInfo('Europe/Berlin'))
    return 'Dokumente/Arbeitsberichte/'+start.strftime('%Y/%m/%d')


def month_folder(year,month):
    return f'Dokumente/Monatsabrechnung/{year:04d}/{month:02d}'


def clock(n):return f'{int(n)//60}:{int(n)%60:02d}'


FORMAT_VERSION=3


def report_filename(report):
    data=json.loads(report.payload_json)
    day='-'.join(report_folder(report).split('/')[-3:])
    version=int(data.get('_train_revision',0))+1
    return f'{day}-{version}-{report.id}-Arbeitsbericht.pdf'


def rendered(db,row):
    db.flush()
    state=db.get(DocumentRenderState,row.id)
    if not state:db.add(DocumentRenderState(document_id=row.id,format_version=FORMAT_VERSION))
    else:state.format_version=FORMAT_VERSION


def needs_render(db,row):
    state=db.get(DocumentRenderState,row.id) if row else None
    return not state or state.format_version<FORMAT_VERSION


def pdf_document(title,lines,rows=None,sections=None,wide=False):
    register_fonts('DocumentSans')
    width,height=landscape(A4) if wide else A4
    usable=width-68-12  # SimpleDocTemplate frame has 6 pt padding on each side.
    style=ParagraphStyle('Doc',fontName='DocumentSans',fontSize=8,leading=11,splitLongWords=True)
    heading=ParagraphStyle('DocHeading',parent=style,fontName='DocumentSans-Bold',fontSize=17,leading=22,textColor=colors.HexColor('#17445b'))
    subheading=ParagraphStyle('DocSection',parent=heading,fontSize=11,leading=15,spaceBefore=12,spaceAfter=6,keepWithNext=True)
    paragraph=lambda text:Paragraph(escape(str(text)).replace('\n','<br/>'),style)
    def table(values,header=False,indent=0):
        space=usable-indent
        count=len(values[0]);widths=[space/count]*count
        if count==2:widths=[space*.29,space*.71]
        elif count==5:widths=[space*w for w in (.12,.27,.17,.27,.17)]
        elif count==6:widths=[space*w for w in (.32,.18,.16,.14,.14,.06)]
        elif count==7:widths=[space*w for w in (.18,.18,.14,.14,.08,.22,.06)]
        result=Table([[paragraph(v) for v in row] for row in values],colWidths=widths,repeatRows=1 if header else 0,hAlign='RIGHT' if indent else 'LEFT',splitInRow=1)
        commands=[('GRID',(0,0),(-1,-1),.4,colors.HexColor('#bdcdd7')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('ROWBACKGROUNDS',(0,0),(-1,-1),[colors.white,colors.HexColor('#f1f6f8')])]
        if header:commands.append(('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dcebf4')))
        result.setStyle(TableStyle(commands));return result
    # Key/value metadata is always tabular; legacy string callers remain supported.
    metadata=[list(value) if isinstance(value,(tuple,list)) else list(value.split(': ',1)) if ': ' in value else ['',value] for value in lines]
    story=[Paragraph(escape(title),heading),Spacer(1,12)]
    if metadata:story.append(table(metadata))
    if rows:story += [Spacer(1,12),table(rows,True)]
    for section in sections or []:
        label,values=section[:2];indent=usable*section[2] if len(section)>2 else 0
        section_style=ParagraphStyle('IndentedSection',parent=subheading,leftIndent=indent)
        story += [Paragraph(escape(label),section_style),table(values,True,indent)]
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont('DocumentSans',8);canvas.setFillColor(colors.HexColor('#546b7b'));canvas.drawRightString(width-34,16,str(doc.page));canvas.restoreState()
    stream=io.BytesIO();SimpleDocTemplate(stream,pagesize=(width,height),leftMargin=34,rightMargin=34,topMargin=30,bottomMargin=32,title=title).build(story,onFirstPage=footer,onLaterPages=footer)
    return stream.getvalue()


def report_time(value,start,end,previous=None):
    value=datetime.fromisoformat(value);start=datetime.fromisoformat(start);end=datetime.fromisoformat(end)
    reference=datetime.fromisoformat(previous) if previous else start
    changed=start.date()!=end.date() and value.date()!=reference.date()
    return value.strftime('%d.%m.%Y %H:%M' if changed else '%H:%M')


def work_report_pdf(db,user,report):
    data=json.loads(report.payload_json);profile=db.get(TfProfile,user.id);lang=user_language(db,user.id);t=lambda s:translate(s,lang)
    from ..work_reports.schemas import train_pause_minutes,minutes
    from ..work_reports.service import report_view
    view=report_view(db,report);credited=view['credited_minutes']
    stamp=lambda value,previous=None:report_time(value,data['start_at'],data['end_at'],previous)
    station=lambda row,key:(' '.join([row.get(key,''),row.get(key+'_name','')])).strip() or '-'
    lines=[(t('TF-Nummer'),user.username),(t('Vorname')+' / '+t('Nachname'),f'{profile.first_name} {profile.last_name}'),
        (t('Arbeitsbericht'),report.id),(t('Version'),int(data.get('_train_revision',0))+1),
        (t('Dienstart'),t('Dienstschicht' if data.get('kind','Sonstige Erfassung')=='Sonstige Erfassung' else data['kind'])),
        (t('Dienstbeginn'),stamp(data['start_at'])),(t('Dienstende'),stamp(data['end_at'],data['start_at'])),(t('Arbeitszeit'),clock(credited)),
        (t('Dokumentierte Pausen gesamt'),str(data['actual_pause']+train_pause_minutes(data.get('train_journeys',[])))+' min'),
        (t('Ausbleibe'),', '.join(data.get('ausbleibe',[])) or '-'),(t('Begründung für mehr als zwölf Stunden'),data.get('overrun_reason','') or '-')]
    lines += [(t('Gesamtarbeitszeit (Dienstspanne)'),clock(view['duration_minutes'])),(t('Mindestpause nach Dienstregel'),str(view['minimum_pause_minutes'])+' min'),(t('Gastfahrten gesamt'),clock(view['guest_total_minutes'])),(t('Gastfahrt im Dienst'),clock(view['guest_minutes'])),(t('Gastfahrt außerhalb des Dienstes'),clock(view['external_guest_minutes']))]
    transport={'train':'Zug','car':'Auto','taxi':'Taxi','public_transport':'ÖPNV','other':'Anderes Transportmittel'}
    guests=[[t(v) for v in ['Von','Nach','Beginn','Ende','Dauer','Verkehrsmittel','Sz']]]
    previous_guest=None
    for trip in data['trips']:
        guests.append([station(trip,'start_station'),station(trip,'end_station'),stamp(trip['start_at'],previous_guest),stamp(trip['end_at'],trip['start_at']),clock(minutes(datetime.fromisoformat(trip['start_at']),datetime.fromisoformat(trip['end_at']))),t(transport[trip['transport']])+(' / '+trip['transport_detail'] if trip.get('transport_detail') else ''),'✓' if trip.get('self_payer') else '-'])
        previous_guest=trip['end_at']
    if len(guests)==1:guests.append(['-']*7)
    sections=[(t('Gastfahrten'),guests)]
    for train in data.get('train_journeys',[]):
        header=[[t(v) for v in ['Zugnummer','StartBf','Abfahrt','ZielBf','Ankunft']],[train['train_number'],station(train,'start_station'),stamp(train['start_at']),station(train,'end_station'),stamp(train['end_at'],train['start_at'])]]
        sections.append((t('Zugfahrt')+' '+train['train_number'],header))
        events=[[t(v) for v in ['Grund','Verursacher','Meldestelle/Ort','Von','Bis','Dauer']]]
        previous_event=None
        for event in train.get('events',[]):
            events.append([t(event['reason'])+(' / '+event['reason_detail'] if event.get('reason_detail') else ''),t(event['cause'])+(' / '+event['cause_detail'] if event.get('cause_detail') else ''),station(event,'station'),stamp(event['start_at'],previous_event),stamp(event['end_at'],event['start_at']),clock(minutes(datetime.fromisoformat(event['start_at']),datetime.fromisoformat(event['end_at'])))])
            previous_event=event['end_at']
        if len(events)==1:events.append(['-']*6)
        sections.append((t('Zugfahrt'),events,.12))
    return pdf_document(t('Arbeitsbericht vom')+' '+datetime.fromisoformat(data['start_at']).strftime('%d.%m.%Y'),lines,sections=sections,wide=True)


def archive_report(db,user,report,queue_email=False,include_months=True):
    db.flush();content=work_report_pdf(db,user,report)
    rendered(db,generated(db,user,f'{report_folder(report)}/{report_filename(report)}',content,f'work-report:{report.id}'))
    entry=db.get(WorkEntry,report.entry_id)
    if queue_email:
        profile=db.get(TfProfile,user.id)
        db.add(ReportDispatch(tf_user_id=user.id,work_month_id=entry.work_month_id,recipient_email=profile.email,
            filename=report_filename(report),pdf_data=content,status='pending'))
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
    lines=[(t('TF-Nummer'),user.username),(t('Vorname')+' / '+t('Nachname'),f'{profile.first_name} {profile.last_name}'),(t('Monat'),f'{year}-{month:02d}'),(t('Sollstunden'),clock(monthly_minutes(db,user.id,year,month)))]
    labels={'work_without_guest':'Arbeitszeit ohne Gastfahrten','guest':'Gastfahrten gesamt','topup':'Auffüllung','vacation':'Urlaub','sick':'Krank','credited':'Angerechnete Arbeitszeit','sunday':'Sonntag','holiday':'Feiertag','night':'Nacht'}
    lines += [(t(label),clock(summary['totals'][key])) for key,label in labels.items()]
    rows=[[t('Datum'),t('Dienstart'),t('Angerechnete Arbeitszeit')]]+[[r['date'],t(r['type']),clock(r['credited'])] for r in summary['days']]
    folder=month_folder(year,month)
    rendered(db,generated(db,user,folder+'/Monatszusammenfassung.pdf',pdf_document(t('Monatszusammenfassung'),lines,rows),f'month-summary:{year}-{month:02d}'))
    report=render_receipt_pdf(first_name=profile.first_name,last_name=profile.last_name,personnel_number=profile.personnel_number,
        federal_state=state,year=year,month=month,received_at=today(),rows=[r for r in day_rows(entries,state) if r.day.year==year and r.day.month==month],lang=lang,monthly=True)
    rendered(db,generated(db,user,folder+'/Monatsbericht.pdf',report,f'month-report:{year}-{month:02d}'))


def archive_dispatch(db,dispatch):
    user=db.get(User,dispatch.tf_user_id)
    db.scalar(select(User).where(User.id==user.id).with_for_update())
    match=re.fullmatch(r'Arbeitsbericht-(\d+)\.pdf',dispatch.filename) or re.fullmatch(r'\d{4}-\d{2}-\d{2}-\d+-(\d+)-Arbeitsbericht\.pdf',dispatch.filename)
    if match:
        report=db.get(DutyReport,int(match[1]))
        latest=db.scalar(select(ReportDispatch.id).where(ReportDispatch.tf_user_id==user.id,or_(ReportDispatch.filename==f'Arbeitsbericht-{int(match[1])}.pdf',ReportDispatch.filename.like(f'%-{int(match[1])}-Arbeitsbericht.pdf'))).order_by(ReportDispatch.id.desc()).limit(1))
        if report and report.tf_user_id==user.id and latest==dispatch.id and dispatch.filename==report_filename(report):
            generated(db,user,f'{report_folder(report)}/{dispatch.filename}',dispatch.pdf_data,f'work-report:{report.id}')
            entry=db.get(WorkEntry,report.entry_id)
            for year,month in touched_months(entry.entry_date,entry_end_date(entry)):archive_month(db,user,year,month)
    else:
        period=db.get(WorkMonth,dispatch.work_month_id)
        generated(db,user,f'{month_folder(period.year,period.month)}/Eingang-{dispatch.id}.pdf',dispatch.pdf_data,f'dispatch:{dispatch.id}')
        archive_month(db,user,period.year,period.month)


def backfill_documents(db):
    from ..user_directories import user_path
    from calendar import monthrange
    # Include months reached by overnight duties, even without a WorkMonth row there.
    for user in db.scalars(select(User).where(User.role=='tf')):
        db.scalar(select(User).where(User.id==user.id).with_for_update())
        root=user_path(user.username,user.role)
        for report in db.scalars(select(DutyReport).where(DutyReport.tf_user_id==user.id)):
            stored=db.scalar(select(DocumentFile).where(DocumentFile.owner_id==user.id,DocumentFile.source_key==f'work-report:{report.id}'))
            if stored:relocate(db,user,stored,f'{report_folder(report)}/{report_filename(report)}')
            if needs_render(db,stored) or not stored or not (stored.display_name==report_filename(report) or stored.display_name.startswith(report_filename(report)[:-4]+'-system-')) or not (root/stored.relative_path).is_file():archive_report(db,user,report,include_months=False)
        for stored in db.scalars(select(DocumentFile).where(DocumentFile.owner_id==user.id,DocumentFile.source_key.like('dispatch:%'))):
            dispatch=db.get(ReportDispatch,int(stored.source_key.split(':')[1]))
            if dispatch:
                period=db.get(WorkMonth,dispatch.work_month_id)
                if period:relocate(db,user,stored,f'{month_folder(period.year,period.month)}/Eingang-{dispatch.id}.pdf')
        periods={(m.year,m.month) for m in db.scalars(select(WorkMonth).where(WorkMonth.tf_user_id==user.id))}
        for source in db.scalars(select(DocumentFile.source_key).where(DocumentFile.owner_id==user.id)):
            match=re.fullmatch(r'month-(?:summary|report):(\d{4})-(\d{2})',source or '')
            if match and 1<=int(match[2])<=12:periods.add((int(match[1]),int(match[2])))
        entries=db.scalars(select(WorkEntry).join(WorkMonth).where(WorkMonth.tf_user_id==user.id)).all()
        for entry in entries:periods.update(touched_months(entry.entry_date,entry_end_date(entry)))
        for year,month in periods:
            row=db.scalar(select(DocumentFile).where(DocumentFile.owner_id==user.id,DocumentFile.source_key==f'month-summary:{year}-{month:02d}'))
            relevant=[e for e in entries if (year,month) in touched_months(e.entry_date,entry_end_date(e))]
            updated=max((e.updated_at for e in relevant),default=None)
            report=db.scalar(select(DocumentFile).where(DocumentFile.owner_id==user.id,DocumentFile.source_key==f'month-report:{year}-{month:02d}'))
            if row:relocate(db,user,row,month_folder(year,month)+'/Monatszusammenfassung.pdf')
            if report:relocate(db,user,report,month_folder(year,month)+'/Monatsbericht.pdf')
            if needs_render(db,row) or needs_render(db,report) or not row or not report or not (root/row.relative_path).is_file() or not (root/report.relative_path).is_file() or (updated and updated>row.updated_at):
                try:archive_month(db,user,year,month)
                except ValueError:
                    import logging
                    logging.getLogger(__name__).exception('Monatsarchiv enthält widersprüchliche Altdaten: Benutzer %s, %s-%s',user.id,year,month)
