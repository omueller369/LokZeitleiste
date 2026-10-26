import unittest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import test_accounts
from lokzeitleiste.main import app
from lokzeitleiste.models import AccountPolicy

class BackendStartTest(unittest.TestCase):
    setUp=test_accounts.AccountsTest.setUp
    tearDown=test_accounts.AccountsTest.tearDown
    payload=test_accounts.AccountsTest.payload
    create_staff=test_accounts.AccountsTest.create_staff
    staff_login=test_accounts.AccountsTest.staff_login
    change=test_accounts.AccountsTest.change
    active_staff=test_accounts.AccountsTest.active_staff

    def test_admin_gets_modules_and_start_is_not_a_grant(self):
        response=self.client.get('/api/v1/admin/start');self.assertEqual(response.status_code,200,response.text)
        ids={row['id'] for row in response.json()['modules']}
        self.assertTrue({'tf','staff','directory','planning','shifts','vehicles','app_defaults','reports','documents','password'}<=ids)
        tools=response.json()['admin_tools']
        self.assertEqual({row['url'] for row in tools},{'/phpmyadmin','/webmailer'})
        self.assertTrue(all(row['new_tab'] for row in tools))
        self.assertIn('no-store',response.headers['cache-control'])
        self.assertNotIn('start',self.client.get('/api/v1/admin/me').json()['permissions'])
        self.assertEqual(self.client.get('/admin/start').status_code,200)
        self.assertIn('no-cache',self.client.get('/admin/start').headers['cache-control'])
        self.assertEqual(self.client.get('/admin/menu-designs').status_code,200)

    def test_own_profile_shell_and_staff_personnel_number(self):
        payload=self.payload('own-profile-office',{})
        payload['personnel_number']='00123'
        response=self.client.post('/api/v1/admin/staff',json=payload)
        self.assertEqual(response.status_code,201,response.text)
        staff,_=self.staff_login('own-profile-office')
        self.assertEqual(staff.get('/api/v1/account/profile').status_code,403)
        self.assertEqual(self.change(staff).status_code,200)
        staff.post('/api/v1/admin/login',json={'username':'own-profile-office','password':'personal-secret-67890'})
        meta=staff.get('/api/v1/account/shell').json()
        self.assertEqual(meta['personnel_number'],'00123')
        self.assertEqual(meta['first_name'],'Mira')
        self.assertTrue(meta['last_login_at'].endswith('Z'))
        data=staff.get('/api/v1/account/profile?user_id=999').json()
        self.assertEqual(data['data']['personnel_number'],'00123')
        self.assertEqual(data['data']['username'],'own-profile-office')
        self.assertNotIn('password',str(data))
        self.assertEqual(len(data['data']['addresses']),2)
        self.assertEqual(staff.get('/admin/me').status_code,200)
        admin=self.client.get('/api/v1/account/profile').json()
        self.assertEqual(admin['data']['role'],'admin')

    def test_no_grants_still_has_personal_modules(self):
        _,staff=self.active_staff({},'start-empty')
        response=staff.get('/api/v1/admin/start');self.assertEqual(response.status_code,200,response.text)
        data=response.json();self.assertEqual(data['admin_tools'],[]);self.assertEqual({r['id'] for r in data['modules']},{'messages','documents','password','own_time'})
        self.assertEqual(data['name'],'Mira Büro')
        self.assertTrue(all(row['group']=='Mein Bereich' for row in data['modules']))

    def test_planning_reader_does_not_receive_staff_or_stammdaten(self):
        _,staff=self.active_staff({'planning':1},'start-planning')
        rows=staff.get('/api/v1/admin/start').json()['modules'];ids={r['id'] for r in rows}
        self.assertEqual(ids,{'tf','planning','overview','roster','messages','documents','password','own_time'})
        self.assertTrue(all(row['level']==1 for row in rows if row['group']!='Mein Bereich'))
        self.assertEqual(staff.get('/api/v1/admin/app-defaults').status_code,403)

    def test_specific_permissions_show_only_the_matching_tiles(self):
        _,staff=self.active_staff({'vehicles':1,'app_defaults':2},'start-data')
        rows=staff.get('/api/v1/admin/start').json()['modules'];levels={r['id']:r['level'] for r in rows}
        self.assertEqual(set(levels),{'vehicles','app_defaults','messages','documents','password','own_time'})
        self.assertEqual(levels['vehicles'],1);self.assertEqual(levels['app_defaults'],2)

    def test_anonymous_tf_and_initial_password_gates(self):
        anonymous=TestClient(app,base_url='https://testserver');self.staff_clients.append(anonymous)
        self.assertEqual(anonymous.get('/api/v1/admin/start').status_code,401)
        anonymous.post('/api/v1/account/login',json={'username':'787100','password':'tf-secret-12345'})
        self.assertEqual(anonymous.get('/api/v1/admin/start').status_code,401)
        self.create_staff({},'start-new');staff,_=self.staff_login('start-new')
        self.assertEqual(staff.get('/api/v1/admin/start').status_code,403)

    def test_staff_with_all_permissions_is_not_administrator(self):
        from lokzeitleiste.accounts.access import MODULES
        _,staff=self.active_staff({key:3 for key in MODULES},'start-all-staff')
        response=staff.get('/api/v1/admin/start')
        self.assertEqual(response.status_code,200,response.text)
        data=response.json()
        self.assertEqual(data['admin_tools'],[])
        self.assertFalse({'phpmyadmin','webmailer'} & {row['id'] for row in data['modules']})
