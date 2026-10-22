import json,unittest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
import test_train_journeys,test_accounts
from lokzeitleiste.main import app
from lokzeitleiste.models import AppDefaultValue,AppDefaultSeed,DutyReport,TrainGpsRecording
from lokzeitleiste.app_defaults import ensure_defaults

BASE='/api/v1/admin/app-defaults'
class AppDefaultsTest(unittest.TestCase):
    setUp=test_train_journeys.TrainJourneysTest.setUp
    tearDown=test_train_journeys.TrainJourneysTest.tearDown
    payload=test_train_journeys.TrainJourneysTest.payload
    create=test_train_journeys.TrainJourneysTest.create
    train=test_train_journeys.TrainJourneysTest.train
    event=test_train_journeys.TrainJourneysTest.event
    data=test_train_journeys.TrainJourneysTest.data
    update=test_train_journeys.TrainJourneysTest.update
    create_staff=test_accounts.AccountsTest.create_staff
    staff_login=test_accounts.AccountsTest.staff_login
    change=test_accounts.AccountsTest.change
    active_staff=test_accounts.AccountsTest.active_staff
    # Staff helpers expect their profile builder under payload, so build explicitly below.
    def catalogue(self):
        response=self.client.get(BASE);self.assertEqual(response.status_code,200,response.text);return response.json()
    def add(self,category,label):
        result=self.client.post(BASE+'/'+category,json=dict(label=label,active=True));self.assertEqual(result.status_code,201,result.text);return result.json()
    def change_value(self,row,**changes):
        response=self.client.put(BASE+'/value/'+str(row['id']),json={**dict(label=row['label'],active=row['active'],expected_revision=row['revision']),**changes});return response
    def remove(self,row):return self.client.delete(BASE+'/value/'+str(row['id']),params={'expected_revision':row['revision']})

    def test_initial_defaults_and_delete_not_recreated_by_update(self):
        rows=self.catalogue();self.assertEqual(len(rows),20)
        self.assertEqual([r['value'] for r in rows if r['category']=='cause'],['CTL','DB InfraGo','Dritte Stelle','sonstiges'])
        self.assertTrue(all(r['active'] and not r['used'] for r in rows))
        row=next(r for r in rows if r['value']=='V3');self.assertEqual(self.remove(row).status_code,200)
        with Session(self.engine) as db:ensure_defaults(db)
        self.assertEqual(len(self.catalogue()),19)
        self.assertEqual(len(self.driver.get('/api/v1/tf/app-defaults').json()),19)

    def test_crud_duplicates_revision_and_stable_keys(self):
        row=self.add('reason','Neuer Grund');original=row['value']
        duplicate=self.client.post(BASE+'/reason',json={'label':' neuer grund '});self.assertEqual(duplicate.status_code,409)
        changed=self.change_value(row,label='Umbenannter Grund',active=False);self.assertEqual(changed.status_code,200,changed.text)
        new=changed.json();self.assertEqual(new['value'],original);self.assertEqual(new['revision'],2)
        self.assertEqual(self.change_value(row,label='Veraltet').status_code,409)
        self.assertEqual(self.remove(new).status_code,200)
        self.assertEqual(self.client.post(BASE+'/bad',json={'label':'Test'}).status_code,422)
        self.assertEqual(self.client.post(BASE+'/reason',json={'label':'  '}).status_code,422)

    def test_used_values_block_delete_allow_disable_and_preserve_old_events(self):
        reason=self.add('reason','Signalprüfung');cause=self.add('cause','Infrastrukturpartner')
        data=self.data();event=data['train_journeys'][0]['events'][0];event.update(reason=reason['value'],cause=cause['value'],reason_label='spoofed',cause_label='spoofed')
        report=self.create(data);saved=report['train_journeys'][0]['events'][0]
        self.assertEqual((saved['reason_label'],saved['cause_label']),('Signalprüfung','Infrastrukturpartner'))
        used={r['id']:r for r in self.catalogue()}
        for row in [reason,cause]:
            self.assertTrue(used[row['id']]['used']);self.assertEqual(self.remove(row).status_code,409)
            disabled=self.change_value(row,active=False);self.assertEqual(disabled.status_code,200,disabled.text)
        trains=report['train_journeys'];trains[0]['events'][0]['end_at']='2026-10-12T10:25'
        changed=self.update(report['id'],trains);self.assertEqual(changed.status_code,200,changed.text)
        new_event=dict(trains[0]['events'][0],id=str(uuid4()),start_at='2026-10-12T10:30',end_at='2026-10-12T10:40');trains[0]['events'].append(new_event)
        self.assertEqual(self.update(report['id'],trains,revision=1).status_code,422)
        # Usage remains a deletion lock even if reports are later removed by a TF reset.
        from lokzeitleiste.accounts.seed_demo_tf import delete_tf_records
        with Session(self.engine) as db:delete_tf_records(db);db.commit()
        row=next(r for r in self.catalogue() if r['id']==reason['id']);self.assertEqual(self.remove(row).status_code,409)

    def test_update_migrates_historical_reports_and_gps_without_rewriting(self):
        report=self.create(self.data())
        with Session(self.engine) as db:
            db.query(AppDefaultValue).delete();db.query(AppDefaultSeed).delete()
            original=db.get(DutyReport,report['id']).payload_json
            db.add(TrainGpsRecording(owner_id=self.tf,journey_id=str(uuid4()),payload_json=json.dumps({'points':[],'reasons':{'s0':{'reason':'Legacy GPS'}}}),revision=1));db.commit()
            ensure_defaults(db)
            self.assertEqual(db.get(DutyReport,report['id']).payload_json,original)
        rows=self.catalogue()
        self.assertTrue(next(r for r in rows if r['value']=='Pause')['used'])
        legacy=next(r for r in rows if r['value']=='Legacy GPS');self.assertTrue(legacy['used']);self.assertFalse(legacy['active']);self.assertEqual(self.remove(legacy).status_code,409)

    def test_permissions_and_tf_access(self):
        self.catalogue()
        account=test_accounts.AccountsTest.payload(self,username='config-office',grants={'app_defaults':1})
        created=self.client.post('/api/v1/admin/staff',json=account);self.assertEqual(created.status_code,201,created.text)
        staff,login=self.staff_login('config-office');self.change(staff);staff.post('/api/v1/admin/login',json={'username':'config-office','password':'personal-secret-67890'})
        self.assertEqual(staff.get(BASE).status_code,200)
        self.assertEqual(staff.post(BASE+'/reason',json={'label':'Forbidden'}).status_code,403)
        self.assertEqual(self.driver.get(BASE).status_code,401)
        self.assertEqual(self.driver.get('/api/v1/tf/app-defaults').status_code,200)
        anonymous=TestClient(app,base_url='https://testserver');self.addCleanup(anonymous.close)
        self.assertEqual(anonymous.get('/api/v1/tf/app-defaults').status_code,401)

    def test_gps_usage_prevents_delete_and_inactive_new_selection(self):
        import test_gps
        reason=self.add('reason','GPS Sonderhalt');path='/api/v1/tf/gps/'+str(uuid4())
        saved=self.driver.put(path,json=dict(train_number='123',points=test_gps.points(),ended=True,expected_revision=0));self.assertEqual(saved.status_code,200,saved.text)
        chosen=self.driver.put(path+'/stations',json={'expected_revision':1,'stations':{},'reasons':{'s0':{'reason':reason['value']}}})
        self.assertEqual(chosen.status_code,200,chosen.text)
        self.assertEqual(chosen.json()['reasons']['s0']['label'],'GPS Sonderhalt')
        self.assertEqual(self.remove(reason).status_code,409)
        self.assertEqual(self.change_value(reason,active=False).status_code,200)
        existing=self.driver.put(path+'/stations',json={'expected_revision':2,'stations':{},'reasons':{'s0':{'reason':reason['value']}}});self.assertEqual(existing.status_code,200,existing.text)
        new=self.driver.put(path+'/stations',json={'expected_revision':3,'stations':{},'reasons':{'start':{'reason':reason['value']}}});self.assertEqual(new.status_code,422)

    def test_writer_can_edit_but_delete_requires_administration(self):
        account=test_accounts.AccountsTest.payload(self,username='config-writer',grants={'app_defaults':2})
        self.assertEqual(self.client.post('/api/v1/admin/staff',json=account).status_code,201)
        staff,_=self.staff_login('config-writer');self.change(staff);staff.post('/api/v1/admin/login',json={'username':'config-writer','password':'personal-secret-67890'})
        added=staff.post(BASE+'/cause',json={'label':'Testpartner'});self.assertEqual(added.status_code,201,added.text);row=added.json()
        path=BASE+'/value/'+str(row['id'])
        self.assertEqual(staff.put(path,json={'label':'Neuer Partner','active':False,'expected_revision':1}).status_code,200)
        self.assertEqual(staff.delete(path,params={'expected_revision':2}).status_code,403)
        self.assertEqual(self.client.delete(path,params={'expected_revision':2}).status_code,200)
