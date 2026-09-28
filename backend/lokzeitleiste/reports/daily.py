from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from itertools import groupby

import holidays

from ..models import WorkEntry


WORK_KINDS = {"Bereitschaft", "Zugfahrt", "Sonstige Erfassung"}


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


def day_rows(entries: list[WorkEntry], federal_state: str) -> list[DayRow]:
    if not entries:
        return []
    years = {entry.entry_date.year for entry in entries}
    years.update(entry.entry_date.year + 1 for entry in entries)
    public_holidays = holidays.country_holidays("DE", subdiv=federal_state, years=years, language="de")
    result = []
    for entry in sorted(entries, key=lambda e: (e.entry_date, e.start_time, e.client_id)):
        begin = datetime.combine(entry.entry_date, time.fromisoformat(entry.start_time))
        finish = datetime.combine(entry.entry_date, time.fromisoformat(entry.end_time))
        if finish <= begin:
            finish += timedelta(days=1)
        is_work = entry.kind in WORK_KINDS
        pause = entry.pause_minutes if is_work else 0
        active_end = max(begin, finish - timedelta(minutes=pause)) if is_work else begin
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
            name = public_holidays.get(day, "")
            result.append(DayRow(
                day=day, kind=entry.kind, start=raw_begin.time(), end=raw_end.time(),
                pause=_overlap(active_end, finish, day_start, day_end) if is_work else 0,
                work=work,
                guest=_overlap(begin, guest_end, day_start, day_end) if is_work else 0,
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
