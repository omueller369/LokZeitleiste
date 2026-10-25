import unittest
from datetime import date
from lokzeitleiste.planning.palette import COLORS,base_key,background_key
class PlanPaletteTest(unittest.TestCase):
    def test_weekend_leave_and_holiday_precedence(self):
        cases=[('2026-10-05','Arbeitstag',False,'Arbeitstag','Arbeitstag'),('2026-10-03','Arbeitstag',False,'Wochenende','Wochenende'),('2026-10-04','Ruhetag',False,'Ruhetag','Ruhetag'),('2026-10-05','Ruhetag',False,'Ruhetag','Ruhetag'),('2026-10-04','Urlaub',False,'Urlaub','Urlaub'),('2026-10-03','Urlaub',True,'Urlaub','Feiertag'),('2026-10-03','Arbeitstag',True,'Wochenende','Feiertag')]
        for value,kind,holiday,base,background in cases:
            day=dict(date=value,kind=kind,is_holiday=holiday)
            self.assertEqual(base_key(day),base);self.assertEqual(background_key(day),background)
        self.assertEqual(base_key(dict(date=date(2026,10,4),kind='Arbeitstag')),'Wochenende')
        self.assertEqual([COLORS[k] for k in ('Urlaub','Arbeitstag','Wochenende','Feiertag')],['FF7256','F5F5F5','EEDC82','FFE4E1'])
