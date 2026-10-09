import base64
import io
import unittest
from datetime import date
from uuid import uuid4
from PIL import Image
from unittest.mock import patch
from fastapi.testclient import TestClient
import test_accounts
from lokzeitleiste.main import app

class EndDateTest(unittest.TestCase):
    setUp=test_accounts.AccountsTest.setUp
    tearDown=test_accounts.AccountsTest.tearDown
    payload=test_accounts.AccountsTest.payload
    create_staff=test_accounts.AccountsTest.create_staff
    staff_login=test_accounts.AccountsTest.staff_login
    change=test_accounts.AccountsTest.change
    active_staff=test_accounts.AccountsTest.active_staff

    def item(self,**kwargs):
        item=dict(client_id=str(uuid4()),kind='Sonstige Erfassung',date='2026-09-30',end_date='2026-10-02',start='22:00',end='06:00',pause=0,guest=0)
        item.update(kwargs);return item

    def photo(self):
        out=io.BytesIO();Image.new('RGB',(20,20),'green').save(out,format='PNG');return base64.b64encode(out.getvalue()).decode()

    def test_explicit_multi_day_cross_month_totals_and_overlap(self):
        uid,client=self.active_staff({})
        result=client.post('/api/v1/account/worktime/entries',json=self.item())
        self.assertEqual(result.status_code,201,result.text);entry=result.json()
        self.assertEqual(entry['end_date'],'2026-10-02')
        sep=client.get('/api/v1/account/worktime/months/2026/9').json();october=client.get('/api/v1/account/worktime/months/2026/10').json()
        self.assertEqual(sep['month']['totals']['work_without_guest'],120)
        self.assertEqual(october['month']['totals']['work_without_guest'],1800)
        self.assertEqual(october['weeks'][0]['totals']['work'],1920)
        conflicting=self.item(date='2026-10-01',end_date='2026-10-01',start='08:00',end='16:00')
        self.assertEqual(client.post('/api/v1/account/worktime/entries',json=conflicting).status_code,409)
        self.assertEqual(client.patch('/api/v1/account/worktime/entries/'+str(entry['id']),json={'start':'22:00','end':'06:00','end_date':'2026-10-01','expected_updated_at':entry['updated_at'],'reason':'Enddatum korrigiert'}).status_code,200)
        self.assertEqual(client.get('/api/v1/account/worktime/months/2026/10').json()['month']['totals']['work_without_guest'],360)

    def test_old_start_month_far_before_view_and_year_boundary(self):
        uid,client=self.active_staff({})
        item=self.item(date='2026-07-31',end_date='2026-09-02')
        response=client.post('/api/v1/account/worktime/entries',json=item)
        self.assertEqual(response.status_code,201,response.text)
        data=client.get('/api/v1/account/worktime/months/2026/9').json()
        self.assertEqual(data['month']['totals']['work_without_guest'],1800)
        item=self.item(date='2026-12-31',end_date='2027-01-01')
        self.assertEqual(client.post('/api/v1/account/worktime/entries',json=item).status_code,201)
        self.assertEqual(client.get('/api/v1/account/worktime/months/2027/1').json()['month']['totals']['work_without_guest'],360)

    def test_invalid_dates_same_day_and_standby_rules(self):
        uid,client=self.active_staff({})
        invalid=[self.item(end_date='2026-09-29'),self.item(end_date='2026-09-30'),self.item(end_date='2026-09-30',end='22:00'),self.item(kind='Bereitschaft'),self.item(kind='Urlaub')]
        for item in invalid:self.assertEqual(client.post('/api/v1/account/worktime/entries',json=item).status_code,422)
        good=self.item(end_date='2026-09-30',start='08:00',end='16:00')
        self.assertEqual(client.post('/api/v1/account/worktime/entries',json=good).status_code,201)
        self.assertEqual(client.get('/api/v1/account/worktime/months/2026/9').json()['month']['totals']['work_without_guest'],480)

    def test_legacy_upload_retains_explicit_end_date_and_locks(self):
        client=TestClient(app,base_url='https://testserver');self.staff_clients.append(client)
        token=client.post('/api/v1/tf/login',json={'username':'tf-account','password':'tf-secret-12345'}).json()['access_token']
        headers={'Authorization':'Bearer '+token};path='/api/v1/me/months/2026/9/entries';item=self.item()
        response=client.post(path,json={'entries':[item]},headers=headers)
        self.assertEqual(response.status_code,200,response.text)
        legacy=dict(item);legacy.pop('end_date')
        self.assertEqual(client.post(path,json={'entries':[legacy]},headers=headers).status_code,200)
        self.assertEqual(client.get(path,headers=headers).json()[0]['end_date'],'2026-10-02')
        self.assertEqual(client.get('/api/v1/me/months/2026/10/summary',headers=headers).json()['totals']['work_without_guest'],1800)
        entry=self.client.get(f'/api/v1/admin/worktime/users/{self.tf}/months/2026/9').json()['entries'][0]
        locked=self.client.put('/api/v1/admin/worktime/entries/'+str(entry['id'])+'/lock',json={'locked':True,'expected_updated_at':entry['updated_at'],'reason':'Geprüft'})
        self.assertEqual(locked.status_code,200)
        self.assertEqual(client.post(path,json={'entries':[dict(item,end_date='2026-10-03')]},headers=headers).status_code,409)

    def test_profile_and_photo_creation_and_update_are_atomic(self):
        payload=self.payload('office-photo',{});payload['photo_base64']=self.photo()
        result=self.client.post('/api/v1/admin/staff',json=payload)
        self.assertEqual(result.status_code,201,result.text);uid=result.json()['id']
        self.assertEqual(self.client.get(f'/api/v1/admin/staff/{uid}/photo').status_code,200)
        update=self.payload('office-photo',{});update['cost_center']='K-2';update['photo_base64']='invalid'
        self.assertEqual(self.client.put(f'/api/v1/admin/staff/{uid}',json=update).status_code,422)
        staff=next(u for u in self.client.get('/api/v1/admin/staff').json() if u['id']==uid)
        self.assertEqual(staff['cost_center'],'K-001')
        user=next(u for u in self.client.get('/api/v1/admin/tf').json() if u['id']==self.tf)
        update={k:user[k] for k in ('last_name','first_name','personnel_number','target_hours_minutes','vacation_days','birth_date','bahncard','email','federal_state')}
        update['photo_base64']=self.photo();update['last_name']='Mit Foto'
        response=self.client.put(f'/api/v1/admin/tf/{self.tf}',json=update)
        self.assertEqual(response.status_code,200,response.text);self.assertTrue(response.json()['has_photo'])
        self.assertEqual(self.client.get(f'/api/v1/admin/tf/{self.tf}/photo').status_code,200)
        create=dict(update,username='tf-with-photo',password='new-tf-secret-12345',personnel_number='P-PHOTO')
        result=self.client.post('/api/v1/admin/tf',json=create)
        self.assertEqual(result.status_code,201,result.text)
        self.assertEqual(self.client.get('/api/v1/admin/tf/'+str(result.json()['id'])+'/photo').status_code,200)
        _,reader=self.active_staff({'employees':1},'photo-reader')
        self.assertEqual(reader.put(f'/api/v1/admin/tf/{self.tf}',json=update).status_code,403)
        self.assertEqual(self.client.post('/api/v1/admin/staff',json=dict(payload,username='photo-invalid',photo_base64='invalid')).status_code,422)
        self.assertFalse(any(u['username']=='photo-invalid' for u in self.client.get('/api/v1/admin/staff').json()))

    def test_tf_date_only_correction_emails_before_after_dates(self):
        item=self.item()
        response=self.client.post(f'/api/v1/admin/worktime/users/{self.tf}/entries',json=item)
        self.assertEqual(response.status_code,201,response.text);entry=response.json()
        with patch('lokzeitleiste.worktime.service.engine',return_value=self.engine),patch('lokzeitleiste.worktime.service.send_time_change') as send:
            response=self.client.patch(f'/api/v1/admin/tf/{self.tf}/worktime/entries/{entry["id"]}',json={
                'start':item['start'],'end':item['end'],'end_date':'2026-10-01','expected_updated_at':entry['updated_at'],'reason':'Enddatum berichtigt'})
            self.assertEqual(response.status_code,200,response.text)
            self.assertTrue(response.json()['changed']);self.assertEqual(send.call_count,1)
            self.assertIn('Enddatum: 2026-10-02 → 2026-10-01',send.call_args.kwargs['body'])
        history=self.client.get(f'/api/v1/admin/tf/{self.tf}/worktime/changes/history').json()
        self.assertEqual(history[0]['end_date_change'],'2026-10-02 → 2026-10-01')
