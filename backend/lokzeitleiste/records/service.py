from datetime import date, timedelta
from fastapi import HTTPException
from sqlalchemy import select
from ..models import TfProfile, WorkEntry, WorkEntryLock, WorkMonth, WorkTimeChange
from ..reports.monthly import summarize_month
from ..worktime.service import overview


def is_locked(db,entry_id):
    item = db.get(WorkEntryLock,entry_id)
    return bool(item and item.locked)


def assert_unlocked(db,entry_id):
    item=db.scalar(select(WorkEntryLock).where(WorkEntryLock.entry_id==entry_id).with_for_update())
    if item and item.locked:
        raise HTTPException(409,'Der Arbeitszeitdatensatz ist gesperrt und kann nicht geändert werden.')


def entry_view(db,entry,entry_dict):
    lock = db.get(WorkEntryLock,entry.id)
    return dict(entry_dict(entry),id=entry.id,updated_at=entry.updated_at.isoformat(),
                locked=bool(lock and lock.locked),lock_reason=lock.reason if lock and lock.locked else '',
                administratively_corrected=db.scalar(select(WorkTimeChange.id).where(WorkTimeChange.entry_id==entry.id).limit(1)) is not None)


def user_overview(db,user,year,month,entry_dict,month_summary, *, lock=False):
    if not 2000 <= year <= 2100 or not 1 <= month <= 12:
        raise HTTPException(422,'Ungültiger Monat')
    profile = db.get(TfProfile,user.id) if user.role == 'tf' else None
    if user.role == 'tf' and (not profile or not profile.federal_state):
        raise HTTPException(409,'Bundesland des Tf fehlt')
    state = profile.federal_state if profile else None
    try:
        data = overview(db,user.id,year,month,state,lock=lock)
        if profile:
            summary = month_summary(db,user.id,year,month)
        else:
            first=date(year,month,1)
            following=date(year+1,1,1) if month==12 else date(year,month+1,1)
            query=select(WorkEntry).join(WorkMonth).where(WorkMonth.tf_user_id==user.id,
                WorkEntry.entry_date>=first-timedelta(days=1),WorkEntry.entry_date<following)
            if lock:query=query.with_for_update()
            entries=list(db.scalars(query).all())
            summary = summarize_month(entries,year=year,month=month,federal_state=None)
            summary.update(target_minutes=None,balance_minutes=None,planning=None)
    except ValueError as exc:
        raise HTTPException(409,str(exc)) from exc
    period = db.scalar(select(WorkMonth).where(WorkMonth.tf_user_id==user.id,WorkMonth.year==year,WorkMonth.month==month))
    data.update(month=summary,role=user.role,entries=[entry_view(db,e,entry_dict) for e in sorted(
        period.entries,key=lambda e:(e.entry_date,e.start_time,e.id))] if period else [])
    return data
