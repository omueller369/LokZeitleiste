import json
import unittest
from sqlalchemy import select,func,update
from sqlalchemy.orm import Session
import test_accounts
from lokzeitleiste.models import SystemChangeLog,User,PlanDay,PlanningNoteBackup,SystemMigration
from lokzeitleiste.planning.clear_legacy_notes import migrate
from lokzeitleiste.security import hash_password

class ChangeLogTest(unittest.TestCase):
    setUp=test_accounts.AccountsTest.setUp
    tearDown=test_accounts.AccountsTest.tearDown
    payload=test_accounts.AccountsTest.payload
    create_staff=test_accounts.AccountsTest.create_staff
    staff_login=test_accounts.AccountsTest.staff_login
    change=test_accounts.AccountsTest.change
    active_staff=test_accounts.AccountsTest.active_staff
    def test_real_plan_request_records_actor_module_and_changes_without_ui(self):
        path=f'/api/v1/admin/tf/{self.tf}/plan/2026/10'
        r=self.client.put(path,json={'expected_revision':0,'days':[{'date':'2026-10-01','kind':'Ruhetag','note':'AR'}]});self.assertEqual(r.status_code,200,r.text)
        with Session(self.engine) as db:
            rows=db.scalars(select(SystemChangeLog).where(SystemChangeLog.module=='Arbeitszeitplanung')).all();self.assertTrue(rows)
            change=next(row for row in rows if json.loads(row.change)['tabelle']=='plan_days');self.assertEqual(change.employee,'admin');self.assertIsNotNone(change.employee_id);self.assertIn('AR',change.change);self.assertIsNotNone(change.changed_at)
        self.assertEqual(self.client.get('/api/v1/admin/change-log').status_code,404)
    def test_transaction_rollback_sensitive_values_and_bulk_updates(self):
        with Session(self.engine) as db:
            actor={'employee_id':1,'employee':'Test Sachbearbeiter','module':'Konten'};db.info['change_actor']=actor
            row=User(username='audit-fixture',role='staff',password_hash=hash_password('never-store-this'));db.add(row);db.commit();identifier=row.id
            logs=db.scalars(select(SystemChangeLog).where(SystemChangeLog.module=='Konten')).all();self.assertTrue(logs);text=''.join(r.change for r in logs);self.assertNotIn(row.password_hash,text);self.assertIn('[geschützt]',text)
            initial=len(logs);row.active=False;db.flush();db.rollback()
            self.assertEqual(db.scalar(select(func.count()).select_from(SystemChangeLog).where(SystemChangeLog.module=='Konten')),initial)
            db.execute(update(User).where(User.id==identifier).values(active=False));db.commit()
            self.assertGreater(db.scalar(select(func.count()).select_from(SystemChangeLog).where(SystemChangeLog.module=='Konten')),initial)
    def test_note_cleanup_is_backed_up_and_runs_only_once(self):
        self.client.put(f'/api/v1/admin/tf/{self.tf}/plan/2026/10',json={'expected_revision':0,'days':[{'date':'2026-10-01','kind':'Ruhetag','note':'Alt'}]})
        with Session(self.engine) as db:
            self.assertEqual(migrate(db),1);db.commit()
            day=db.scalar(select(PlanDay));self.assertEqual(day.note,'');self.assertEqual(db.scalar(select(PlanningNoteBackup)).note,'Alt')
            day.note='SIM';db.commit();self.assertEqual(migrate(db),0);db.commit();self.assertEqual(day.note,'SIM')
            self.assertEqual(db.scalar(select(func.count()).select_from(PlanningNoteBackup)),1)

    def test_planning_performed_hours_include_cross_midnight_and_documented_pause(self):
        from lokzeitleiste.models import WorkMonth,WorkEntry
        from datetime import date
        with Session(self.engine) as db:
            period=WorkMonth(tf_user_id=self.tf,year=2026,month=10);db.add(period);db.flush()
            db.add_all([WorkEntry(work_month_id=period.id,client_id='work',kind='Sonstige Erfassung',entry_date=date(2026,10,1),start_time='22:00',end_time='02:00',pause_minutes=30,guest_minutes=0),WorkEntry(work_month_id=period.id,client_id='leave',kind='Urlaub',entry_date=date(2026,10,3),start_time='09:00',end_time='17:00',pause_minutes=0,guest_minutes=0)]);db.commit()
        result=self.client.get(f'/api/v1/admin/tf/{self.tf}/plan/2026/10').json()
        self.assertEqual([day['performed_minutes'] for day in result['days'][:3]],[120,120,0])
