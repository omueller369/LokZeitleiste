import calendar
import unittest
from datetime import date
from lokzeitleiste.planning.calendar_layout import year_slots
class YearLayoutTest(unittest.TestCase):
    def test_all_months_keep_original_day_columns_and_every_date_once(self):
        for year in (2024,2026,2027,2028):
            for month in range(1,13):
                days=[{'date':date(year,month,d).isoformat()} for d in range(1,calendar.monthrange(year,month)[1]+1)]
                slots=year_slots({'days':days})
                self.assertEqual(len(slots),31)
                self.assertEqual([d for d in slots if d],days)
                for column,day in enumerate(slots):
                    if day:self.assertEqual(date.fromisoformat(day['date']).day,column+1)
