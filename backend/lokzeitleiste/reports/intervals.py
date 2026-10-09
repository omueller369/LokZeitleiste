"""Explizite Enddaten mit kompatibler Mitternachtsregel für alte Einträge."""
from datetime import datetime, time, timedelta
from sqlalchemy import select, or_
from ..models import WorkEntry, WorkEntryDates, WorkMonth


def entry_end_date(entry):
    explicit=entry.explicit_end_date
    if explicit is not None:return explicit
    return entry.entry_date+timedelta(days=1) if entry.end_time<=entry.start_time else entry.entry_date


def interval(entry):
    return (datetime.combine(entry.entry_date,time.fromisoformat(entry.start_time)),
            datetime.combine(entry_end_date(entry),time.fromisoformat(entry.end_time)))


def set_end_date(entry,value):
    if value is None:entry.date_override=None
    elif entry.date_override:entry.date_override.end_date=value
    else:entry.date_override=WorkEntryDates(end_date=value)


def period_entries(db,user_id,start,end,*,lock=False):
    query=select(WorkEntry).join(WorkMonth).outerjoin(WorkEntryDates).where(
        WorkMonth.tf_user_id==user_id,WorkEntry.entry_date<=end,
        or_(WorkEntry.entry_date>=start-timedelta(days=1),WorkEntryDates.end_date>=start))
    if lock:query=query.with_for_update()
    return list(db.scalars(query).all())


def touched_months(start,end):
    cursor=start.replace(day=1);last=end.replace(day=1);result=set()
    while cursor<=last:
        result.add((cursor.year,cursor.month))
        if cursor.year==2100 and cursor.month==12:break
        cursor=cursor.replace(year=cursor.year+1,month=1) if cursor.month==12 else cursor.replace(month=cursor.month+1)
    return result
