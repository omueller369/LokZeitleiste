from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from itertools import groupby
import json
from sqlalchemy import select
from sqlalchemy.orm import object_session
from ..models import DutyReport,DutyGuestTrip
from ..work_reports.schemas import train_pause_minutes

import holidays

from ..models import WorkEntry
from .intervals import interval, entry_end_date


WORK_KINDS = {"Bereitschaft", "Rufbereitschaft", "Ausfallschicht", "Zugfahrt", "Sonstige Erfassung"}


@dataclass(frozen=True)
class DayRow:
    day: date
    kind: str
    start: time
    end: time
    pause: int
    work: int
    guest: int
    sunday: int
    holiday: int
    night: int
    holiday_name: str = ""


def _minutes(a: datetime, b: datetime) -> int:
    return max(0, int((b - a).total_seconds() // 60))


def _overlap(a: datetime, b: datetime, c: datetime, d: datetime) -> int:
    return _minutes(max(a, c), min(b, d))


def _reported_segments(entries):
    """Use real guest intervals while the submitted work entry remains unchanged.

    Pauses are documentation only and never reduce work or premium minutes.
    Original submitted trips remain immutable after admin edits.
    """
    db=object_session(entries[0]) if entries else None
    if not db:return {}
    by_id={e.id:e for e in entries if e.id is not None}
    reports=db.scalars(select(DutyReport).where(DutyReport.entry_id.in_(by_id))).all()
    guests={}
    for trip in db.scalars(select(DutyGuestTrip).where(DutyGuestTrip.report_id.in_([r.id for r in reports]))):
        guests.setdefault(trip.report_id,[]).append((trip.start_at,trip.end_at))
    result={}
    for report in reports:
        entry=by_id[report.entry_id];payload=json.loads(report.payload_json)
        begin,end=interval(entry);trips=sorted((max(begin,a),min(end,b)) for a,b in guests.get(report.id,[]) if max(begin,a)<min(end,b))
        if (begin.isoformat()!=payload['start_at'] or end.isoformat()!=payload['end_at'] or entry.pause_minutes!=payload['actual_pause']+train_pause_minutes(payload.get('train_journeys',[]))
            or entry.guest_minutes!=sum(_minutes(a,b) for a,b in trips)):continue
        result[entry.id]=([(begin,end)],trips)
    return result


def day_rows(entries: list[WorkEntry], federal_state: str) -> list[DayRow]:
    if not entries:
        return []
    years = {entry.entry_date.year for entry in entries}
    years.update(y for entry in entries for y in range(entry.entry_date.year,entry_end_date(entry).year+1))
    public_holidays = holidays.country_holidays("DE", subdiv=federal_state, years=years, language="de")
    result = []
    reported=_reported_segments(entries)
    for entry in sorted(entries, key=lambda e: (e.entry_date, e.start_time, e.client_id)):
        begin, finish = interval(entry)
        is_work = entry.kind in WORK_KINDS
        pause = entry.pause_minutes if is_work else 0
        active_end = finish if is_work else begin
        pause_begin = max(begin, finish-timedelta(minutes=pause))
        guest_end = min(active_end, begin + timedelta(minutes=entry.guest_minutes)) if is_work else begin
        day = begin.date()
        while datetime.combine(day, time.min) < finish:
            day_start = datetime.combine(day, time.min)
            day_end = day_start + timedelta(days=1)
            raw_begin, raw_end = max(begin, day_start), min(finish, day_end)
            work = _overlap(begin, active_end, day_start, day_end) if is_work else 0
            night = (
                _overlap(begin, active_end, day_start, day_start + timedelta(hours=6))
                + _overlap(begin, active_end, day_start + timedelta(hours=22), day_end)
            ) if is_work else 0
            allocated_pause=_overlap(pause_begin,finish,day_start,day_end) if is_work else 0
            if entry.id in reported and is_work:
                work_segments,guest_segments=reported[entry.id]
                work=sum(_overlap(a,b,day_start,day_end) for a,b in work_segments)
                guest=sum(_overlap(a,b,day_start,day_end) for a,b in guest_segments)
                night=sum(_overlap(a,b,day_start,day_start+timedelta(hours=6))+_overlap(a,b,day_start+timedelta(hours=22),day_end) for a,b in work_segments)
            else:
                guest=_overlap(begin,guest_end,day_start,day_end) if is_work else 0
            name = public_holidays.get(day, "")
            result.append(DayRow(
                day=day, kind=entry.kind, start=raw_begin.time(), end=raw_end.time(),
                pause=allocated_pause,
                work=work,
                guest=guest,
                sunday=work if day.weekday() == 6 else 0,
                holiday=work if name else 0,
                night=night, holiday_name=name,
            ))
            day += timedelta(days=1)
    return sorted(result, key=lambda r: (r.day, r.start, r.kind))


def totals(rows: list[DayRow]) -> dict[str, int]:
    return {key: sum(getattr(row, key) for row in rows)
            for key in ("pause", "work", "guest", "sunday", "holiday", "night")}


def grouped_days(rows: list[DayRow]):
    for day, group in groupby(rows, key=lambda r: r.day):
        yield day, list(group)
