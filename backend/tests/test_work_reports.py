import io,json,unittest
from datetime import date,datetime,timedelta
from uuid import uuid4
from unittest.mock import patch
from fastapi.testclient import TestClient
from PIL import Image
from reportlab.pdfgen.canvas import Canvas
from sqlalchemy import select
from sqlalchemy.orm import Session
import test_accounts
from lokzeitleiste.main import app
from lokzeitleiste.models import DutyReport,DutyReceipt,DutyGuestTrip,WorkEntry,WorkEntryLock,RailwayStation,User,UserLocale,PlanDay,PlanMonth
from lokzeitleiste.work_reports.schemas import minimum_pause,ReportIn
from lokzeitleiste.work_reports.receipts import process_receipt,validate_receipt
from lokzeitleiste.accounts.seed_demo_tf import replace_all_tf


class WorkReportsTest(unittest.TestCase):
    tearDown=test_accounts.AccountsTest.tearDown
    def setUp(self):
        test_accounts.AccountsTest.setUp(self)
        with self.engine.connect() as connection:connection.exec_driver_sql('PRAGMA foreign_keys=ON')
        self.driver=TestClient(app,base_url='https://testserver');self.staff_clients.append(self.driver)
        self.driver.post('/api/v1/account/login',json={'username':'787100','password':'tf-secret-12345'})
        self.engine_patch2=patch('lokzeitleiste.work_reports.receipts.engine',return_value=self.engine);self.engine_patch2.start();self.addCleanup(self.engine_patch2.stop)
        self.mail=patch('lokzeitleiste.work_reports.receipts._send_message');self.send=self.mail.start();self.addCleanup(self.mail.stop)
        self.env=patch.dict('os.environ',{'WORK_REPORT_RECEIPT_EMAIL':'omueller369@gmail.com','SMTP_HOST':'mock','SMTP_FROM':'test@example.com'});self.env.start();self.addCleanup(self.env.stop)
        with Session(self.engine) as db:db.add_all([RailwayStation(code='BHF',name='Berlin Beispiel'),RailwayStation(code='LL',name='Leipzig Beispiel')]);db.commit()
    def payload(self,start='2026-10-12T09:00',end='2026-10-12T17:00'):
        return dict(client_id=str(uuid4()),start_at=start,end_at=end,actual_pause=30,overrun_reason='',trips=[dict(start_station='BHF',end_station='LL',start_at=start,end_at=(datetime.fromisoformat(start)+timedelta(hours=1)).isoformat(timespec='minutes'),transport='train',transport_detail='')])
    def create(self,data=None):
        result=self.driver.post('/api/v1/tf/work-reports',json=data or self.payload());self.assertEqual(result.status_code,201,result.text);return result.json()

    def test_guest_self_payer_roundtrip_and_legacy_retry(self):
        data=self.payload();data['trips'][0]['self_payer']=True
        report=self.create(data)
        self.assertTrue(report['trips'][0]['self_payer'])
        self.assertEqual(self.create(data)['id'],report['id'])
        self.assertTrue(self.driver.get(f"/api/v1/tf/work-reports/{report['id']}").json()['trips'][0]['self_payer'])
        month=self.driver.get('/api/v1/tf/work-reports/month/2026/10').json()
        self.assertTrue(month['reports'][0]['trips'][0]['self_payer'])
        with Session(self.engine) as db:
            row=db.get(DutyReport,report['id']);payload=json.loads(row.payload_json)
            payload['trips'][0].pop('self_payer');row.payload_json=json.dumps(payload);db.commit()
        data['trips'][0].pop('self_payer')
        self.assertFalse(self.create(data)['trips'][0]['self_payer'])
        data['trips'][0]['self_payer']=True
        self.assertEqual(self.driver.post('/api/v1/tf/work-reports',json=data).status_code,409)
    def pdf(self):
        out=io.BytesIO();canvas=Canvas(out);canvas.drawString(20,700,'Fiktiver Beleg');canvas.showPage();canvas.save();return out.getvalue()
    def upload(self,report,content=None,name='beleg.pdf'):
        return self.driver.post(f'/api/v1/tf/work-reports/{report}/receipts',files={'file':(name,content or self.pdf(),'application/pdf')})
    def test_station_fulltext_snapshot_and_optional_receipts(self):
        with Session(self.engine) as db:
            db.add_all([RailwayStation(code=f'A{i:02}',name='Halle Test') for i in range(25)]);db.commit()
        self.assertEqual(self.driver.get('/api/v1/tf/work-reports/stations',params={'q':'LL'}).json()[0]['code'],'LL')
        rows=self.driver.get('/api/v1/tf/work-reports/stations',params={'q':'beispiel'}).json()
        self.assertEqual({r['code'] for r in rows},{'BHF','LL'})
        self.assertEqual(self.driver.get('/api/v1/tf/work-reports/stations',params={'q':'%'}).json(),[])
        data=self.payload();data['trips'][0]['start_station_name']='Untrusted name'
        report=self.create(data)
        self.assertEqual(report['trips'][0]['start_station_name'],'Berlin Beispiel')
        self.assertEqual(report['trips'][0]['end_station_name'],'Leipzig Beispiel')
        self.assertEqual(self.driver.get(f"/api/v1/tf/work-reports/{report['id']}/receipts").json(),[])
        with Session(self.engine) as db:
            db.get(RailwayStation,'BHF').name='New catalog name';db.commit()
        self.assertEqual(self.create(data)['trips'][0]['start_station_name'],'Berlin Beispiel')
        # Old records remain readable and retryable without a data migration.
        with Session(self.engine) as db:
            row=db.get(DutyReport,report['id']);payload=json.loads(row.payload_json)
            for trip in payload['trips']:
                trip.pop('start_station_name');trip.pop('end_station_name')
            row.payload_json=json.dumps(payload);db.commit()
        self.assertEqual(self.create(data)['id'],report['id'])
        self.assertEqual(self.driver.get(f"/api/v1/tf/work-reports/{report['id']}").json()['trips'][0]['start_station_name'],'New catalog name')

    def test_pause_boundaries_and_reason(self):
        for duration,expected in [(360,0),(361,30),(539,30),(540,45),(541,45),(599,45),(600,45),(601,46),(660,105),(720,165),(721,166),(780,225)]:self.assertEqual(minimum_pause(duration),expected)
        data=self.payload(end='2026-10-12T22:00')
        self.assertEqual(self.driver.post('/api/v1/tf/work-reports',json=data).status_code,422)
        data['overrun_reason']='Verspätete Ablösung';report=self.create(data);self.assertEqual(report['duration_minutes'],780);self.assertEqual(report['minimum_pause_minutes'],225)
        for name in ('start_at','end_at'):
            invalid=dict(data);invalid[name]=invalid[name]+':10';self.assertEqual(self.driver.post('/api/v1/tf/work-reports',json=invalid).status_code,422)
    def test_new_pause_policy_enforces_only_the_mandatory_part(self):
        from pydantic import ValidationError
        start=datetime(2026,10,12,9)
        for duration,required,recommended in [(360,0,0),(361,30,30),(539,30,30),(540,45,45),(600,45,45),(601,45,46),(690,45,135),(720,45,165)]:
            data=self.payload(start=start.isoformat(timespec='minutes'),end=(start+timedelta(minutes=duration)).isoformat(timespec='minutes'))
            data.update(trips=[],pause_policy=2,actual_pause=required)
            self.assertEqual(ReportIn.model_validate(data).actual_pause,required)
            self.assertEqual(minimum_pause(duration),recommended)
            if required:
                with self.assertRaises(ValidationError):ReportIn.model_validate(dict(data,actual_pause=required-1))
        data=self.payload();data.update(trips=[],pause_policy=1,actual_pause=0)
        self.assertEqual(ReportIn.model_validate(data).pause_policy,1)
        data.update(kind='Bereitschaft',pause_policy=2)
        self.assertEqual(ReportIn.model_validate(data).actual_pause,0)

    def test_hotel_and_performed_minutes_roundtrip_without_absence_credit(self):
        data=self.payload(end='2026-10-12T15:00');data.update(trips=[],actual_pause=0,pause_policy=2,in_hotel=True,hotel_name='  Testhotel  ')
        report=self.create(data)
        self.assertTrue(report['in_hotel']);self.assertEqual(report['hotel_name'],'Testhotel')
        self.assertEqual(self.create(data)['id'],report['id'])
        reread=self.driver.get('/api/v1/tf/work-reports/'+str(report['id'])).json()
        self.assertEqual(reread['hotel_name'],'Testhotel')
        vacation=self.payload(start='2026-10-13T09:00',end='2026-10-13T10:00');vacation.update(kind='Urlaub',trips=[],actual_pause=0,pause_policy=2)
        self.create(vacation)
        rows=self.driver.get('/api/v1/tf/work-reports/month/2026/10').json()['days']
        self.assertEqual(next(r for r in rows if r['date']=='2026-10-12')['performed_minutes'],360)
        self.assertEqual(next(r for r in rows if r['date']=='2026-10-13')['performed_minutes'],0)
        optional=dict(data,client_id=str(uuid4()),start_at='2026-10-14T09:00',end_at='2026-10-14T15:00',hotel_name='')
        self.assertEqual(self.create(optional)['hotel_name'],'')

    def test_atomic_idempotent_guest_creation_and_worktime(self):
        data=self.payload();data['trips'].append(dict(start_station='LL',end_station='BHF',start_at='2026-10-12T15:00',end_at='2026-10-12T16:00',transport='other',transport_detail='Testbus'))
        first=self.create(data);second=self.create(data);self.assertEqual(first['id'],second['id'])
        with Session(self.engine) as db:self.assertEqual(len(db.scalars(select(WorkEntry)).all()),1);self.assertEqual(len(db.scalars(select(DutyGuestTrip)).all()),2)
        month=self.driver.get('/api/v1/tf/work-reports/month/2026/10').json();self.assertEqual(month['work_minutes'],480);self.assertEqual(month['guest_minutes'],120)
        existing=self.driver.get('/api/v1/account/worktime/months/2026/10').json();self.assertEqual(existing['days'][0]['work'],480)
        changed=dict(data,overrun_reason='different');self.assertEqual(self.driver.post('/api/v1/tf/work-reports',json=changed).status_code,409)
        overlap=self.payload(start='2026-10-12T16:00',end='2026-10-12T19:00');self.assertEqual(self.driver.post('/api/v1/tf/work-reports',json=overlap).status_code,409)
        invalid=self.payload(start='2026-10-13T09:00',end='2026-10-13T17:00');invalid['trips'][0]['start_station']='UNKNOWN'
        self.assertEqual(self.driver.post('/api/v1/tf/work-reports',json=invalid).status_code,422)
        with Session(self.engine) as db:self.assertEqual(len(db.scalars(select(DutyReport)).all()),1)
    def test_invalid_trips_and_other_transport(self):
        for change in [dict(end_at='2026-10-12T08:00'),dict(transport='other',transport_detail=''),dict(transport='other',transport_detail='X'*141),dict(transport='boat')]:
            data=self.payload();data['trips'][0].update(change);self.assertEqual(self.driver.post('/api/v1/tf/work-reports',json=data).status_code,422)
        data=self.payload();data['trips'].append(dict(data['trips'][0]));self.assertEqual(self.driver.post('/api/v1/tf/work-reports',json=data).status_code,422)
    def test_special_duty_limits_and_credit(self):
        for day,kind,start,end in [(14,'Bereitschaft','23:00','07:00'),(16,'Rufbereitschaft','08:00','16:00'),(17,'Ausfallschicht','09:00','17:00')]:
            finish=day+1 if end<start else day
            data=self.payload(start=f'2026-10-{day}T{start}',end=f'2026-10-{finish}T{end}')
            data.update(kind=kind,actual_pause=0,trips=[])
            report=self.create(data)
            self.assertEqual((report['kind'],report['credited_minutes'],report['minimum_pause_minutes']),(kind,480,0))
            self.assertEqual(self.create(data)['id'],report['id'])
        for kind in ('Bereitschaft','Rufbereitschaft','Ausfallschicht'):
            data=self.payload(start='2026-10-18T08:00',end='2026-10-18T16:01');data.update(kind=kind,actual_pause=0,trips=[])
            self.assertEqual(self.driver.post('/api/v1/tf/work-reports',json=data).status_code,422)
        for start,end in [('2026-10-18T07:59','2026-10-18T08:59'),('2026-10-18T19:01','2026-10-18T20:01'),('2026-10-18T19:00','2026-10-19T01:00')]:
            data=self.payload(start=start,end=end);data.update(kind='Rufbereitschaft',trips=[],actual_pause=0)
            self.assertEqual(self.driver.post('/api/v1/tf/work-reports',json=data).status_code,422)
        month=self.driver.get('/api/v1/tf/work-reports/month/2026/10').json()
        self.assertEqual(month['work_minutes'],1440)
        canonical=self.driver.get('/api/v1/account/worktime/months/2026/10').json()
        self.assertEqual(sum(d['work'] for d in canonical['days']),1440)
        short=self.payload(start='2026-10-19T09:00',end='2026-10-19T12:00');short.update(kind='Ausfallschicht',actual_pause=0,trips=[])
        self.assertEqual(self.create(short)['credited_minutes'],180)
        canonical=self.driver.get('/api/v1/account/worktime/months/2026/10').json()
        self.assertEqual(next(d for d in canonical['days'] if d['date']=='2026-10-19')['credited'],180)

    def test_absence_credit_on_rest_days_and_plan_updates(self):
        with Session(self.engine) as db:
            period=PlanMonth(tf_user_id=self.tf,year=2026,month=10);db.add(period);db.flush()
            db.add_all([PlanDay(plan_month_id=period.id,day=date(2026,10,14),kind='Ruhetag',note=''),PlanDay(plan_month_id=period.id,day=date(2026,10,16),kind='Ruhetag',note='')]);db.commit()
        for day,kind,credit in [(14,'Urlaub',0),(15,'Urlaub',480),(16,'Krank',0),(17,'Krank',480)]:
            data=self.payload(start=f'2026-10-{day}T09:00',end=f'2026-10-{day}T10:00');data.update(kind=kind,actual_pause=0,trips=[])
            report=self.create(data);self.assertEqual(report['credited_minutes'],credit)
            self.assertEqual(self.create(data)['id'],report['id'])
            another=dict(data,client_id=str(uuid4()))
            self.assertEqual(self.driver.post('/api/v1/tf/work-reports',json=another).status_code,409)
        month=self.driver.get('/api/v1/tf/work-reports/month/2026/10').json();self.assertEqual(month['work_minutes'],960)
        canonical=self.driver.get('/api/v1/account/worktime/months/2026/10').json();self.assertEqual(sum(d['credited'] for d in canonical['days']),960)
        with Session(self.engine) as db:
            day=db.scalar(select(PlanDay).where(PlanDay.day==date(2026,10,14)));day.kind='Arbeitstag';db.commit()
        self.assertEqual(self.driver.get('/api/v1/tf/work-reports/month/2026/10').json()['work_minutes'],1440)
        self.assertEqual(sum(d['credited'] for d in self.driver.get('/api/v1/account/worktime/months/2026/10').json()['days']),1440)
        long_absence=self.payload(start='2026-10-18T06:00',end='2026-10-18T22:00');long_absence.update(kind='Krank',actual_pause=0,trips=[])
        self.assertEqual(self.create(long_absence)['credited_minutes'],480)
        bad=self.payload(start='2026-10-19T23:00',end='2026-10-20T01:00');bad.update(kind='Krank',actual_pause=0,trips=[])
        self.assertEqual(self.driver.post('/api/v1/tf/work-reports',json=bad).status_code,422)

    def test_legacy_report_kind_and_retries(self):
        data=self.payload();report=self.create(data)
        with Session(self.engine) as db:
            r=db.get(DutyReport,report['id']);payload=json.loads(r.payload_json);payload.pop('kind');r.payload_json=json.dumps(payload);db.commit()
        self.assertEqual(self.create(data)['kind'],'Sonstige Erfassung')

    def test_pause_is_documented_without_work_deduction(self):
        data=self.payload();data['actual_pause']=120
        # A guest journey may occupy the entire duty; pauses are independent documentation.
        data['trips'][0]['end_at']=data['end_at']
        report=self.create(data)
        month=self.driver.get('/api/v1/tf/work-reports/month/2026/10').json()
        self.assertEqual((month['work_minutes'],month['pause_minutes'],month['guest_minutes']),(480,120,480))
        canonical=self.driver.get('/api/v1/account/worktime/months/2026/10').json()
        self.assertEqual(canonical['days'][0]['work'],480)
        self.assertEqual(canonical['entries'][0]['pause'],120)
        self.assertEqual(canonical['weeks'][2]['totals']['work'],480)
        self.assertEqual(report['actual_pause'],120)

    def test_external_and_partial_guest_time_separate_from_work(self):
        data=self.payload();data['trips']=[
            dict(start_station='BHF',end_station='LL',start_at='2026-10-12T07:00',end_at='2026-10-12T08:00',transport='train'),
            dict(start_station='BHF',end_station='LL',start_at='2026-10-12T08:30',end_at='2026-10-12T09:30',transport='train'),
            dict(start_station='BHF',end_station='LL',start_at='2026-10-12T16:30',end_at='2026-10-12T17:30',transport='train'),
            dict(start_station='BHF',end_station='LL',start_at='2026-10-12T18:00',end_at='2026-10-12T19:00',transport='train')]
        report=self.create(data)
        self.assertEqual((report['guest_total_minutes'],report['guest_minutes'],report['external_guest_minutes']),(240,60,180))
        with Session(self.engine) as db:self.assertEqual(db.get(WorkEntry,report['entry_id']).guest_minutes,60)
        month=self.driver.get('/api/v1/tf/work-reports/month/2026/10').json()
        self.assertEqual((month['work_minutes'],month['guest_minutes'],month['external_guest_minutes']),(480,60,180))
        self.assertEqual(month['days'][0]['external_guest_minutes'],180)
        actual=self.driver.get('/api/v1/account/worktime/months/2026/10').json()
        self.assertEqual(actual['days'][0]['work'],480)
        self.assertEqual(self.create(data)['id'],report['id'])

    def test_external_guest_in_other_month_without_work(self):
        data=self.payload(start='2026-11-01T01:00',end='2026-11-01T09:00')
        data['trips']=[dict(start_station='BHF',end_station='LL',start_at='2026-10-31T23:00',end_at='2026-11-01T01:00',transport='train')]
        report=self.create(data)
        oct=self.driver.get('/api/v1/tf/work-reports/month/2026/10').json()
        nov=self.driver.get('/api/v1/tf/work-reports/month/2026/11').json()
        self.assertEqual((oct['work_minutes'],oct['guest_minutes'],oct['external_guest_minutes']),(0,0,60))
        self.assertEqual((nov['work_minutes'],nov['guest_minutes'],nov['external_guest_minutes']),(480,0,60))
        self.assertEqual(oct['reports'][0]['id'],report['id']);self.assertIsNone(oct['days'][0]['start_at'])

    def test_night_month_boundary_uses_real_guest_dates(self):
        data=self.payload(start='2026-10-31T21:00',end='2026-11-01T09:00');data['trips']=[dict(start_station='BHF',end_station='LL',start_at='2026-11-01T08:00',end_at='2026-11-01T09:00',transport='taxi',transport_detail='')]
        self.create(data)
        oct=self.driver.get('/api/v1/tf/work-reports/month/2026/10').json();nov=self.driver.get('/api/v1/tf/work-reports/month/2026/11').json()
        self.assertEqual((oct['guest_minutes'],nov['guest_minutes']),(0,60));self.assertEqual(oct['work_minutes']+nov['work_minutes'],720)
        self.assertEqual(nov['days'][0]['end_at'],'2026-11-01T09:00:00')
    def test_receipt_sends_attachment_once_and_survives_failed_mail(self):
        report=self.create()['id'];content=self.pdf();uploaded=self.upload(report,content);self.assertEqual(uploaded.status_code,202,uploaded.text);rid=uploaded.json()['id']
        self.assertEqual(self.send.call_count,1);message=self.send.call_args.args[0];self.assertEqual(message['To'],'omueller369@gmail.com');self.assertEqual(list(message.iter_attachments())[0].get_payload(decode=True),content)
        self.assertNotIn('787100',message.get_body(preferencelist=('plain',)).get_content());self.assertNotIn('TF-Nummer',message.get_body(preferencelist=('plain',)).get_content())
        self.assertEqual(self.upload(report,content).json()['id'],rid);self.assertEqual(self.send.call_count,1)
        downloaded=self.driver.get(f'/api/v1/tf/work-reports/{report}/receipts/{rid}');self.assertEqual(downloaded.content,content)
        image=io.BytesIO();Image.new('RGB',(20,20),'white').save(image,format='PNG')
        with Session(self.engine) as db:db.add(UserLocale(user_id=self.tf,language='pl'));db.commit()
        self.send.side_effect=OSError('SMTP down');failed=self.upload(report,image.getvalue(),'beleg.png');self.assertEqual(failed.status_code,202)
        with Session(self.engine) as db:row=db.get(DutyReceipt,failed.json()['id']);self.assertEqual(row.status,'failed');self.assertTrue(row.content)
        self.send.side_effect=None;self.driver.post(f'/api/v1/tf/work-reports/{report}/receipts/{failed.json()["id"]}/retry')
        with Session(self.engine) as db:self.assertEqual(db.get(DutyReceipt,failed.json()['id']).status,'sent')
        self.assertEqual(self.send.call_args.args[0]['Subject'],'LokZeitleiste: rachunek do raportu pracy')
    def test_access_locks_invalid_receipts_and_reset_closure(self):
        report=self.create();self.assertEqual(self.client.get(f'/api/v1/tf/work-reports/{report["id"]}').status_code,403)
        self.assertEqual(self.upload(report['id'],b'not PDF').status_code,422)
        with Session(self.engine) as db:db.add(WorkEntryLock(entry_id=report['entry_id'],actor_id=1,locked=True,reason='Test'));db.commit()
        self.assertEqual(self.upload(report['id']).status_code,409)
        with Session(self.engine) as db:db.get(WorkEntryLock,report['entry_id']).locked=False;db.commit()
        self.upload(report['id']);other=self.create_tf('787111','OTHER').json()['id']
        self.driver.post('/api/v1/account/login',json={'username':'787111','password':'tf-secret-12345'})
        self.assertEqual(self.driver.get(f'/api/v1/tf/work-reports/{report["id"]}/receipts').status_code,404)
        with Session(self.engine) as db:
            replace_all_tf(db,seed=25);db.commit()
            for model in (DutyReport,DutyGuestTrip,DutyReceipt):self.assertEqual(db.scalars(select(model)).all(),[])
    def test_missing_mail_config_keeps_durable_pending_receipt(self):
        report=self.create()['id']
        with patch.dict('os.environ',{'WORK_REPORT_RECEIPT_EMAIL':'','SMTP_HOST':''}):result=self.upload(report);self.assertEqual(result.status_code,202)
        with Session(self.engine) as db:row=db.get(DutyReceipt,result.json()['id']);self.assertEqual(row.status,'pending');self.assertEqual(row.attempts,0)
        process_receipt(result.json()['id']);self.assertEqual(self.send.call_count,1)
