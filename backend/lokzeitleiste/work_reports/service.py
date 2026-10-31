import json
from datetime import datetime,time,timedelta
from ..records.service import is_locked,assert_unlocked
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from ..models import User,WorkMonth,WorkEntry,WorkEntryAudit,DutyReport,DutyGuestTrip,RailwayStation,now_utc
from ..reports.intervals import set_end_date,period_entries,interval
from ..reports.absence import is_rest_day
from ..reports.daily import WORK_KINDS
from ..worktime.service import validate_no_overlap
from .schemas import minutes,minimum_pause,required_pause,ReportIn,train_pause_minutes


def report_view(db,report):
    payload=json.loads(report.payload_json)
    for trip in payload['trips']:
        trip.setdefault('self_payer',False)
        for field,name in (('start_station','start_station_name'),('end_station','end_station_name')):
            if name not in trip:
                station=db.get(RailwayStation,trip[field]);trip[name]=station.name if station else ''
    start=datetime.fromisoformat(payload['start_at']);end=datetime.fromisoformat(payload['end_at'])
    guest_total=sum(minutes(datetime.fromisoformat(t['start_at']),datetime.fromisoformat(t['end_at'])) for t in payload['trips'])
    guest_inside=sum(max(0,minutes(max(start,datetime.fromisoformat(t['start_at'])),min(end,datetime.fromisoformat(t['end_at'])))) for t in payload['trips'])
    payload.setdefault('train_journeys',[])
    payload.setdefault('ausbleibe',[])
    payload.setdefault('kind','Sonstige Erfassung')
    payload.setdefault('in_hotel',False);payload.setdefault('hotel_name','');payload.setdefault('hotel_location','');payload.setdefault('pause_policy',1)
    rest=is_rest_day(db,report.tf_user_id,start.date()) if payload['kind'] in ('Urlaub','Krank') else False
    credit=(0 if rest else 480) if payload['kind'] in ('Urlaub','Krank') else minutes(start,end)
    revision=payload.pop('_train_revision',0)
    payload.pop('_pdf_version_offset',None)
    entry=db.get(WorkEntry,report.entry_id)
    return dict(id=report.id,entry_id=report.entry_id,**payload,
                duration_minutes=minutes(datetime.fromisoformat(payload['start_at']),datetime.fromisoformat(payload['end_at'])),
                minimum_pause_minutes=minimum_pause(minutes(start,end)) if payload['kind']=='Sonstige Erfassung' else 0,
                required_pause_minutes=required_pause(minutes(start,end)) if payload['kind']=='Sonstige Erfassung' else 0,
                credited_minutes=credit,is_rest_day=rest,
                train_editable=not is_locked(db,entry.id) and interval(entry)==(start,end) and entry.pause_minutes==payload['actual_pause']+train_pause_minutes(payload['train_journeys']),
                train_revision=revision,documented_pause_minutes=payload['actual_pause']+train_pause_minutes(payload['train_journeys']),
                guest_total_minutes=guest_total,guest_minutes=guest_inside,external_guest_minutes=guest_total-guest_inside,
                locked=is_locked(db,entry.id))


def save_report(db,user,data,commit=True):
    from ..app_defaults import ensure_defaults
    ensure_defaults(db)
    db.scalar(select(User).where(User.id==user.id).with_for_update())
    existing=db.scalar(select(DutyReport).where(DutyReport.tf_user_id==user.id,DutyReport.client_id==str(data.client_id)))
    if existing:
        # Historical reports have no station names. Compare the actual duty/trip data;
        # keep the original station-name snapshot on retries and catalog changes.
        def identity(payload):
            payload.setdefault('ausbleibe',[])
            payload.setdefault('kind','Sonstige Erfassung')
            payload.setdefault('in_hotel',False);payload.setdefault('hotel_name','');payload.setdefault('hotel_location','');payload.setdefault('pause_policy',1)
            payload.pop('train_journeys',None);payload.pop('_train_revision',None);payload.pop('_pdf_version_offset',None)
            for trip in payload['trips']:
                trip.setdefault('self_payer',False)
                trip.pop('start_station_name',None);trip.pop('end_station_name',None)
            return payload
        if identity(json.loads(existing.payload_json))!=identity(json.loads(data.model_dump_json())):
            raise HTTPException(409,'Dieser Arbeitsbericht wurde bereits mit anderen Daten synchronisiert.')
        return existing
    for trip in data.trips:
        for code,name_field in ((trip.start_station,'start_station_name'),(trip.end_station,'end_station_name')):
            station=db.get(RailwayStation,code)
            if not station:raise HTTPException(422,'Unbekanntes DS100-Kürzel: '+code)
            setattr(trip,name_field,station.name)
    from ..app_defaults import use_journeys
    use_journeys(db,data.train_journeys)
    resolve_train_stations(db,data.train_journeys)
    normalized=data.model_dump_json()
    if len(normalized.encode('utf-8'))>60000:raise HTTPException(422,'Arbeitsbericht enthält zu viele Zugfahrtdaten.')
    # An absence occupies a calendar day, regardless of the display times.
    first=data.start_at.date();last=(data.end_at-timedelta(minutes=1)).date()
    for other in period_entries(db,user.id,first,last,lock=True):
        begin,end=interval(other)
        if other.kind in ('Urlaub','Krank') or data.kind in ('Urlaub','Krank'):
            if begin<datetime.combine(last+timedelta(days=1),time.min) and end>datetime.combine(first,time.min) and other.kind in WORK_KINDS|{'Urlaub','Krank'}:
                raise HTTPException(409,'Für diesen Tag besteht bereits eine Arbeitszeit oder Abwesenheit.')
    duplicate=db.scalar(select(WorkEntry.id).join(WorkMonth).where(WorkMonth.tf_user_id==user.id,WorkEntry.client_id==str(data.client_id)))
    if duplicate:raise HTTPException(409,'Diese Erfassung ist bereits vorhanden.')
    period=db.scalar(select(WorkMonth).where(WorkMonth.tf_user_id==user.id,WorkMonth.year==data.start_at.year,WorkMonth.month==data.start_at.month))
    if not period:period=WorkMonth(tf_user_id=user.id,year=data.start_at.year,month=data.start_at.month);db.add(period);db.flush()
    entry=WorkEntry(work_month_id=period.id,client_id=str(data.client_id),kind=data.kind,entry_date=data.start_at.date(),
        start_time=data.start_at.strftime('%H:%M'),end_time=data.end_at.strftime('%H:%M'),pause_minutes=data.actual_pause+train_pause_minutes(json.loads(normalized)['train_journeys']),
        guest_minutes=sum(max(0,minutes(max(t.start_at,data.start_at),min(t.end_at,data.end_at))) for t in data.trips),note=data.overrun_reason)
    db.add(entry);set_end_date(entry,data.end_at.date());db.flush()
    try:validate_no_overlap(db,user.id,entry)
    except ValueError as exc:db.rollback();raise HTTPException(409,str(exc)) from exc
    report=DutyReport(tf_user_id=user.id,entry_id=entry.id,client_id=str(data.client_id),payload_json=normalized);db.add(report);db.flush()
    for trip in data.trips:db.add(DutyGuestTrip(report_id=report.id,**trip.model_dump(exclude={'start_station_name','end_station_name','self_payer'})))
    db.add(WorkEntryAudit(entry_id=entry.id,actor_id=user.id,action='work_report_created'))
    from ..documents.archive import archive_report
    archive_report(db,user,report,queue_email=True)
    try:
        if commit:db.commit()
        else:db.flush()
    except IntegrityError as exc:db.rollback();raise HTTPException(409,'Arbeitsbericht wurde inzwischen gespeichert. Bitte erneut laden.') from exc
    return report


def resolve_train_stations(db,journeys):
    for train in journeys:
        for code,attribute in ((train.start_station,'start_station_name'),(train.end_station,'end_station_name')):
            station=db.get(RailwayStation,code)
            if not station:raise HTTPException(422,'Unbekanntes DS100-Kürzel: '+code)
            setattr(train,attribute,station.name)
        for event in train.events:
            if not event.station:
                continue
            station=db.get(RailwayStation,event.station)
            if not station:raise HTTPException(422,'Unbekanntes DS100-Kürzel: '+event.station)
            event.station_name=station.name


def update_train_journeys(db,user,report,changes):
    assert_unlocked(db,report.entry_id)
    payload=json.loads(report.payload_json)
    current=payload.get('train_journeys',[]);revision=payload.get('_train_revision',0)
    data=ReportIn.model_validate(dict(payload,train_journeys=[t.model_dump(mode='json') for t in changes.train_journeys]))
    from ..app_defaults import use_journeys
    use_journeys(db,data.train_journeys,current)
    resolve_train_stations(db,data.train_journeys)
    trains=[t.model_dump(mode='json') for t in data.train_journeys]
    if trains==current:return report
    if changes.expected_revision!=revision:raise HTTPException(409,'Zugfahrten wurden inzwischen geändert. Bitte erneut laden.')
    entry=db.scalar(select(WorkEntry).where(WorkEntry.id==report.entry_id).with_for_update())
    begin,end=interval(entry)
    if begin.isoformat()!=payload['start_at'] or end.isoformat()!=payload['end_at'] or entry.pause_minutes!=payload['actual_pause']+train_pause_minutes(current):
        raise HTTPException(409,'Arbeitszeit wurde administrativ geändert. Zugfahrten können nicht mehr geändert werden.')
    payload['train_journeys']=trains;payload['_train_revision']=revision+1
    encoded=json.dumps(payload,ensure_ascii=False)
    if len(encoded.encode('utf-8'))>60000:raise HTTPException(422,'Arbeitsbericht enthält zu viele Zugfahrtdaten.')
    report.payload_json=encoded
    entry.updated_at=now_utc()
    entry.pause_minutes=payload['actual_pause']+train_pause_minutes(trains)
    db.add(WorkEntryAudit(entry_id=entry.id,actor_id=user.id,action='work_report_trains_updated'))
    from ..documents.archive import archive_report
    archive_report(db,user,report,queue_email=True)
    db.commit()
    return report
