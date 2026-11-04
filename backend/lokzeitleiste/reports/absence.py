"""Sick days credit eight hours; vacation credit follows the personnel plan."""
from ..localization import source as _text_source
from sqlalchemy import select
from sqlalchemy.orm import object_session
from ..models import PlanDay,PlanMonth,WorkMonth


def is_rest_day(db,user_id,day):
    return db.scalar(select(PlanDay.id).join(PlanMonth).where(PlanMonth.tf_user_id==user_id,PlanDay.day==day,PlanDay.kind==_text_source('server_reports_absence.text_e79aa42d7d18'))) is not None


def absence_minutes(entry):
    if entry.kind == _text_source("server_reports_absence.text_be1600b499c6"):
        return 480
    db=object_session(entry)
    period=db.get(WorkMonth,entry.work_month_id) if db and entry.work_month_id else None
    return 0 if period and is_rest_day(db,period.tf_user_id,entry.entry_date) else 480
