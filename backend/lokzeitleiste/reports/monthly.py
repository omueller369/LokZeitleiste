"""Monatsübersicht in Minuten; Gastfahrt gehört zur geleisteten Zeit."""

from dataclasses import asdict, dataclass
from datetime import date, timedelta

from ..models import WorkEntry
from .daily import day_rows, grouped_days, totals


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
    for entry in entries:
        if entry.kind in ("Urlaub", "Krank") and start <= entry.entry_date < end:
            absence.setdefault(entry.entry_date, set()).add(entry.kind)
    result = []
    day = start
    while day < end:
        rows = by_day.get(day, [])
        sums = totals(rows)
        work = sums["work"]
        kinds = absence.get(day, set())
        if len(kinds) > 1 or (kinds and work):
            raise ValueError(f"Widersprüchliche Arbeits- und Abwesenheitseinträge am {day:%d.%m.%Y}")
        guest = sums["guest"]
        without_guest = work - guest
        used = min(guest, max(0, 480 - without_guest))
        topup = max(0, 480 - work) if work else 0
        vacation = 480 if "Urlaub" in kinds else 0
        sick = 480 if "Krank" in kinds else 0
        if work or vacation or sick:
            kind = "Urlaub" if vacation else "Krank" if sick else "Arbeit"
            result.append(MonthDay(day.isoformat(), kind, without_guest, guest, used,
                                   topup, vacation, sick, work + topup + vacation + sick,
                                   sums["sunday"], sums["holiday"], sums["night"]))
        day += timedelta(days=1)
    fields = ("work_without_guest", "guest", "guest_used_for_target", "topup", "vacation",
              "sick", "credited", "sunday", "holiday", "night")
    return {"year": year, "month": month, "days": [asdict(item) for item in result],
            "totals": {field: sum(getattr(item, field) for item in result) for field in fields},
            "vacation_days": sum(item.type == "Urlaub" for item in result),
            "sick_days": sum(item.type == "Krank" for item in result),
            "rule": "Gastfahrt ist Teil der Arbeitszeit, wird zuerst für acht Stunden genutzt und nicht doppelt gezählt."}
