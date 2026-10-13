"""Absence credit follows the current personnel plan; rest days have no credit."""
from sqlalchemy import select
from sqlalchemy.orm import object_session
from ..models import PlanDay,PlanMonth,WorkMonth


def is_rest_day(db,user_id,day):
    return db.scalar(select(PlanDay.id).join(PlanMonth).where(PlanMonth.tf_user_id==user_id,PlanDay.day==day,PlanDay.kind=='Ruhetag')) is not None


def absence_minutes(entry):
    db=object_session(entry)
    period=db.get(WorkMonth,entry.work_month_id) if db and entry.work_month_id else None
    return 0 if period and is_rest_day(db,period.tf_user_id,entry.entry_date) else 480
