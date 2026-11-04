from ..localization import source as _text_source
import calendar
from datetime import date
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import PlanChange, PlanDay, PlanMonth, PlanDuty, PlanDutyAudit
from .duties import duty_info, resolve_shift, driver_type
from .schemas import DayInput
from .holidays import holiday_info

KINDS = (_text_source('server_planning_service.text_eb8f579b6931'), _text_source('server_planning_service.text_35d3a889824d'), _text_source('server_planning_service.text_e79aa42d7d18'), _text_source('server_planning_service.text_52e37a639da5'))


class RevisionConflict(ValueError):
    pass


def get_month(db: Session, tf_id: int, year: int, month: int) -> dict:
    period = db.scalar(select(PlanMonth).where(PlanMonth.tf_user_id == tf_id,
                       PlanMonth.year == year, PlanMonth.month == month))
    stored = {d.day.day: d for d in period.days} if period else {}
    duties={d.day:d.shift for d in db.scalars(select(PlanDuty).where(PlanDuty.tf_user_id==tf_id,PlanDuty.day>=date(year,month,1),PlanDuty.day<=date(year,month,calendar.monthrange(year,month)[1])))}
    from ..accounts.tf_profiles import daily_minutes, weekly_minutes, monthly_minutes
    standard_minutes=daily_minutes(db,tf_id)
    days = []
    for number in range(1, calendar.monthrange(year, month)[1] + 1):
        item = stored.get(number)
        kind = item.kind if item else _text_source('server_planning_service.text_52e37a639da5')
        day=date(year,month,number)
        info=holiday_info(day)
        days.append({"date": day.isoformat(), "kind": kind, **info,
                     "note": item.note if item else "", **duty_info(day,kind,duties.get(day,"standard"),info["is_holiday"],standard_minutes)})
    from ..reports.intervals import period_entries
    from ..reports.daily import day_rows
    from ..models import TfProfile
    profile=db.get(TfProfile,tf_id)
    actual={}
    for row in day_rows(period_entries(db,tf_id,date(year,month,1),date(year,month,len(days))),profile.federal_state or 'BE' if profile else 'BE'):
        actual[row.day.isoformat()]=actual.get(row.day.isoformat(),0)+row.work
    for item in days:item['performed_minutes']=actual.get(item['date'],0)
    counts = {kind: sum(d["kind"] == kind and not d["is_holiday"] for d in days) for kind in KINDS}
    return {"year": year, "month": month,"weekly_minutes":weekly_minutes(db,tf_id),"contract_monthly_minutes":monthly_minutes(db,tf_id,year,month),"driver_type":driver_type(db,tf_id), "revision": period.revision if period else 0,
            "days": days, "holiday_days":sum(d["is_holiday"] for d in days), "holiday_state":"BE", "work_days": counts[_text_source('server_planning_service.text_eb8f579b6931')], "vacation_days": counts[_text_source('server_planning_service.text_35d3a889824d')],
            "rest_days": counts[_text_source('server_planning_service.text_e79aa42d7d18')], "unplanned_days": counts[_text_source('server_planning_service.text_52e37a639da5')],
            "work_target_minutes": sum(d["target_minutes"] for d in days if d["kind"]==_text_source('server_planning_service.text_eb8f579b6931')),
            "vacation_minutes": counts[_text_source('server_planning_service.text_35d3a889824d')] * 480,
            "target_minutes": sum(d["target_minutes"] for d in days),
            "complete": counts[_text_source('server_planning_service.text_52e37a639da5')] == 0}


def get_year(db: Session, tf_id: int, year: int) -> dict:
    months = [get_month(db, tf_id, year, m) for m in range(1, 13)]
    keys = ("holiday_days", "work_days", "vacation_days", "rest_days", "unplanned_days", "work_target_minutes", "vacation_minutes", "target_minutes")
    return {"year": year,"driver_type":driver_type(db,tf_id), "months": months, "totals": {key: sum(m[key] for m in months) for key in keys},
            "complete": all(m["complete"] for m in months)}


def apply_days(db: Session, *, tf_id: int, year: int, days: list[DayInput],
               revisions: dict[int, int], admin_id: int, source: str):
    if any(d.date.year != year for d in days):
        raise ValueError(_text_source('server_planning_service.text_defe74489865'))
    groups = {}
    for item in days:
        groups.setdefault(item.date.month, []).append(item)
    periods = {}
    # Alle Revisionen vor der ersten Änderung prüfen; Import ist atomar.
    for month in sorted(groups):
        period = db.scalar(select(PlanMonth).where(PlanMonth.tf_user_id == tf_id,
                            PlanMonth.year == year, PlanMonth.month == month).with_for_update())
        revision = period.revision if period else 0
        if revisions.get(month) != revision:
            raise RevisionConflict(f"{_text_source('server_planning_service.text_af56fe657b85')}{month:02d}/{year}{_text_source('server_planning_service.text_180d7ca7b864')}")
        periods[month] = period
    changes = 0
    tf_type=driver_type(db,tf_id)
    for month in sorted(groups):
        period = periods[month]
        if period is None:
            period = PlanMonth(tf_user_id=tf_id, year=year, month=month, revision=0)
            db.add(period)
            db.flush()
        stored = {d.day: d for d in period.days}
        changed = False
        for item in groups[month]:
            old = stored.get(item.date)
            old_kind, old_note = (old.kind, old.note) if old else (_text_source('server_planning_service.text_52e37a639da5'), "")
            note = item.note.strip() if item.kind != _text_source('server_planning_service.text_52e37a639da5') else ""
            duty=db.get(PlanDuty,(tf_id,item.date));old_shift=duty.shift if duty else "standard"
            shift=resolve_shift(db,tf_id,item.kind,item.shift,old_shift,old_kind,known_driver_type=tf_type)
            if (old_kind, old_note,old_shift) == (item.kind, note,shift):
                continue
            change=PlanChange(tf_user_id=tf_id, admin_user_id=admin_id, day=item.date,
                              previous_kind=old_kind, new_kind=item.kind, previous_note=old_note,
                              new_note=note, source=source)
            db.add(change);db.flush()
            db.add(PlanDutyAudit(change_id=change.id,previous_shift=old_shift,new_shift=shift))
            if shift=="standard":
                if duty:db.delete(duty)
            elif duty:duty.shift=shift
            else:db.add(PlanDuty(tf_user_id=tf_id,day=item.date,shift=shift))
            if item.kind == _text_source('server_planning_service.text_52e37a639da5'):
                if old:
                    db.delete(old)
            elif old:
                old.kind, old.note = item.kind, note
            else:
                db.add(PlanDay(plan_month_id=period.id, day=item.date, kind=item.kind, note=note))
            changes += 1
            changed = True
        if changed:
            period.revision += 1
    db.flush()
    return changes
