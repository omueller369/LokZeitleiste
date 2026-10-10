import calendar
from datetime import date
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import PlanChange, PlanDay, PlanMonth, PlanDuty, PlanDutyAudit
from .duties import duty_info, resolve_shift, driver_type
from .schemas import DayInput
from .holidays import holiday_info

KINDS = ("Arbeitstag", "Urlaub", "Ruhetag", "Ungeplant")


class RevisionConflict(ValueError):
    pass


def get_month(db: Session, tf_id: int, year: int, month: int) -> dict:
    period = db.scalar(select(PlanMonth).where(PlanMonth.tf_user_id == tf_id,
                       PlanMonth.year == year, PlanMonth.month == month))
    stored = {d.day.day: d for d in period.days} if period else {}
    duties={d.day:d.shift for d in db.scalars(select(PlanDuty).where(PlanDuty.tf_user_id==tf_id,PlanDuty.day>=date(year,month,1),PlanDuty.day<=date(year,month,calendar.monthrange(year,month)[1])))}
    days = []
    for number in range(1, calendar.monthrange(year, month)[1] + 1):
        item = stored.get(number)
        kind = item.kind if item else "Ungeplant"
        day=date(year,month,number)
        info=holiday_info(day)
        days.append({"date": day.isoformat(), "kind": kind, **info,
                     "note": item.note if item else "", **duty_info(day,kind,duties.get(day,"standard"),info["is_holiday"])})
    counts = {kind: sum(d["kind"] == kind and not d["is_holiday"] for d in days) for kind in KINDS}
    return {"year": year, "month": month,"driver_type":driver_type(db,tf_id), "revision": period.revision if period else 0,
            "days": days, "holiday_days":sum(d["is_holiday"] for d in days), "holiday_state":"BE", "work_days": counts["Arbeitstag"], "vacation_days": counts["Urlaub"],
            "rest_days": counts["Ruhetag"], "unplanned_days": counts["Ungeplant"],
            "work_target_minutes": sum(d["target_minutes"] for d in days if d["kind"]=="Arbeitstag"),
            "vacation_minutes": counts["Urlaub"] * 480,
            "target_minutes": sum(d["target_minutes"] for d in days),
            "complete": counts["Ungeplant"] == 0}


def get_year(db: Session, tf_id: int, year: int) -> dict:
    months = [get_month(db, tf_id, year, m) for m in range(1, 13)]
    keys = ("holiday_days", "work_days", "vacation_days", "rest_days", "unplanned_days", "work_target_minutes", "vacation_minutes", "target_minutes")
    return {"year": year,"driver_type":driver_type(db,tf_id), "months": months, "totals": {key: sum(m[key] for m in months) for key in keys},
            "complete": all(m["complete"] for m in months)}


def apply_days(db: Session, *, tf_id: int, year: int, days: list[DayInput],
               revisions: dict[int, int], admin_id: int, source: str):
    if any(d.date.year != year for d in days):
        raise ValueError("Alle Daten müssen zum gewählten Jahr gehören")
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
            raise RevisionConflict(f"Plan {month:02d}/{year} wurde inzwischen geändert. Bitte neu laden.")
        periods[month] = period
    changes = 0
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
            old_kind, old_note = (old.kind, old.note) if old else ("Ungeplant", "")
            note = item.note.strip() if item.kind != "Ungeplant" else ""
            duty=db.get(PlanDuty,(tf_id,item.date));old_shift=duty.shift if duty else "standard"
            shift=resolve_shift(db,tf_id,item.kind,item.shift,old_shift,old_kind)
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
            if item.kind == "Ungeplant":
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
