import unittest
from datetime import date
from uuid import uuid4
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import Session

import test_accounts
from lokzeitleiste.models import WorkMonth,WorkEntry,OvertimeClosing,OvertimeAudit
from lokzeitleiste.reports.intervals import set_end_date
from lokzeitleiste.overtime import allocate,CAP


class OvertimeTest(unittest.TestCase):
    setUp=test_accounts.AccountsTest.setUp
    tearDown=test_accounts.AccountsTest.tearDown
    payload=test_accounts.AccountsTest.payload
    create_staff=test_accounts.AccountsTest.create_staff
    staff_login=test_accounts.AccountsTest.staff_login
    change=test_accounts.AccountsTest.change
    active_staff=test_accounts.AccountsTest.active_staff

    def url(self,month=9,year=2026):
        return f'/api/v1/admin/tf/{self.tf}/overtime/{year}/{month}'

    def get(self,month=9,year=2026):
        result=self.client.get(self.url(month,year))
        self.assertEqual(result.status_code,200,result.text)
        return result.json()

    def enable(self,month=9,enabled=True,year=2026):
        result=self.client.put(self.url(month,year)+'/policy',
            json=dict(enabled=enabled,expected_token=self.get(month,year)['token']))
        self.assertEqual(result.status_code,200,result.text)
        return result.json()

    def entry(self,day,start='09:00',end='19:00',kind='Sonstige Erfassung',end_date=None,pause=60):
        with Session(self.engine) as db:
            period=db.scalar(select(WorkMonth).where(WorkMonth.tf_user_id==self.tf,WorkMonth.year==day.year,WorkMonth.month==day.month))
            if not period:
                period=WorkMonth(tf_user_id=self.tf,year=day.year,month=day.month)
                db.add(period);db.flush()
            row=WorkEntry(work_month_id=period.id,client_id=str(uuid4()),kind=kind,entry_date=day,
                          start_time=start,end_time=end,pause_minutes=pause,guest_minutes=0)
            db.add(row)
            if end_date:set_end_date(row,end_date)
            db.commit()
            return row.id

    def close(self,month=9,mode='annual',year=2026):
        result=self.client.post(self.url(month,year)+'/close',
            json=dict(mode=mode,expected_token=self.get(month,year)['token']))
        self.assertEqual(result.status_code,200,result.text)
        return result.json()

    def test_per_duty_midnight_pause_absence_and_activation(self):
        self.entry(date(2026,9,1),end='17:00')
        self.entry(date(2026,9,2))
        self.entry(date(2026,9,30),'21:00','09:00',end_date=date(2026,10,1),pause=120)
        self.entry(date(2026,9,3),'09:00','21:00',kind='Urlaub')
        self.entry(date(2026,9,4),'09:00','21:00',kind='Krank')
        self.entry(date(2026,9,5),'09:00','21:00',kind='Bereitschaft')
        self.assertEqual(self.get()['total_minutes'],0)
        self.enable()
        self.assertEqual(self.get()['total_minutes'],360)
        self.assertEqual(self.get(10)['total_minutes'],0)
        self.assertTrue(self.get(10)['enabled'])
        self.enable(10,False)
        self.assertFalse(self.get(11)['enabled'])
        self.assertTrue(self.get(9)['enabled'])

    def test_bank_cap_payout_and_duplicate_close(self):
        self.entry(date(2026,9,1),'00:00','00:00',end_date=date(2026,9,4))
        self.enable()
        result=self.close()
        self.assertEqual(result['closing']['total_minutes'],64*60)
        self.assertEqual(result['closing']['annual_minutes'],40*60)
        self.assertEqual(result['closing']['payout_minutes'],24*60)
        self.assertEqual(result['bank_balance_minutes'],CAP)
        retry=self.client.post(self.url()+'/close',json=dict(mode='annual',expected_token=result['token']))
        self.assertEqual(retry.status_code,409)
        with Session(self.engine) as db:
            self.assertEqual(len(db.scalars(select(OvertimeClosing)).all()),1)
            self.assertEqual(len(db.scalars(select(OvertimeAudit).where(OvertimeAudit.action=='close')).all()),1)

    def test_payout_does_not_credit_bank(self):
        self.entry(date(2026,9,1))
        self.enable()
        result=self.close(mode='payout')
        self.assertEqual(result['bank_balance_minutes'],0)
        self.assertEqual(result['closing']['payout_minutes'],120)

    def test_tokens_prevent_stale_calculation_and_competing_month_closings(self):
        self.entry(date(2026,8,1));self.entry(date(2026,9,1))
        self.enable(8)
        old=self.get()
        self.close(8)
        result=self.client.post(self.url()+'/close',json=dict(mode='annual',expected_token=old['token']))
        self.assertEqual(result.status_code,409)
        old=self.get()
        self.entry(date(2026,9,2))
        result=self.client.post(self.url()+'/close',json=dict(mode='annual',expected_token=old['token']))
        self.assertEqual(result.status_code,409)

    def test_changed_source_requires_review_reopen_and_reclose(self):
        identity=self.entry(date(2026,9,1));self.enable();self.close()
        with Session(self.engine) as db:
            db.get(WorkEntry,identity).end_time='20:00';db.commit()
        data=self.get();self.assertTrue(data['stale'])
        self.assertEqual(data['closing']['annual_minutes'],120)
        self.assertEqual(data['total_minutes'],180)
        self.entry(date(2026,8,1));self.enable(10)
        # A new closing must not book against an unresolved old snapshot.
        with patch('lokzeitleiste.overtime.current_month',return_value=date(2026,11,1)):
            result=self.client.post(self.url(10)+'/close',json=dict(mode='annual',expected_token=self.get(10)['token']))
        self.assertEqual(result.status_code,409)
        opened=self.client.post(self.url()+'/reopen',json=dict(reason='Zeitkorrektur',expected_token=self.get()['token']))
        self.assertEqual(opened.status_code,200,opened.text)
        self.assertEqual(opened.json()['bank_balance_minutes'],0)
        result=self.close()
        self.assertEqual(result['closing']['annual_minutes'],180)
        self.assertEqual(result['closing']['revision'],3)

    def test_policies_cannot_change_closed_history_and_current_month_cannot_close(self):
        self.entry(date(2026,9,1));self.enable();self.close()
        response=self.client.put(self.url()+'/policy',json=dict(enabled=False,expected_token=self.get()['token']))
        self.assertEqual(response.status_code,409)
        with patch('lokzeitleiste.overtime.current_month',return_value=date(2026,10,1)):
            response=self.client.post(self.url(10)+'/close',json=dict(mode='payout',expected_token=self.get(10)['token']))
        self.assertEqual(response.status_code,409)

    def test_bank_balance_survives_calendar_year_change(self):
        self.entry(date(2025,12,1));self.enable(12,year=2025);self.close(12,year=2025)
        self.entry(date(2026,9,1))
        result=self.close()
        self.assertEqual(result['bank_balance_minutes'],240)
        year=self.client.get(f'/api/v1/admin/tf/{self.tf}/overtime/2026').json()
        self.assertEqual(year['opening_minutes'],120)

    def test_permission_levels_read_close_administer_and_owner_validation(self):
        _,reader=self.active_staff({'reports':1},'ot-read')
        self.assertEqual(reader.get(self.url()).status_code,200)
        self.assertEqual(reader.put(self.url()+'/policy',json=dict(enabled=True,expected_token=self.get()['token'])).status_code,403)
        self.assertEqual(reader.post(self.url()+'/close',json=dict(mode='payout',expected_token=self.get()['token'])).status_code,403)
        self.enable();self.entry(date(2026,9,1))
        _,writer=self.active_staff({'reports':2},'ot-write')
        response=writer.post(self.url()+'/close',json=dict(mode='payout',expected_token=self.get()['token']))
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(writer.post(self.url()+'/reopen',json=dict(reason='Korrektur',expected_token=self.get()['token'])).status_code,403)
        _,none=self.active_staff({'employees':3},'ot-none')
        self.assertEqual(none.get(self.url()).status_code,403)
        self.assertEqual(self.client.get('/api/v1/admin/tf/999999/overtime/2026/9').status_code,404)
        self.assertEqual(self.client.get(self.url(13)).status_code,422)

    def test_allocation_exact_cap_and_overflow(self):
        self.assertEqual(allocate(120,0,'payout'),(0,120))
        self.assertEqual(allocate(120,CAP-60,'annual'),(60,60))
        self.assertEqual(allocate(120,CAP,'annual'),(0,120))
        self.assertEqual(allocate(0,CAP,'annual'),(0,0))
