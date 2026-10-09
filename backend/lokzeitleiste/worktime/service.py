"""Arbeitszeitkorrekturen, Kalenderwochen und dauerhafte E-Mail-Aufträge."""
import calendar
import logging
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import engine
from ..models import WorkEntry, WorkMonth, WorkTimeChange, now_utc
from ..reports.monthly import summarize_month
from ..reports.daily import WORK_KINDS
from ..reports.mailer import send_time_change
from ..reports.service import MAX_ATTEMPTS

log = logging.getLogger(__name__)
FIELDS = ("work_without_guest", "guest", "topup", "vacation", "sick", "credited", "sunday", "holiday", "night")


def validate_no_overlap(db, tf_id, entry):
    def interval(item):
        begin = datetime.combine(item.entry_date, time.fromisoformat(item.start_time))
        end = datetime.combine(item.entry_date, time.fromisoformat(item.end_time))
        return begin, end + timedelta(days=1) if end <= begin else end
    begin, end = interval(entry)
    others = db.scalars(select(WorkEntry).join(WorkMonth).where(
        WorkMonth.tf_user_id == tf_id, WorkEntry.id != entry.id, WorkEntry.kind.in_(WORK_KINDS),
        WorkEntry.entry_date >= entry.entry_date - timedelta(days=1),
        WorkEntry.entry_date <= entry.entry_date + timedelta(days=1)).with_for_update()).all()
    for other in others:
        other_begin, other_end = interval(other)
        if begin < other_end and other_begin < end:
            raise ValueError("Der korrigierte Zeitraum überschneidet sich mit einer anderen Arbeitszeit.")


def overview(db, tf_id, year, month, state, *, lock=False):
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    begin = first - timedelta(days=first.weekday())
    end = last + timedelta(days=6 - last.weekday())
    # Den Vortag einbeziehen: Schichten dürfen über Mitternacht reichen.
    query = select(WorkEntry).join(WorkMonth).where(
        WorkMonth.tf_user_id == tf_id, WorkEntry.entry_date >= begin - timedelta(days=1),
        WorkEntry.entry_date <= end)
    # Korrekturen brauchen unter MySQL einen aktuellen Locking Read statt eines alten Snapshots.
    if lock:
        query = query.with_for_update()
    entries = list(db.scalars(query).all())
    days = []
    cursor = date((begin - timedelta(days=1)).year, (begin - timedelta(days=1)).month, 1)
    while cursor <= end:
        days.extend(summarize_month(entries, year=cursor.year, month=cursor.month, federal_state=state)["days"])
        cursor = date(cursor.year + 1, 1, 1) if cursor.month == 12 else date(cursor.year, cursor.month + 1, 1)
    by_date = {day["date"]: dict(day, work=day["work_without_guest"] + day["guest"]) for day in days}
    weeks = []
    cursor = begin
    while cursor <= end:
        week_end = cursor + timedelta(days=6)
        selected = [d for key, d in by_date.items() if cursor.isoformat() <= key <= week_end.isoformat()]
        iso = cursor.isocalendar()
        sums = {field: sum(d[field] for d in selected) for field in (*FIELDS, "work")}
        weeks.append({"iso_year": iso.year, "week": iso.week, "start": cursor.isoformat(),
                      "end": week_end.isoformat(), "totals": sums})
        cursor += timedelta(days=7)
    return {"days": [by_date[key] for key in sorted(by_date) if first.isoformat() <= key <= last.isoformat()],
            "weeks": weeks}


def clock(minutes):
    return f"{minutes // 60}:{minutes % 60:02d} h"


def change_body(profile, entry, old_start, old_end, reason, before, after):
    lines = [f"Guten Tag {profile.first_name} {profile.last_name},", "",
             f"Ihre Arbeitszeit am {entry.entry_date:%d.%m.%Y} ({entry.kind}) wurde administrativ angepasst.",
             f"Arbeitsbeginn: {old_start} → {entry.start_time}",
             f"Arbeitsende: {old_end} → {entry.end_time}",
             f"Pause unverändert: {entry.pause_minutes} Minuten", f"Grund: {reason}", "",
             "Neuberechnung (Vorher → Nachher):"]
    previous_days = {d["date"]: d for data in before.values() for d in data["days"]}
    new_days = {d["date"]: d for data in after.values() for d in data["days"]}
    for key in sorted(previous_days.keys() | new_days.keys()):
        old, new = previous_days.get(key, {}), new_days.get(key, {})
        if old != new:
            lines.append(f"Tag {key}: Arbeitszeit {clock(old.get('work', 0))} → {clock(new.get('work', 0))}; "
                         f"Gutschrift {clock(old.get('credited', 0))} → {clock(new.get('credited', 0))}")
    old_weeks = {(w["iso_year"], w["week"]): w for data in before.values() for w in data["weeks"]}
    new_weeks = {(w["iso_year"], w["week"]): w for data in after.values() for w in data["weeks"]}
    for key, new in sorted(new_weeks.items()):
        old = old_weeks[key]
        if old["totals"] != new["totals"]:
            lines.append(f"KW {key[1]}/{key[0]} ({new['start']} bis {new['end']}): "
                         f"Arbeitszeit {clock(old['totals']['work'])} → {clock(new['totals']['work'])}; "
                         f"Gutschrift {clock(old['totals']['credited'])} → {clock(new['totals']['credited'])}")
    for key, data in sorted(after.items()):
        old = before[key]
        for label, field in (("Arbeitszeit", "work"), ("Gutschrift", "credited")):
            lines.append(f"Monat {key[1]:02d}/{key[0]} · {label}: "
                         f"{clock(sum(d[field] for d in old['days']))} → {clock(sum(d[field] for d in data['days']))}")
    lines += ["", "Arbeitszeit enthält Gastfahrt und berücksichtigt Pausen. Die Gutschrift enthält die bestehende",
              "Auffüllung auf acht Stunden sowie Urlaub/Krank. Bei Nachtarbeit wird auf Kalendertage aufgeteilt.",
              "Alle Uhrzeiten sind lokale Zeiten wie in Ihrer Erfassung."]
    return "\n".join(lines)


def process_change(change_id):
    with Session(engine()) as db:
        item = db.scalar(select(WorkTimeChange).where(WorkTimeChange.id == change_id).with_for_update())
        if not item or item.status == "sent" or item.attempts >= MAX_ATTEMPTS:
            return
        try:
            send_time_change(recipient=item.recipient_email, body=item.email_body)
        except Exception as exc:
            item.status = "failed"
            item.last_error = str(exc)[:500]
            log.exception("Arbeitszeitbenachrichtigung fehlgeschlagen, Änderung %s", change_id)
        else:
            item.status = "sent"
            item.sent_at = now_utc()
            item.last_error = ""
        item.attempts += 1
        db.commit()
