import unittest
from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

import test_api
from lokzeitleiste.main import app
from lokzeitleiste.models import AccountAudit, AccountPolicy, ModulePermission, User, WorkEntry, WorkMonth


class AccountsTest(unittest.TestCase):
    def setUp(self):
        test_api.ApiFlowTest.setUp(self)
        self.client.post('/api/v1/admin/login',json={'username':'admin','password':'admin-secret-12345'})
        self.staff_clients=[]
        self.create_tf=test_api.ApiFlowTest.create_tf.__get__(self)
        self.tf=self.create_tf('tf-account','P-ACCOUNT').json()['id']

    def tearDown(self):
        for client in self.staff_clients: client.close()
        test_api.ApiFlowTest.tearDown(self)

    def payload(self,username='office-one',grants=None):
        return {'username':username,'initial_password':'initial-secret-12345','first_name':'Mira','last_name':'Büro',
                'nationality':'deutsch','birth_date':'1990-05-12','cost_center':'K-001',
                'addresses':[{'street':'Hauptstraße','house_number':'12a','postal_code':'01234','city':'Berlin'},
                             {'street':'Nebenstraße','house_number':'2','postal_code':'10115','city':'Berlin'}],
                'permissions':grants or {}}

    def create_staff(self,grants=None,username='office-one'):
        result=self.client.post('/api/v1/admin/staff',json=self.payload(username,grants))
        self.assertEqual(result.status_code,201,result.text)
        return result.json()['id']

    def staff_login(self,username='office-one',password='initial-secret-12345'):
        client=TestClient(app,base_url='https://testserver');self.staff_clients.append(client)
        result=client.post('/api/v1/admin/login',json={'username':username,'password':password})
        self.assertEqual(result.status_code,200,result.text)
        return client,result.json()

    def change(self,client,old='initial-secret-12345',new='personal-secret-67890'):
        return client.post('/api/v1/account/password',json={'current_password':old,'new_password':new,'confirm_password':new})

    def active_staff(self,grants=None,username='office-one'):
        user_id=self.create_staff(grants,username);client,login=self.staff_login(username)
        self.assertTrue(login['password_change_required'])
        self.assertEqual(self.change(client).status_code,200)
        client.post('/api/v1/admin/login',json={'username':username,'password':'personal-secret-67890'})
        return user_id,client

    def test_create_addresses_hash_and_first_login_gate(self):
        user_id=self.create_staff({'planning':1})
        with Session(self.engine) as db:
            self.assertNotEqual(db.get(User,user_id).password_hash,'initial-secret-12345')
        rows=self.client.get('/api/v1/admin/staff').json()
        self.assertEqual(rows[0]['addresses'][0]['postal_code'],'01234')
        self.assertEqual(len(rows[0]['addresses']),2)
        self.assertNotIn('initial_password',rows[0]);self.assertNotIn('password_hash',rows[0])
        client,_=self.staff_login()
        self.assertTrue(client.get('/api/v1/account/me').json()['password_change_required'])
        for path in ['/api/v1/admin/me','/api/v1/admin/tf','/api/v1/admin/staff',f'/api/v1/admin/tf/{self.tf}/plan/2026']:
            self.assertEqual(client.get(path).status_code,403,path)
        self.assertEqual(self.change(client,old='wrong').status_code,403)
        self.assertEqual(self.change(client,new='initial-secret-12345').status_code,422)
        self.assertEqual(self.change(client).status_code,200)
        self.assertEqual(client.get('/api/v1/account/me').status_code,401)
        client.post('/api/v1/admin/login',json={'username':'office-one','password':'personal-secret-67890'})
        self.assertFalse(client.get('/api/v1/account/me').json()['password_change_required'])
        self.assertEqual(client.get(f'/api/v1/admin/tf/{self.tf}/plan/2026').status_code,200)

    def test_reader_cannot_write_or_read_other_modules(self):
        _,client=self.active_staff({'planning':1})
        selected=client.get('/api/v1/admin/tf').json()[0]
        self.assertNotIn('birth_date',selected);self.assertNotIn('email',selected)
        base=f'/api/v1/admin/tf/{self.tf}'
        self.assertEqual(client.get(base+'/plan/2026/9/pdf').status_code,200)
        self.assertEqual(client.put(base+'/plan/2026/9',json={'expected_revision':0,'days':[]}).status_code,403)
        self.assertEqual(client.post(base+'/plan/2026/import/preview',files={'file':('a.xlsx',b'x')}).status_code,403)
        for path in [base+'/worktime/months/2026/9',base+'/months',base+'/reports','/api/v1/admin/staff']:
            self.assertEqual(client.get(path).status_code,403,path)
        self.assertEqual(client.post('/api/v1/admin/tf',json={}).status_code,403)

    def test_writer_can_edit_plan_without_user_administration(self):
        _,client=self.active_staff({'planning':2})
        base=f'/api/v1/admin/tf/{self.tf}/plan/2026/9'
        result=client.put(base,json={'expected_revision':0,'days':[{'date':'2026-09-01','kind':'Urlaub'}]})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['vacation_days'],1)
        self.assertEqual(client.post('/api/v1/admin/staff',json=self.payload('not-allowed')).status_code,403)

    def test_worktime_reader_cannot_correct_or_retry_and_plan_is_redacted(self):
        _,client=self.active_staff({'worktime':1})
        base=f'/api/v1/admin/tf/{self.tf}/worktime'
        data=client.get(base+'/months/2026/9')
        self.assertEqual(data.status_code,200,data.text)
        self.assertNotIn('days',data.json()['month']['planning'])
        self.assertEqual(client.patch(base+'/entries/1',json={'start':'08:00','end':'17:00',
            'expected_updated_at':'2026-09-01T12:00:00','reason':'Test'}).status_code,403)
        self.assertEqual(client.post(base+'/changes/1/retry').status_code,403)

    def test_employees_write_cannot_create_or_reset_accounts(self):
        _,client=self.active_staff({'employees':2})
        base=f'/api/v1/admin/tf/{self.tf}'
        self.assertEqual(client.patch(base+'/delivery',json={'email':'new@example.com','federal_state':'BE'}).status_code,200)
        self.assertEqual(client.post('/api/v1/admin/tf',json={}).status_code,403)
        self.assertEqual(client.post(f'/api/v1/admin/accounts/{self.tf}/reset-password',json={'initial_password':'reset-secret-12345'}).status_code,403)

    def test_no_grants_and_no_privilege_escalation(self):
        user_id,client=self.active_staff({'staff':3,'planning':1})
        self.assertEqual(client.post('/api/v1/admin/staff',json=self.payload('too-powerful',{'planning':2})).status_code,403)
        self.assertEqual(client.post('/api/v1/admin/staff',json=self.payload('limited',{'planning':1})).status_code,201)
        self.assertEqual(client.put(f'/api/v1/admin/staff/{user_id}',json=self.payload(grants={'staff':3,'planning':3})).status_code,403)
        self.assertEqual(client.post('/api/v1/admin/accounts/1/reset-password',json={'initial_password':'root-reset-secret-12345'}).status_code,403)
        self.create_staff({'staff':3,'worktime':3},'higher')
        target=self.client.get('/api/v1/admin/staff').json()[-1]
        higher=next(item for item in self.client.get('/api/v1/admin/staff').json() if item['username']=='higher')
        self.assertEqual(client.put(f'/api/v1/admin/staff/{higher["id"]}',json=self.payload(grants={})).status_code,403)
        _,empty=self.active_staff({},'empty')
        self.assertEqual(empty.get('/api/v1/admin/tf').status_code,403)

    def test_profile_edit_with_write_cannot_grant_rights(self):
        target=self.create_staff({'staff':1},'target')
        _,client=self.active_staff({'staff':2})
        data=self.payload('target',{'staff':1});data['cost_center']='K-NEW'
        self.assertEqual(client.put(f'/api/v1/admin/staff/{target}',json=data).status_code,200)
        data['permissions']={'staff':2}
        self.assertEqual(client.put(f'/api/v1/admin/staff/{target}',json=data).status_code,403)

    def test_reset_revokes_sessions_forces_change_and_keeps_audit(self):
        user_id,client=self.active_staff({'planning':1})
        result=self.client.post(f'/api/v1/admin/accounts/{user_id}/reset-password',json={'initial_password':'reset-secret-12345'})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(client.get('/api/v1/account/me').status_code,401)
        client,_=self.staff_login(password='reset-secret-12345')
        self.assertEqual(client.get(f'/api/v1/admin/tf/{self.tf}/plan/2026').status_code,403)
        self.assertEqual(self.change(client,old='reset-secret-12345',new='second-personal-67890').status_code,200)
        with Session(self.engine) as db:
            actions=list(db.scalars(select(AccountAudit.action).where(AccountAudit.target_id==user_id)))
            self.assertIn('password_reset',actions);self.assertEqual(actions.count('password_changed'),2)

    def test_administrator_self_change_and_csrf(self):
        with patch('lokzeitleiste.main.PUBLIC_ORIGIN','https://testserver'):
            self.assertEqual(self.change(self.client,old='admin-secret-12345').status_code,403)
            result=self.client.post('/api/v1/account/password',headers={'Origin':'https://testserver'},json={
                'current_password':'admin-secret-12345','new_password':'new-admin-secret-67890','confirm_password':'new-admin-secret-67890'})
            self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.client.get('/api/v1/admin/tf').status_code,401)
        self.assertEqual(self.client.post('/api/v1/admin/login',json={'username':'admin','password':'new-admin-secret-67890'}).status_code,200)

    def test_tf_initial_password_and_bearer_change(self):
        result=self.client.post('/api/v1/admin/tf',json={'username':'tf-initial','password':'tf-initial-12345',
            'first_name':'Test','last_name':'Tf','personnel_number':'P-INITIAL','target_hours_minutes':9600,'vacation_days':30,
            'birth_date':'1990-05-12','bahncard':50,'email':'tf@example.com','federal_state':'BE'})
        self.assertEqual(result.status_code,201,result.text)
        login=self.client.post('/api/v1/tf/login',json={'username':'tf-initial','password':'tf-initial-12345'}).json()
        self.assertTrue(login['password_change_required'])
        headers={'Authorization':'Bearer '+login['access_token']}
        self.assertEqual(self.client.get('/api/v1/me/months/2026/9/entries',headers=headers).status_code,403)
        result=self.client.post('/api/v1/account/password',headers=headers,json={'current_password':'tf-initial-12345',
            'new_password':'tf-personal-67890','confirm_password':'tf-personal-67890'})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.client.get('/api/v1/me/months/2026/9/entries',headers=headers).status_code,401)
        self.assertEqual(self.client.get('/api/v1/admin/me').json()['username'],'admin')

    def test_validation_duplicate_and_permissions_update_revokes_login(self):
        self.create_staff({'planning':1})
        self.assertEqual(self.client.post('/api/v1/admin/staff',json=self.payload()).status_code,409)
        for field,value in [('addresses',[]),('nationality',' '),('birth_date','2999-01-01'),('permissions',{'unknown':3})]:
            data=self.payload('invalid');data[field]=value
            self.assertEqual(self.client.post('/api/v1/admin/staff',json=data).status_code,422,field)
        user_id,client=self.active_staff({'planning':2},'revoke')
        self.assertEqual(self.client.put(f'/api/v1/admin/staff/{user_id}',json=self.payload('revoke',{'planning':1})).status_code,200)
        self.assertEqual(client.get('/api/v1/admin/me').status_code,401)


if __name__=='__main__':unittest.main()
