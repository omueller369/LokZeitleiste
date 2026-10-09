import io
import unittest
from uuid import uuid4
from PIL import Image
from fastapi.testclient import TestClient
import test_accounts
from lokzeitleiste.main import app

class RecordsTest(unittest.TestCase):
    setUp=test_accounts.AccountsTest.setUp
    tearDown=test_accounts.AccountsTest.tearDown
    payload=test_accounts.AccountsTest.payload
    create_staff=test_accounts.AccountsTest.create_staff
    staff_login=test_accounts.AccountsTest.staff_login
    change=test_accounts.AccountsTest.change
    active_staff=test_accounts.AccountsTest.active_staff

    def item(self,day='2026-09-01',**kw):
        return dict(client_id=str(uuid4()),kind='Sonstige Erfassung',date=day,start='08:00',end='16:00',pause=0,guest=0,**kw)
    def lock(self,client,entry,locked=True):
        return client.put(f'/api/v1/admin/worktime/entries/{entry["id"]}/lock',json={
            'locked':locked,'reason':'Monat geprüft','expected_updated_at':entry['updated_at']})
    def edit(self,client,entry,path='/api/v1/account/worktime/entries/'):
        return client.patch(path+str(entry['id']),json={'start':'08:00','end':'17:00',
            'reason':'Korrektur','expected_updated_at':entry['updated_at']})

    def test_own_staff_entry_totals_idempotency_and_isolation(self):
        uid,client=self.active_staff({})
        item=self.item();result=client.post('/api/v1/account/worktime/entries',json=item)
        self.assertEqual(result.status_code,201,result.text);entry=result.json()
        self.assertEqual(client.post('/api/v1/account/worktime/entries',json=item).json()['id'],entry['id'])
        self.assertEqual(client.post('/api/v1/account/worktime/entries',json=dict(item,end='17:00')).status_code,409)
        data=client.get('/api/v1/account/worktime/months/2026/9').json()
        self.assertEqual(data['month']['totals']['work_without_guest'],480)
        self.assertEqual(self.edit(client,entry).status_code,200)
        data=client.get('/api/v1/account/worktime/months/2026/9').json()
        self.assertEqual(data['month']['totals']['work_without_guest'],540)
        _,other=self.active_staff({},'other-office')
        self.assertEqual(self.edit(other,data['entries'][0]).status_code,404)
        self.assertEqual(other.get('/api/v1/account/worktime/months/2026/9').json()['entries'],[])
        self.assertEqual(client.post(f'/api/v1/admin/worktime/users/{self.tf}/entries',json=self.item()).status_code,403)

    def test_lock_permissions_stale_edit_and_unlock(self):
        uid,writer=self.active_staff({'worktime':2})
        _,reader=self.active_staff({'worktime':1},'reader-office')
        entry=writer.post('/api/v1/account/worktime/entries',json=self.item()).json()
        self.assertEqual(self.lock(reader,entry).status_code,403)
        locked=self.lock(writer,entry);self.assertEqual(locked.status_code,200,locked.text)
        self.assertEqual(self.edit(writer,locked.json()).status_code,409)
        self.assertEqual(self.lock(writer,locked.json(),False).status_code,403)
        self.assertEqual(self.lock(self.client,entry,False).status_code,409)
        unlocked=self.lock(self.client,locked.json(),False)
        self.assertEqual(unlocked.status_code,200,unlocked.text)
        self.assertEqual(self.edit(writer,unlocked.json()).status_code,200)
        audits=self.client.get(f'/api/v1/admin/worktime/users/{uid}/audit').json()
        self.assertEqual({a['action'] for a in audits},{'manual_created','manual_updated','locked','unlocked'})

    def test_tf_lock_blocks_old_upload_batch_and_admin_correction(self):
        tf=TestClient(app,base_url='https://testserver');self.staff_clients.append(tf)
        tf.post('/api/v1/account/login',json={'username':'tf-account','password':'tf-secret-12345'})
        item=self.item();entry=tf.post('/api/v1/account/worktime/entries',json=item)
        self.assertEqual(entry.status_code,201,entry.text)
        locked=self.lock(self.client,entry.json()).json()
        self.assertEqual(self.edit(tf,locked).status_code,409)
        self.assertEqual(self.edit(self.client,locked,f'/api/v1/admin/tf/{self.tf}/worktime/entries/').status_code,409)
        token=tf.post('/api/v1/tf/login',json={'username':'tf-account','password':'tf-secret-12345'}).json()['access_token']
        headers={'Authorization':'Bearer '+token};path='/api/v1/me/months/2026/9/entries'
        self.assertEqual(tf.post(path,json={'entries':[item]},headers=headers).status_code,200)
        self.assertEqual(tf.post(path,json={'entries':[self.item('2026-09-02'),dict(item,end='17:00')]},headers=headers).status_code,409)
        self.assertEqual(len(tf.get(path,headers=headers).json()),1)
        self.assertEqual(self.send_mock.call_count,2)

    def test_overlap_and_overnight_absence_rejected(self):
        uid,client=self.active_staff({})
        first=self.item();self.assertEqual(client.post('/api/v1/account/worktime/entries',json=first).status_code,201)
        self.assertEqual(client.post('/api/v1/account/worktime/entries',json=self.item()).status_code,409)
        holiday=self.item('2026-10-01');holiday['kind']='Urlaub'
        self.assertEqual(client.post('/api/v1/account/worktime/entries',json=holiday).status_code,201)
        night=self.item('2026-09-30');night.update(start='22:00',end='06:00')
        self.assertEqual(client.post('/api/v1/account/worktime/entries',json=night).status_code,409)
        self.assertEqual(len(client.get('/api/v1/account/worktime/months/2026/9').json()['entries']),1)

    def test_photos_normalize_private_and_module_permissions(self):
        uid,client=self.active_staff({'employees':1,'staff':1})
        output=io.BytesIO();Image.new('RGBA',(900,300),(255,0,0,80)).save(output,format='PNG')
        content=output.getvalue();path=f'/api/v1/admin/tf/{self.tf}/photo'
        self.assertEqual(client.post(path,files={'file':('a.png',content,'image/png')}).status_code,403)
        self.assertEqual(self.client.post(path,files={'file':('a.png',content,'image/png')}).status_code,200)
        response=client.get(path);self.assertEqual(response.status_code,200);self.assertEqual(response.headers['cache-control'],'private, no-store')
        with Image.open(io.BytesIO(response.content)) as img:
            self.assertEqual(img.format,'JPEG');self.assertEqual(img.size,(640,213));self.assertFalse(img.getexif())
        for route in [path,f'/api/v1/admin/staff/{uid}/photo']:
            self.assertEqual(self.client.post(route,files={'file':('a.svg',b'<svg/>','image/svg+xml')}).status_code,422)
        self.assertEqual(self.client.post(path,files={'file':('big.png',b'x'*(5*1024*1024+1))}).status_code,413)
        _,none=self.active_staff({},'no-photos')
        self.assertEqual(none.get(path).status_code,403)
        self.assertEqual(self.client.delete(path).status_code,200);self.assertEqual(self.client.get(path).status_code,404)

    def test_bulk_plan_atomic_across_months(self):
        base=f'/api/v1/admin/tf/{self.tf}/plan/2026'
        data={'days':[{'date':'2026-09-30','kind':'Urlaub'},{'date':'2026-10-01','kind':'Ruhetag'}],
              'expected_revisions':{'9':0,'10':0}}
        response=self.client.post(base+'/bulk',json=data);self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['changed_days'],2)
        stale={'days':[{'date':'2026-08-31','kind':'Urlaub'},{'date':'2026-09-30','kind':'Ruhetag'}],
               'expected_revisions':{'8':0,'9':0}}
        self.assertEqual(self.client.post(base+'/bulk',json=stale).status_code,409)
        self.assertEqual(self.client.get(base+'/8').json()['vacation_days'],0)
        _,reader=self.active_staff({'planning':1})
        self.assertEqual(reader.post(base+'/bulk',json=data).status_code,403)
