import unittest
from datetime import date
from sqlalchemy.orm import Session
from lokzeitleiste.models import PlanDutyAudit
from lokzeitleiste.planning.service import get_year
from lokzeitleiste.planning.excel import parse_excel,template
import test_accounts


class BorderDutyTest(unittest.TestCase):
    setUp=test_accounts.AccountsTest.setUp
    tearDown=test_accounts.AccountsTest.tearDown

    def role(self,kind):
        data=next(r for r in self.client.get('/api/v1/admin/tf').json() if r['id']==self.tf)
        data['driver_type']=kind
        response=self.client.put(f'/api/v1/admin/tf/{self.tf}',json=data)
        self.assertEqual(response.status_code,200,response.text)

    def apply(self,year,days,revisions):
        return self.client.post(f'/api/v1/admin/tf/{self.tf}/plan/{year}/bulk',json=dict(days=days,expected_revisions=revisions))

    def test_mixed_targets_overnight_holiday_vacation_audit_and_qualification(self):
        days=[dict(date='2026-04-28',kind='Arbeitstag',shift='border_day'),dict(date='2026-04-30',kind='Arbeitstag',shift='border_night'),dict(date='2026-05-01',kind='Arbeitstag',shift='border_day'),dict(date='2026-05-02',kind='Urlaub'),dict(date='2026-05-03',kind='Ruhetag'),dict(date='2026-05-04',kind='Arbeitstag',shift='standard')]
        self.assertEqual(self.apply(2026,days,{4:0,5:0}).status_code,422)
        self.role('both');response=self.apply(2026,days,{4:0,5:0});self.assertEqual(response.status_code,200,response.text)
        plan=response.json()['plan'];april=plan['months'][3];may=plan['months'][4]
        self.assertEqual(april['work_target_minutes'],1440)
        night=april['days'][29];self.assertEqual(night['planned_start'],'2026-04-30T21:00');self.assertEqual(night['planned_end'],'2026-05-01T09:00');self.assertEqual(night['target_minutes'],720)
        self.assertEqual([d['target_minutes'] for d in may['days'][:4]],[0,480,0,480])
        self.assertEqual(self.client.get(f'/api/v1/admin/tf/{self.tf}/hours/2026').json()['months'][3]['target_minutes'],1440)
        edited=self.apply(2026,[dict(date='2026-04-30',kind='Arbeitstag',shift='standard')],{4:1});self.assertEqual(edited.status_code,200,edited.text)
        self.assertEqual(edited.json()['plan']['months'][3]['target_minutes'],1200)
        history=self.client.get(f'/api/v1/admin/tf/{self.tf}/plan/2026/history').json()[0]
        self.assertEqual((history['previous_shift'],history['new_shift']),('border_night','standard'))
        self.assertEqual(self.apply(2026,[dict(date='2026-04-30',kind='Arbeitstag',shift='border_night')],{4:1}).status_code,409)

    def test_border_default_existing_history_and_excel_round_trip(self):
        self.role('border')
        response=self.apply(2026,[dict(date='2026-06-01',kind='Arbeitstag'),dict(date='2026-06-02',kind='Arbeitstag',shift='border_night')],{6:0})
        self.assertEqual(response.status_code,200,response.text);self.assertEqual(response.json()['plan']['months'][5]['target_minutes'],1440)
        with Session(self.engine) as db:
            book=template(get_year(db,self.tf,2026),'P-ACCOUNT')
        imported=parse_excel(book,year=2026,personnel_number='P-ACCOUNT')
        night=next(d for d in imported if d.date==date(2026,6,2));self.assertEqual(night.shift,'border_night')
        self.role('route')
        old=self.client.get(f'/api/v1/admin/tf/{self.tf}/plan/2026/6').json();self.assertEqual(old['days'][1]['target_minutes'],720)
        self.assertEqual(self.client.get('/api/v1/admin/tf').json()[0]['driver_type'],'route')

    def test_shift_cycle_year_boundary_and_nonqualified_assignment(self):
        response=self.client.post('/api/v1/admin/shifts/models',json=dict(name='Grenze T-N-R',blocks=[dict(kind='Arbeitstag',days=1,shift='border_day'),dict(kind='Arbeitstag',days=1,shift='border_night'),dict(kind='Ruhetag',days=1)]))
        self.assertEqual(response.status_code,201,response.text);model=response.json()
        payload=dict(model_id=model['id'],tf_id=self.tf,start='2026-12-30',end='2027-01-02',cycle_start='2026-12-30',expected_model_revision=model['revision'])
        self.assertEqual(self.client.post('/api/v1/admin/shifts/preview',json=payload).status_code,422)
        self.role('border');preview=self.client.post('/api/v1/admin/shifts/preview',json=payload)
        self.assertEqual(preview.status_code,200,preview.text)
        self.assertEqual(preview.json()['days'][1]['new_planned_end'],'2027-01-01T09:00')
        payload['expected_revisions']=preview.json()['expected_revisions']
        self.assertEqual(self.client.post('/api/v1/admin/shifts/assign',json=payload).status_code,200)
        december=self.client.get(f'/api/v1/admin/tf/{self.tf}/plan/2026/12').json()
        self.assertEqual(december['days'][30]['shift'],'border_night');self.assertEqual(december['target_minutes'],1440)


if __name__=='__main__':unittest.main()
