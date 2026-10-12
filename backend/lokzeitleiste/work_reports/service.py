import json
from datetime import datetime
from ..records.service import is_locked
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from ..models import User,WorkMonth,WorkEntry,WorkEntryAudit,DutyReport,DutyGuestTrip,RailwayStation
from ..reports.intervals import set_end_date
from ..worktime.service import validate_no_overlap
from .schemas import minutes,minimum_pause


def report_view(db,report):
    payload=json.loads(report.payload_json)
    entry=db.get(WorkEntry,report.entry_id)
    return dict(id=report.id,entry_id=report.entry_id,**payload,
                duration_minutes=minutes(datetime.fromisoformat(payload['start_at']),datetime.fromisoformat(payload['end_at'])),
                minimum_pause_minutes=minimum_pause(minutes(datetime.fromisoformat(payload['start_at']),datetime.fromisoformat(payload['end_at']))),
                locked=is_locked(db,entry.id))


def save_report(db,user,data):
    normalized=data.model_dump_json()
    db.scalar(select(User).where(User.id==user.id).with_for_update())
    existing=db.scalar(select(DutyReport).where(DutyReport.tf_user_id==user.id,DutyReport.client_id==str(data.client_id)))
    if existing:
        if existing.payload_json!=normalized:raise HTTPException(409,'Dieser Arbeitsbericht wurde bereits mit anderen Daten synchronisiert.')
        return existing
    for trip in data.trips:
        for code in (trip.start_station,trip.end_station):
            station=db.get(RailwayStation,code)
            if not station:raise HTTPException(422,'Unbekanntes DS100-Kürzel: '+code)
    duplicate=db.scalar(select(WorkEntry.id).join(WorkMonth).where(WorkMonth.tf_user_id==user.id,WorkEntry.client_id==str(data.client_id)))
    if duplicate:raise HTTPException(409,'Diese Erfassung ist bereits vorhanden.')
    period=db.scalar(select(WorkMonth).where(WorkMonth.tf_user_id==user.id,WorkMonth.year==data.start_at.year,WorkMonth.month==data.start_at.month))
    if not period:period=WorkMonth(tf_user_id=user.id,year=data.start_at.year,month=data.start_at.month);db.add(period);db.flush()
    entry=WorkEntry(work_month_id=period.id,client_id=str(data.client_id),kind='Sonstige Erfassung',entry_date=data.start_at.date(),
        start_time=data.start_at.strftime('%H:%M'),end_time=data.end_at.strftime('%H:%M'),pause_minutes=data.actual_pause,
        guest_minutes=sum(minutes(t.start_at,t.end_at) for t in data.trips),note=data.overrun_reason)
    db.add(entry);set_end_date(entry,data.end_at.date());db.flush()
    try:validate_no_overlap(db,user.id,entry)
    except ValueError as exc:db.rollback();raise HTTPException(409,str(exc)) from exc
    report=DutyReport(tf_user_id=user.id,entry_id=entry.id,client_id=str(data.client_id),payload_json=normalized);db.add(report);db.flush()
    for trip in data.trips:db.add(DutyGuestTrip(report_id=report.id,**trip.model_dump()))
    db.add(WorkEntryAudit(entry_id=entry.id,actor_id=user.id,action='work_report_created'))
    try:db.commit()
    except IntegrityError as exc:db.rollback();raise HTTPException(409,'Arbeitsbericht wurde inzwischen gespeichert. Bitte erneut laden.') from exc
    return report
