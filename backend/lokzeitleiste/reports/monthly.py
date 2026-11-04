"""Monatsübersicht in Minuten; Gastfahrt gehört zur geleisteten Zeit."""
from ..localization import source as _text_source

from dataclasses import asdict, dataclass
from datetime import date, timedelta

from ..models import WorkEntry
from .daily import day_rows, grouped_days, totals
from .absence import absence_minutes


@dataclass(frozen=True)
class MonthDay:
    date: str
    type: str
    work_without_guest: int
    guest: int
    guest_used_for_target: int
    topup: int
    vacation: int
    sick: int
    credited: int
    sunday: int
    holiday: int
    night: int


def summarize_month(entries: list[WorkEntry], *, year: int, month: int,
                    federal_state: str) -> dict:
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    split = [r for r in day_rows(entries, federal_state) if start <= r.day < end]
    by_day = {day: items for day, items in grouped_days(split)}
    absence = {}
    absence_credit = {}
    for entry in entries:
        if entry.kind in (_text_source('server_reports_monthly.text_35d3a889824d'), _text_source('server_reports_monthly.text_be1600b499c6')) and start <= entry.entry_date < end:
            absence.setdefault(entry.entry_date, set()).add(entry.kind)
            absence_credit[entry.entry_date]=max(absence_credit.get(entry.entry_date,0),absence_minutes(entry))
    result = []
    day = start
    while day < end:
        rows = by_day.get(day, [])
        sums = totals(rows)
        work = sums["work"]
        kinds = absence.get(day, set())
        if len(kinds) > 1 or (kinds and work):
            raise ValueError(f"{_text_source('server_reports_monthly.text_58cbe129eef2')}{day:%d.%m.%Y}")
        guest = sums["guest"]
        without_guest = work - guest
        used = min(guest, max(0, 480 - without_guest))
        topup = max(0, 480 - work) if work and any(r.kind in (_text_source('server_reports_monthly.text_52c5d4a0445b'),_text_source('server_reports_monthly.text_f31b8681bfca')) for r in rows) else 0
        vacation = absence_credit.get(day,480) if _text_source('server_reports_monthly.text_35d3a889824d') in kinds else 0
        sick = absence_credit.get(day,480) if _text_source('server_reports_monthly.text_be1600b499c6') in kinds else 0
        if work or kinds:
            kind = _text_source('server_reports_monthly.text_35d3a889824d') if _text_source('server_reports_monthly.text_35d3a889824d') in kinds else _text_source('server_reports_monthly.text_be1600b499c6') if _text_source('server_reports_monthly.text_be1600b499c6') in kinds else _text_source('server_reports_monthly.text_3f0828ad8bfa')
            result.append(MonthDay(day.isoformat(), kind, without_guest, guest, used,
                                   topup, vacation, sick, work + topup + vacation + sick,
                                   sums["sunday"], sums["holiday"], sums["night"]))
        day += timedelta(days=1)
    fields = ("work_without_guest", "guest", "guest_used_for_target", "topup", "vacation",
              "sick", "credited", "sunday", "holiday", "night")
    return {"year": year, "month": month, "days": [asdict(item) for item in result],
            "totals": {field: sum(getattr(item, field) for item in result) for field in fields},
            "vacation_days": sum(item.type == _text_source('server_reports_monthly.text_35d3a889824d') for item in result),
            "sick_days": sum(item.type == _text_source('server_reports_monthly.text_be1600b499c6') for item in result),
            "rule": _text_source('server_reports_monthly.text_2b3732a707c4')}
