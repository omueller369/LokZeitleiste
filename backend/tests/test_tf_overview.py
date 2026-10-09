import unittest
from datetime import date
from sqlalchemy.orm import Session
import test_accounts
from lokzeitleiste.models import WorkMonth, WorkEntry, WorkEntryDates


class TfOverviewTest(unittest.TestCase):
    setUp = test_accounts.AccountsTest.setUp
    tearDown = test_accounts.AccountsTest.tearDown
    payload = test_accounts.AccountsTest.payload
    create_staff = test_accounts.AccountsTest.create_staff
    staff_login = test_accounts.AccountsTest.staff_login
    change = test_accounts.AccountsTest.change
    active_staff = test_accounts.AccountsTest.active_staff

    def test_daily_monthly_yearly_comparison_and_cross_year_shift(self):
        with Session(self.engine) as db:
            month = WorkMonth(tf_user_id=self.tf, year=2025, month=12)
            db.add(month); db.flush()
            entry = WorkEntry(work_month_id=month.id, client_id='cross-year', kind='Sonstige Erfassung',
                              entry_date=date(2025,12,31), start_time="22:00", end_time="06:00", pause_minutes=0, guest_minutes=60, note='')
            db.add(entry); db.flush();db.add(WorkEntryDates(entry_id=entry.id,end_date=date(2026,1,1)))
            db.commit()
        plan = self.client.put(f'/api/v1/admin/tf/{self.tf}/plan/2026/1', json={'expected_revision':0,'days':[
            {'date':'2026-01-01','kind':'Arbeitstag'}, {'date':'2026-01-02','kind':'Urlaub'}, {'date':'2026-01-03','kind':'Ruhetag'}]})
        self.assertEqual(plan.status_code,200,plan.text)
        response=self.client.get(f'/api/v1/admin/tf/{self.tf}/hours/2026')
        self.assertEqual(response.status_code,200,response.text)
        data=response.json();jan=data['months'][0];day=jan['days'][0]
        self.assertEqual(day['work_minutes'],360);self.assertEqual(day['target_minutes'],0)
        self.assertTrue(day['is_holiday']);self.assertEqual(day['kind'],'Arbeitstag');self.assertEqual(day['balance_minutes'],360)
        self.assertEqual(jan['days'][1]['target_minutes'],480);self.assertEqual(jan['days'][1]['work_minutes'],0)
        self.assertEqual(jan['days'][2]['target_minutes'],0);self.assertIsNone(jan['days'][3]['balance_minutes'])
        self.assertEqual(jan['work_minutes'],360);self.assertEqual(jan['credited_minutes'],480)
        self.assertEqual(data['totals']['work_minutes'],360);self.assertEqual(data['totals']['target_minutes'],480)
        self.assertFalse(data['totals']['complete']);self.assertIsNone(data['totals']['balance_minutes'])
        self.assertEqual(sum(len(m['days']) for m in data['months']),365)
        feb=self.client.get(f'/api/v1/admin/tf/{self.tf}/hours/2028').json()['months'][1]
        self.assertEqual(len(feb['days']),29)

    def test_combined_module_permissions_and_validation(self):
        path=f'/api/v1/admin/tf/{self.tf}/hours/2026'
        for i,grants in enumerate([{'employees':1},{'worktime':1},{'planning':1},{'reports':1}]):
            _,client=self.active_staff(grants,username=f'restricted-{i}')
            self.assertEqual(client.get(path).status_code,403)
        for i,grants in enumerate([{'planning':1,'worktime':1},{'planning':1,'reports':1}]):
            _,client=self.active_staff(grants,username=f'allowed-{i}')
            self.assertEqual(client.get(path).status_code,200)
        self.assertEqual(self.client.get(f'/api/v1/admin/tf/{self.tf}/hours/1999').status_code,422)
        self.assertEqual(self.client.get('/api/v1/admin/tf/9999/hours/2026').status_code,404)
