import calendar
from datetime import date
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import PlanChange, PlanDay, PlanMonth
from .schemas import DayInput

KINDS = ("Arbeitstag", "Urlaub", "Ruhetag", "Ungeplant")


class RevisionConflict(ValueError):
    pass


def get_month(db: Session, tf_id: int, year: int, month: int) -> dict:
    period = db.scalar(select(PlanMonth).where(PlanMonth.tf_user_id == tf_id,
                       PlanMonth.year == year, PlanMonth.month == month))
    stored = {d.day.day: d for d in period.days} if period else {}
    days = []
    for number in range(1, calendar.monthrange(year, month)[1] + 1):
        item = stored.get(number)
        kind = item.kind if item else "Ungeplant"
        days.append({"date": date(year, month, number).isoformat(), "kind": kind,
                     "note": item.note if item else "", "target_minutes": 480 if kind in ("Arbeitstag", "Urlaub") else 0})
    counts = {kind: sum(d["kind"] == kind for d in days) for kind in KINDS}
    return {"year": year, "month": month, "revision": period.revision if period else 0,
            "days": days, "work_days": counts["Arbeitstag"], "vacation_days": counts["Urlaub"],
            "rest_days": counts["Ruhetag"], "unplanned_days": counts["Ungeplant"],
            "work_target_minutes": counts["Arbeitstag"] * 480,
            "vacation_minutes": counts["Urlaub"] * 480,
            "target_minutes": (counts["Arbeitstag"] + counts["Urlaub"]) * 480,
            "complete": counts["Ungeplant"] == 0}


def get_year(db: Session, tf_id: int, year: int) -> dict:
    months = [get_month(db, tf_id, year, m) for m in range(1, 13)]
    keys = ("work_days", "vacation_days", "rest_days", "unplanned_days", "work_target_minutes", "vacation_minutes", "target_minutes")
    return {"year": year, "months": months, "totals": {key: sum(m[key] for m in months) for key in keys},
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
            if (old_kind, old_note) == (item.kind, note):
                continue
            db.add(PlanChange(tf_user_id=tf_id, admin_user_id=admin_id, day=item.date,
                              previous_kind=old_kind, new_kind=item.kind, previous_note=old_note,
                              new_note=note, source=source))
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
