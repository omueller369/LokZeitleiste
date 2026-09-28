import unittest
from datetime import date

from lokzeitleiste.models import WorkEntry
from lokzeitleiste.reports.daily import day_rows
from lokzeitleiste.reports.monthly import summarize_month


class ReportCalculationTest(unittest.TestCase):
    def test_public_holiday_split_and_previous_month_rollover(self):
        crossing = WorkEntry(client_id="a", kind="Zugfahrt", entry_date=date(2026, 4, 30),
                             start_time="22:00", end_time="06:00", pause_minutes=0,
                             guest_minutes=120)
        april, may = day_rows([crossing], "BE")
        self.assertEqual((april.work, april.night, april.holiday), (120, 120, 0))
        self.assertEqual((may.work, may.night, may.holiday), (360, 360, 360))
        self.assertEqual(summarize_month([crossing], year=2026, month=5, federal_state="BE")["totals"]["credited"], 480)

    def test_same_day_absence_once_and_conflict_detection(self):
        vacation = [WorkEntry(client_id=str(i), kind="Urlaub", entry_date=date(2026, 9, 23),
                              start_time="08:00", end_time="16:00", pause_minutes=0,
                              guest_minutes=0) for i in range(2)]
        summary = summarize_month(vacation, year=2026, month=9, federal_state="BE")
        self.assertEqual((summary["vacation_days"], summary["totals"]["vacation"]), (1, 480))
        vacation.append(WorkEntry(client_id="sick", kind="Krank", entry_date=date(2026, 9, 23),
                                  start_time="08:00", end_time="16:00", pause_minutes=0,
                                  guest_minutes=0))
        with self.assertRaises(ValueError):
            summarize_month(vacation, year=2026, month=9, federal_state="BE")
