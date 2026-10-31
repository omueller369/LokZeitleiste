import io,json,unittest
from uuid import uuid4
from PIL import Image
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select,func
from lokzeitleiste.main import app
from lokzeitleiste.models import WorkEntry,DutyReport,DutyReceipt
import test_work_reports

class DraftTest(unittest.TestCase):
    setUp=test_work_reports.WorkReportsTest.setUp
    tearDown=test_work_reports.WorkReportsTest.tearDown
    payload=test_work_reports.WorkReportsTest.payload
    base='/api/v1/tf/work-report-drafts'
    def save(self,data,revision=0,keys=None,client=None):
        return (client or self.driver).put(self.base+'/'+data['client_id'],json={'expected_revision':revision,'report':data,'receipt_keys':keys or []})
    def test_second_device_edit_conflict_and_no_accounting_until_finalization(self):
        data=self.payload();first=self.save(data);self.assertEqual(first.status_code,200,first.text)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(WorkEntry)),0)
            self.assertEqual(db.scalar(select(func.count()).select_from(DutyReport)),0)
        second=TestClient(app,base_url='https://testserver');self.staff_clients.append(second)
        second.post('/api/v1/account/login',json={'username':'787100','password':'tf-secret-12345'})
        listed=second.get(self.base).json()['drafts'];self.assertEqual(listed[0]['report']['client_id'],data['client_id'])
        changed=dict(data,in_hotel=True,hotel_name='Testhotel');updated=self.save(changed,1,client=second);self.assertEqual(updated.status_code,200,updated.text)
        self.assertEqual(self.save(data,1).status_code,409)
        self.assertEqual(self.driver.post('/api/v1/tf/work-reports',json=data,headers={'X-CTL-Draft-Revision':'1'}).status_code,409)
        self.assertEqual(self.driver.post('/api/v1/tf/work-reports',json=changed).status_code,409)
        final=second.post('/api/v1/tf/work-reports',json=changed,headers={'X-CTL-Draft-Revision':'2'})
        self.assertEqual(final.status_code,201,final.text)
        result=self.driver.get(self.base).json();self.assertEqual(result['drafts'],[]);self.assertEqual(result['finalized'][0]['report_id'],final.json()['id'])
        self.assertEqual(self.save(changed,2).status_code,409)
        self.assertEqual(self.driver.post('/api/v1/tf/work-reports',json=changed,headers={'X-CTL-Draft-Revision':'2'}).status_code,201)
    def test_delete_unsynchronized_draft_and_protect_finalized_report(self):
        data=self.payload();self.assertEqual(self.save(data).status_code,200)
        path=self.base+'/'+data['client_id']
        self.assertEqual(self.driver.delete(path).status_code,200)
        self.assertEqual(self.driver.get(path).status_code,404)
        self.assertEqual(self.driver.delete(path).status_code,200)
        self.assertEqual(self.driver.get(self.base).json()['drafts'],[])
        self.assertEqual(self.save(data).status_code,409)
        data=self.payload();self.assertEqual(self.save(data).status_code,200)
        path=self.base+'/'+data['client_id']
        final=self.driver.post('/api/v1/tf/work-reports',json=data,headers={'X-CTL-Draft-Revision':'1'})
        self.assertEqual(final.status_code,201,final.text)
        self.assertEqual(self.driver.delete(path).status_code,409)
        self.assertEqual(self.driver.get('/api/v1/tf/work-reports/'+str(final.json()['id'])).status_code,200)

    def test_incomplete_pause_is_allowed_only_for_draft(self):
        data=self.payload();data.update(pause_policy=2,actual_pause=0)
        saved=self.save(data);self.assertEqual(saved.status_code,200,saved.text)
        self.assertEqual(saved.json()['report']['actual_pause'],0)
        self.assertEqual(self.driver.get(self.base).json()['drafts'][0]['report']['pause_policy'],2)
        final=self.driver.post('/api/v1/tf/work-reports',json={**data,'check_required_pause':False},headers={'X-CTL-Draft-Revision':'1'})
        self.assertEqual(final.status_code,422,final.text)
        with Session(self.engine) as db:self.assertEqual(db.scalar(select(func.count()).select_from(DutyReport)),0)
        data['actual_pause']=30
        self.assertEqual(self.save(data,1).status_code,200)
        final=self.driver.post('/api/v1/tf/work-reports',json=data,headers={'X-CTL-Draft-Revision':'2'})
        self.assertEqual(final.status_code,201,final.text)

    def test_private_access_and_receipt_handoff(self):
        data=self.payload();file_key=str(uuid4());self.assertEqual(self.save(data,keys=[file_key]).status_code,200)
        path=self.base+'/'+data['client_id']
        self.assertEqual(self.client.get(self.base).status_code,403)
        anonymous=TestClient(app,base_url='https://testserver');self.staff_clients.append(anonymous)
        self.assertEqual(anonymous.get(self.base).status_code,401)
        self.create_tf('787222','DRAFT-OTHER')
        other=TestClient(app,base_url='https://testserver');self.staff_clients.append(other)
        other.post('/api/v1/account/login',json={'username':'787222','password':'tf-secret-12345'})
        self.assertEqual(other.get(self.base).json()['drafts'],[])
        self.assertEqual(other.get(path).status_code,404)
        self.assertEqual(other.get(path+'/files/'+file_key).status_code,404)
        self.assertEqual(self.driver.post('/api/v1/tf/work-reports',json=data,headers={'X-CTL-Draft-Revision':'1'}).status_code,409)
        content=io.BytesIO();Image.new('RGB',(10,10),'blue').save(content,format='PNG');content=content.getvalue()
        upload=self.driver.put(path+'/files/'+file_key,files={'file':('Beleg.png',content,'image/png')});self.assertEqual(upload.status_code,200,upload.text)
        self.assertEqual(anonymous.get(path+'/files/'+file_key).status_code,401)
        self.assertEqual(self.driver.get(path+'/files/'+file_key).content,content)
        with Session(self.engine) as db:self.assertEqual(db.scalar(select(func.count()).select_from(DutyReceipt)),0)
        self.assertFalse(self.send.called)
        final=self.driver.post('/api/v1/tf/work-reports',json=data,headers={'X-CTL-Draft-Revision':'1'});self.assertEqual(final.status_code,201,final.text)
        self.assertEqual(len(self.driver.get('/api/v1/tf/work-reports/'+str(final.json()['id'])+'/receipts').json()),1)
        self.assertTrue(self.send.called)

    def test_removed_draft_receipt_is_not_finalized(self):
        data=self.payload();file_key=str(uuid4());self.assertEqual(self.save(data,keys=[file_key]).status_code,200)
        path=self.base+'/'+data['client_id'];content=io.BytesIO();Image.new('RGB',(5,5),'red').save(content,format='PNG')
        self.assertEqual(self.driver.put(path+'/files/'+file_key,files={'file':('Beleg.png',content.getvalue(),'image/png')}).status_code,200)
        self.assertEqual(self.save(data,1,keys=[]).status_code,200)
        self.assertEqual(self.driver.get(path+'/files/'+file_key).status_code,404)
        final=self.driver.post('/api/v1/tf/work-reports',json=data,headers={'X-CTL-Draft-Revision':'2'})
        self.assertEqual(final.status_code,201,final.text)
        self.assertEqual(self.driver.get('/api/v1/tf/work-reports/'+str(final.json()['id'])+'/receipts').json(),[])
        self.assertFalse(self.send.called)
