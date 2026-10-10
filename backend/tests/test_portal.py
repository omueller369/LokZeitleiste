import unittest
from datetime import date
from sqlalchemy.orm import Session
import test_accounts
from lokzeitleiste.models import ShiftAssignment


class PortalTest(unittest.TestCase):
    setUp=test_accounts.AccountsTest.setUp
    tearDown=test_accounts.AccountsTest.tearDown
    payload=test_accounts.AccountsTest.payload
    create_staff=test_accounts.AccountsTest.create_staff
    staff_login=test_accounts.AccountsTest.staff_login
    change=test_accounts.AccountsTest.change
    active_staff=test_accounts.AccountsTest.active_staff

    def model(self):
        r=self.client.post('/api/v1/admin/shifts/models',json={'name':'2 Arbeit / 1 Ruhe','blocks':[{'kind':'Arbeitstag','days':2},{'kind':'Ruhetag','days':1}]})
        self.assertEqual(r.status_code,201,r.text);return r.json()

    def test_all_employee_directory_permission_and_redaction(self):
        uid=self.create_staff({'directory':1})
        users=self.client.get('/api/v1/admin/directory').json()
        self.assertEqual({u['role'] for u in users},{'tf','staff'})
        self.assertEqual({u['id'] for u in users},{self.tf,uid})
        self.assertNotIn('password_hash',str(users));self.assertNotIn('birth_date',str(users))
        _,reader=self.active_staff({'directory':1},'roster-reader')
        self.assertEqual(reader.get('/api/v1/admin/directory').status_code,200)
        self.assertEqual(reader.get('/api/v1/admin/staff').status_code,403)
        _,restricted=self.active_staff({'employees':1},'roster-denied')
        self.assertEqual(restricted.get('/api/v1/admin/directory').status_code,403)

    def test_shift_cycle_year_boundary_preserve_vacation_and_snapshot(self):
        model=self.model()
        plan=f'/api/v1/admin/tf/{self.tf}/plan'
        self.assertEqual(self.client.put(plan+'/2027/1',json={'expected_revision':0,'days':[{'date':'2027-01-02','kind':'Urlaub'}]}).status_code,200)
        payload=dict(model_id=model['id'],tf_id=self.tf,start='2026-12-30',end='2027-01-05',cycle_start='2026-12-30',expected_model_revision=1)
        response=self.client.post('/api/v1/admin/shifts/preview',json=payload)
        self.assertEqual(response.status_code,200,response.text);preview=response.json()
        self.assertEqual([d['new_kind'] for d in preview['days']],['Arbeitstag','Arbeitstag','Ruhetag','Arbeitstag','Arbeitstag','Ruhetag','Arbeitstag'])
        self.assertEqual(preview['skipped_days'],1)
        payload['expected_revisions']=preview['expected_revisions']
        response=self.client.post('/api/v1/admin/shifts/assign',json=payload)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['changed_days'],6)
        jan=self.client.get(plan+'/2027/1').json()
        self.assertTrue(jan['days'][0]['is_holiday']);self.assertEqual(jan['days'][0]['target_minutes'],0)
        self.assertEqual(jan['days'][1]['kind'],'Urlaub')
        self.assertEqual(jan['days'][2]['kind'],'Arbeitstag')
        self.assertEqual(self.client.put('/api/v1/admin/shifts/models/'+str(model['id']),json={'name':'Geändert','blocks':[{'kind':'Ruhetag','days':1}],'expected_revision':1}).status_code,200)
        self.assertEqual(self.client.get(plan+'/2027/1').json()['days'][2]['kind'],'Arbeitstag')
        history=self.client.get('/api/v1/admin/shifts/assignments').json()
        self.assertEqual(history[0]['model']['name'],model['name'])
        self.assertEqual(self.client.post('/api/v1/admin/shifts/preview',json=payload).status_code,409)

    def test_shift_revision_conflict_rolls_back_all_years_and_overwrite(self):
        model=self.model();payload=dict(model_id=model['id'],tf_id=self.tf,start='2026-12-31',end='2027-01-02',cycle_start='2026-12-31',expected_model_revision=1,overwrite=True)
        preview=self.client.post('/api/v1/admin/shifts/preview',json=payload).json()
        payload['expected_revisions']=preview['expected_revisions']
        plan=f'/api/v1/admin/tf/{self.tf}/plan'
        self.client.put(plan+'/2027/1',json={'expected_revision':0,'days':[{'date':'2027-01-02','kind':'Urlaub'}]})
        self.assertEqual(self.client.post('/api/v1/admin/shifts/assign',json=payload).status_code,409)
        self.assertEqual(self.client.get(plan+'/2026/12').json()['days'][-1]['kind'],'Ungeplant')
        with Session(self.engine) as db:self.assertEqual(db.query(ShiftAssignment).count(),0)
        payload['expected_revisions']=self.client.post('/api/v1/admin/shifts/preview',json=payload).json()['expected_revisions']
        self.assertEqual(self.client.post('/api/v1/admin/shifts/assign',json=payload).status_code,200)
        self.assertEqual(self.client.get(plan+'/2027/1').json()['days'][1]['kind'],'Ruhetag')

    def test_shift_permissions_and_invalid_cycle(self):
        model=self.model()
        _,reader=self.active_staff({'shifts':1,'planning':1},'shift-reader')
        self.assertEqual(reader.get('/api/v1/admin/shifts/models').status_code,200)
        self.assertEqual(reader.post('/api/v1/admin/shifts/models',json={'name':'No','blocks':[]}).status_code,403)
        _,writer=self.active_staff({'shifts':2},'shift-model-only')
        payload=dict(model_id=model['id'],tf_id=self.tf,start='2026-01-01',end='2026-01-02',cycle_start='2026-01-01',expected_model_revision=1)
        self.assertEqual(writer.post('/api/v1/admin/shifts/assign',json=payload).status_code,403)
        for blocks in [[],[{'kind':'Urlaub','days':1}],[{'kind':'Arbeitstag','days':0}],[{'kind':'Arbeitstag','days':366},{'kind':'Ruhetag','days':1}]]:
            self.assertEqual(self.client.post('/api/v1/admin/shifts/models',json={'name':'Invalid','blocks':blocks}).status_code,422)
