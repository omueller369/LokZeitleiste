import copy,json,unittest
from uuid import uuid4
from sqlalchemy.orm import Session
from sqlalchemy import select
import test_work_reports
from lokzeitleiste.models import WorkEntry,WorkEntryLock,WorkEntryAudit,DutyReport


class TrainJourneysTest(unittest.TestCase):
    setUp=test_work_reports.WorkReportsTest.setUp
    tearDown=test_work_reports.WorkReportsTest.tearDown
    payload=test_work_reports.WorkReportsTest.payload
    create=test_work_reports.WorkReportsTest.create

    def train(self,number='123ABC'):
        return dict(id=str(uuid4()),train_number=number,start_station='BHF',end_station='LL',start_at='2026-10-12T09:00',end_at='2026-10-12T10:00',events=[self.event()])
    def event(self):
        return dict(id=str(uuid4()),reason='Pause',reason_detail='',cause='CTL Logistics DE',cause_detail='',station='BHF',start_at='2026-10-12T10:05',end_at='2026-10-12T10:20')
    def data(self):
        value=self.payload();value['trips']=[];value['train_journeys']=[self.train()];return value
    def update(self,report,trains,revision=0):
        return self.driver.put(f'/api/v1/tf/work-reports/{report}/train-journeys',json={'expected_revision':revision,'train_journeys':trains})

    def test_multiple_trains_and_pause_documentation_without_work_deduction(self):
        data=self.data();data['train_journeys'].append(dict(self.train(),events=[]))
        report=self.create(data);self.assertEqual(len(report['train_journeys']),2)
        self.assertEqual([t['train_number'] for t in report['train_journeys']],['123ABC','123ABC'])
        self.assertNotEqual(report['train_journeys'][0]['id'],report['train_journeys'][1]['id'])
        self.assertEqual(report['documented_pause_minutes'],45)
        self.assertEqual(report['train_journeys'][0]['start_station_name'],'Berlin Beispiel')
        self.assertEqual(report['train_journeys'][0]['events'][0]['station_name'],'Berlin Beispiel')
        self.assertEqual(self.create(data)['id'],report['id'])
        month=self.driver.get('/api/v1/tf/work-reports/month/2026/10').json()
        self.assertEqual((month['work_minutes'],month['pause_minutes']),(480,45))
        with Session(self.engine) as db:self.assertEqual(db.get(WorkEntry,report['entry_id']).pause_minutes,45)

    def test_validation_and_unique_identifiers(self):
        for number in ('','1234567890123','12-AB'):
            data=self.data();data['train_journeys'][0]['train_number']=number
            self.assertEqual(self.driver.post('/api/v1/tf/work-reports',json=data).status_code,422)
        for field,value in [('reason','invalid'),('cause','invalid'),('station','UNKNOWN'),('end_at','2026-10-12T10:00'),('start_at','2026-10-12T08:00')]:
            data=self.data();data['train_journeys'][0]['events'][0][field]=value
            self.assertEqual(self.driver.post('/api/v1/tf/work-reports',json=data).status_code,422)
        for field,size in [('reason_detail',257),('cause_detail',51)]:
            data=self.data();event=data['train_journeys'][0]['events'][0];event['reason']=event['cause']='sonstiges';event['reason_detail']=event['cause_detail']='Description';event[field]='X'*size
            self.assertEqual(self.driver.post('/api/v1/tf/work-reports',json=data).status_code,422)
        data=self.data();data['train_journeys'].append(copy.deepcopy(data['train_journeys'][0]))
        self.assertEqual(self.driver.post('/api/v1/tf/work-reports',json=data).status_code,422)
        data=self.data();data['train_journeys'][0]['events'].append(dict(self.event(),id=str(uuid4())))
        self.assertEqual(self.driver.post('/api/v1/tf/work-reports',json=data).status_code,422)
        data=self.data();data['kind']='Urlaub';data['actual_pause']=0
        self.assertEqual(self.driver.post('/api/v1/tf/work-reports',json=data).status_code,422)

    def test_event_before_departure_and_free_text(self):
        data=self.data();event=data['train_journeys'][0]['events'][0]
        event.update(reason='sonstiges',reason_detail='X'*256,cause='sonstiges',cause_detail='Y'*50,start_at='2026-10-12T09:00',end_at='2026-10-12T09:05')
        data['train_journeys'][0]['start_at']='2026-10-12T09:30'
        report=self.create(data);self.assertEqual(report['documented_pause_minutes'],30)
        self.assertEqual(report['train_journeys'][0]['events'][0]['reason_detail'],'X'*256)

    def test_edit_after_sync_revision_retry_lock_and_administrative_changes(self):
        report=self.create(self.data());trains=copy.deepcopy(report['train_journeys'])
        trains[0]['events'][0]['end_at']='2026-10-12T10:25'
        updated=self.update(report['id'],trains);self.assertEqual(updated.status_code,200,updated.text)
        self.assertEqual(updated.json()['documented_pause_minutes'],50);self.assertEqual(updated.json()['train_revision'],1)
        self.assertEqual(self.update(report['id'],trains).json()['train_revision'],1)
        changed=copy.deepcopy(trains);changed[0]['events'][0]['end_at']='2026-10-12T10:30'
        self.assertEqual(self.update(report['id'],changed).status_code,409)
        self.assertEqual(self.client.put(f"/api/v1/tf/work-reports/{report['id']}/train-journeys",json={'expected_revision':1,'train_journeys':changed}).status_code,403)
        with Session(self.engine) as db:
            self.assertEqual(len(db.scalars(select(WorkEntryAudit).where(WorkEntryAudit.action=='work_report_trains_updated')).all()),1)
            db.add(WorkEntryLock(entry_id=report['entry_id'],locked=True,actor_id=1,reason='Checked'));db.commit()
        self.assertEqual(self.update(report['id'],changed,1).status_code,409)
        with Session(self.engine) as db:
            db.get(WorkEntryLock,report['entry_id']).locked=False
            db.get(WorkEntry,report['entry_id']).end_time='16:00';db.commit()
        self.assertEqual(self.update(report['id'],changed,1).status_code,409)
        self.assertFalse(self.driver.get(f"/api/v1/tf/work-reports/{report['id']}").json()['train_editable'])

    def test_legacy_records_and_old_initial_post_retries_after_train_edits(self):
        data=self.payload();data['trips']=[];report=self.create(data)
        with Session(self.engine) as db:
            row=db.get(DutyReport,report['id']);payload=json.loads(row.payload_json);payload.pop('train_journeys');row.payload_json=json.dumps(payload);db.commit()
        self.assertEqual(self.create(data)['train_journeys'],[])
        changed=self.update(report['id'],[self.train()]);self.assertEqual(changed.status_code,200,changed.text)
        self.assertEqual(len(self.create(data)['train_journeys']),1)
