import unittest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
import test_accounts
from lokzeitleiste.main import app
from lokzeitleiste.models import AccountPolicy, PlanMonth, TfEmployment, User
from lokzeitleiste.security import verify_password


class TfPortalTest(unittest.TestCase):
    tearDown=test_accounts.AccountsTest.tearDown
    payload=test_accounts.AccountsTest.payload

    def setUp(self):
        test_accounts.AccountsTest.setUp(self)
        self.driver=TestClient(app,base_url='https://testserver')
        self.staff_clients.append(self.driver)
        self.driver.post('/api/v1/account/login',json={'username':'787100','password':'tf-secret-12345'})

    def test_six_character_creation_change_login_and_reset(self):
        profile=self.client.get('/api/v1/admin/tf').json()[0]
        profile.update(username='787123',personnel_number='00123',password='abc123',email='787123@example.com')
        created=self.client.post('/api/v1/admin/tf',json=profile)
        self.assertEqual(created.status_code,201,created.text)
        login=self.driver.post('/api/v1/tf/login',json={'username':'787123','password':'abc123'}).json()
        self.assertTrue(login['password_change_required'])
        headers={'Authorization':'Bearer '+login['access_token']}
        self.assertEqual(self.driver.get('/api/v1/tf/portal',headers=headers).status_code,403)
        change=self.driver.post('/api/v1/account/password',headers=headers,json={'current_password':'abc123','new_password':'def456','confirm_password':'def456'})
        self.assertEqual(change.status_code,200,change.text)
        self.assertEqual(self.driver.get('/api/v1/tf/portal',headers=headers).status_code,401)
        self.assertEqual(self.driver.post('/api/v1/account/login',json={'username':'787123','password':'def456'}).status_code,200)
        self.assertEqual(self.driver.get('/api/v1/tf/portal').status_code,200)
        reset=self.client.post('/api/v1/admin/accounts/'+str(created.json()['id'])+'/reset-password',json={'initial_password':'ghi789'})
        self.assertEqual(reset.status_code,200,reset.text)
        self.assertEqual(self.driver.get('/api/v1/tf/portal').status_code,401)
        relogin=self.driver.post('/api/v1/account/login',json={'username':'787123','password':'ghi789'})
        self.assertTrue(relogin.json()['password_change_required'])
        self.assertEqual(self.driver.get('/tf',follow_redirects=False).status_code,303)
        invalid=dict(profile,username='787124',personnel_number='00124',password='12345')
        self.assertEqual(self.client.post('/api/v1/admin/tf',json=invalid).status_code,422)
        staff=self.payload('six-office');staff['initial_password']='abc123'
        self.assertEqual(self.client.post('/api/v1/admin/staff',json=staff).status_code,201)

    def test_own_plan_matches_personnel_planning_and_is_read_only(self):
        profile=self.client.get('/api/v1/admin/tf').json()[0];profile['driver_type']='both'
        self.assertEqual(self.client.put(f'/api/v1/admin/tf/{self.tf}',json=profile).status_code,200)
        path=f'/api/v1/admin/tf/{self.tf}/plan/2026/10'
        edited=self.client.put(path,json={'expected_revision':0,'days':[
            {'date':'2026-10-03','kind':'Arbeitstag','shift':'border_night','note':'Feiertagsdienst'},
            {'date':'2026-10-05','kind':'Arbeitstag','shift':'border_night','note':'Einsatz A'},
            {'date':'2026-10-06','kind':'Urlaub'}, {'date':'2026-10-07','kind':'Ruhetag'}]})
        self.assertEqual(edited.status_code,200,edited.text)
        plan=self.driver.get('/api/v1/tf/portal/plan/2026/10').json()
        self.assertEqual(plan,self.client.get(path).json())
        self.assertEqual(plan['days'][2]['target_minutes'],0)
        self.assertTrue(plan['days'][2]['is_holiday'])
        self.assertEqual(plan['days'][4]['planned_end'],'2026-10-06T09:00')
        self.assertEqual(plan['days'][4]['target_minutes'],720)
        self.assertEqual(plan['days'][5]['target_minutes'],480)
        self.assertEqual(plan['days'][6]['target_minutes'],0)
        other=self.create_tf('787111','OTHER').json()['id']
        self.assertEqual(self.driver.get('/api/v1/tf/portal/plan/2026/10?tf_id='+str(other)).json(),plan)
        self.assertEqual(self.driver.get(f'/api/v1/admin/tf/{other}/plan/2026/10').status_code,401)
        self.assertEqual(self.driver.post('/api/v1/tf/portal/plan/2026/10',json={}).status_code,405)
        with Session(self.engine) as db:before=len(db.scalars(select(PlanMonth)).all())
        self.assertEqual(self.driver.get('/api/v1/tf/portal/plan/2027/1').status_code,200)
        with Session(self.engine) as db:self.assertEqual(len(db.scalars(select(PlanMonth)).all()),before)
        self.assertEqual(self.driver.get('/api/v1/tf/portal/plan/2026/13').status_code,422)

    def test_portal_pages_roles_and_logged_out_access(self):
        for path in ('/tf','/tf/bremszettel','/tf/arbeitsbericht','/tf/lokuebergabebuch','/tf/leuna-uebergabeprotokoll','/tf/arbeitsplan'):
            result=self.driver.get(path);self.assertEqual(result.status_code,200);self.assertIn('TF Portal',result.text.replace('TF-Portal','TF Portal'))
            self.assertEqual(self.client.get(path,follow_redirects=False).status_code,303)
        self.assertEqual(self.client.get('/api/v1/tf/portal/plan/2026/10').status_code,403)
        staff=self.payload('portal-office');self.client.post('/api/v1/admin/staff',json=staff)
        self.driver.post('/api/v1/account/login',json={'username':'portal-office','password':staff['initial_password']})
        self.assertEqual(self.driver.get('/api/v1/tf/portal',headers={'X-CTL-Area':'backend'}).status_code,403)
        self.driver.cookies.clear()
        self.assertEqual(self.driver.get('/tf',follow_redirects=False).status_code,303)
        self.assertEqual(self.driver.get('/api/v1/tf/portal/plan/2026/10').status_code,401)

    def test_initial_password_and_blocked_tf_cannot_access_portal(self):
        with Session(self.engine) as db:db.get(AccountPolicy,self.tf).must_change_password=True;db.commit()
        self.assertEqual(self.driver.get('/api/v1/tf/portal/plan/2026/10').status_code,403)
        self.assertEqual(self.driver.get('/tf',follow_redirects=False).status_code,303)
        with Session(self.engine) as db:
            db.get(AccountPolicy,self.tf).must_change_password=False
            db.get(TfEmployment,self.tf).immediate_block=True;db.commit()
        self.assertEqual(self.driver.get('/api/v1/tf/portal/plan/2026/10').status_code,401)
        self.assertEqual(self.driver.get('/tf',follow_redirects=False).status_code,303)

    def test_own_year_plan_read_only_year_bounds_and_leap_days(self):
        path='/api/v1/tf/portal/plan/2024'
        result=self.driver.get(path);self.assertEqual(result.status_code,200,result.text)
        year=result.json();self.assertEqual(year['year'],2024);self.assertEqual(len(year['months']),12)
        self.assertEqual(len(year['months'][1]['days']),29)
        self.assertEqual(year,self.client.get(f'/api/v1/admin/tf/{self.tf}/plan/2024').json())
        self.assertEqual(self.driver.get(path+'?tf_id=999999').json(),year)
        self.assertEqual(self.driver.post(path,json={}).status_code,405)
        self.assertEqual(self.driver.get('/api/v1/tf/portal/plan/1999').status_code,422)
        self.assertEqual(self.driver.get('/api/v1/tf/portal/plan/2101').status_code,422)
        self.driver.cookies.clear();self.assertEqual(self.driver.get(path).status_code,401)
