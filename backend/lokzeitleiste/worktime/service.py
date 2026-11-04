"""Arbeitszeitkorrekturen, Kalenderwochen und dauerhafte E-Mail-Aufträge."""
from ..localization import source as _text_source
import calendar
import logging
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import engine
from ..models import WorkEntry, WorkMonth, WorkTimeChange, now_utc
from ..reports.monthly import summarize_month
from ..reports.daily import WORK_KINDS
from ..reports.intervals import interval, period_entries
from ..reports.mailer import send_time_change
from ..reports.service import MAX_ATTEMPTS

log = logging.getLogger(__name__)
FIELDS = ("work_without_guest", "guest", "topup", "vacation", "sick", "credited", "sunday", "holiday", "night")


def validate_no_overlap(db, tf_id, entry):
    begin, end = interval(entry)
    others=[e for e in period_entries(db,tf_id,begin.date(),end.date(),lock=True)
            if e.id!=entry.id and e.kind in WORK_KINDS]
    for other in others:
        other_begin, other_end = interval(other)
        if begin < other_end and other_begin < end:
            raise ValueError(_text_source('server_worktime_service.text_82f3fadb4c78'))


def overview(db, tf_id, year, month, state, *, lock=False):
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    begin = first - timedelta(days=first.weekday())
    end = last + timedelta(days=6 - last.weekday())
    # Den Vortag einbeziehen: Schichten dürfen über Mitternacht reichen.
    entries=period_entries(db,tf_id,begin,end,lock=lock)
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
    lines = [f"{_text_source('server_worktime_service.text_64837f4186a2')}{profile.first_name} {profile.last_name},", "",
             f"{_text_source('server_worktime_service.text_1209a630cbb4')}{entry.entry_date:%d.%m.%Y} ({entry.kind}{_text_source('server_worktime_service.text_d82ede17f3a1')}",
             f"{_text_source('server_worktime_service.text_239bd0a9f785')}{old_start} → {entry.start_time}",
             f"{_text_source('server_worktime_service.text_4efcfc7b4bd5')}{old_end} → {entry.end_time}",
             f"{_text_source('server_worktime_service.text_75031d29a279')}{entry.pause_minutes}{_text_source('server_worktime_service.text_78d0e952adb5')}", f"{_text_source('server_worktime_service.text_8446867dbbc4')}{reason}", "",
             _text_source('server_worktime_service.text_715ca508b0ea')]
    previous_days = {d["date"]: d for data in before.values() for d in data["days"]}
    new_days = {d["date"]: d for data in after.values() for d in data["days"]}
    for key in sorted(previous_days.keys() | new_days.keys()):
        old, new = previous_days.get(key, {}), new_days.get(key, {})
        if old != new:
            lines.append(f"{_text_source('server_worktime_service.text_e1639a9be519')}{key}{_text_source('server_worktime_service.text_42205887883e')}{clock(old.get('work', 0))} → {clock(new.get('work', 0))}{_text_source('server_worktime_service.text_d3941960a4b5')}{clock(old.get('credited', 0))} → {clock(new.get('credited', 0))}")
    old_weeks = {(w["iso_year"], w["week"]): w for data in before.values() for w in data["weeks"]}
    new_weeks = {(w["iso_year"], w["week"]): w for data in after.values() for w in data["weeks"]}
    for key, new in sorted(new_weeks.items()):
        old = old_weeks[key]
        if old["totals"] != new["totals"]:
            lines.append(f"KW {key[1]}/{key[0]} ({new['start']}{_text_source('server_worktime_service.text_cffcbd9e175f')}{new['end']}{_text_source('server_worktime_service.text_69e49921fb80')}{clock(old['totals']['work'])} → {clock(new['totals']['work'])}{_text_source('server_worktime_service.text_d3941960a4b5')}{clock(old['totals']['credited'])} → {clock(new['totals']['credited'])}")
    for key, data in sorted(after.items()):
        old = before[key]
        for label, field in ((_text_source('server_worktime_service.text_b574d367e922'), "work"), (_text_source('server_worktime_service.text_a2791bb9b7dc'), "credited")):
            lines.append(f"{_text_source('server_worktime_service.text_c8a7a86d527a')}{key[1]:02d}/{key[0]} · {label}: {clock(sum((d[field] for d in old['days'])))} → {clock(sum((d[field] for d in data['days'])))}")
    lines += ["", _text_source('server_worktime_service.text_69a767809637'),
              _text_source('server_worktime_service.text_8c07d33e2d40'),
              _text_source('server_worktime_service.text_b3c984dc667a')]
    return "\n".join(lines)


def process_change(change_id):
    with Session(engine()) as db:
        item = db.scalar(select(WorkTimeChange).where(WorkTimeChange.id == change_id).with_for_update())
        if not item or item.status == "sent" or item.attempts >= MAX_ATTEMPTS:
            return
        try:
            from ..i18n import translate, user_language
            lang=user_language(db,item.tf_user_id)
            send_time_change(recipient=item.recipient_email, body=translate(item.email_body,lang),lang=lang)
        except Exception as exc:
            item.status = "failed"
            item.last_error = str(exc)[:500]
            log.exception(_text_source('server_worktime_service.text_e2f616498c72'), change_id)
        else:
            item.status = "sent"
            item.sent_at = now_utc()
            item.last_error = ""
        item.attempts += 1
        db.commit()
