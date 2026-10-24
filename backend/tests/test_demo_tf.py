import io
import unittest
from collections import Counter
from datetime import date, timedelta
from unittest.mock import patch
from PIL import Image
from sqlalchemy import select, text
from sqlalchemy.orm import Session
import test_accounts
from lokzeitleiste.models import (Base, User, TfProfile, TfEmployment, TfIdentity, TfAddress,
    AccountPolicy, TfDutyProfile, TfBahnCardValidity, ProfilePhoto, WorkMonth, WorkEntry,
    WorkEntryDates, WorkTimeChange, WorkEntryLock, WorkEntryAudit, AccountAudit, PlanMonth,
    PlanDay, PlanChange, PlanDuty, PlanDutyAudit, ShiftModel, ShiftAssignment, MailboxAccount,
    MailboxSettings, MailboxAuthorization, MailboxOAuthState, MailDraft, SessionToken,
    UserLocale, RailwayStation, TfNumberMigration, ReportDispatch)
from lokzeitleiste.security import hash_password, verify_password, issue_token
from lokzeitleiste.accounts.seed_demo_tf import replace_all_tf, build_records, validate_records, DATA, PASSWORD


class DemoTfTest(unittest.TestCase):
    tearDown=test_accounts.AccountsTest.tearDown
    payload=test_accounts.AccountsTest.payload
    create_staff=test_accounts.AccountsTest.create_staff
    staff_login=test_accounts.AccountsTest.staff_login
    change=test_accounts.AccountsTest.change
    active_staff=test_accounts.AccountsTest.active_staff

    def setUp(self):
        test_accounts.AccountsTest.setUp(self)
        with self.engine.connect() as connection:connection.exec_driver_sql('PRAGMA foreign_keys=ON')

    def test_gender_default_edit_validation_and_rights(self):
        profile=self.client.get('/api/v1/admin/tf').json()[0]
        self.assertEqual(profile['gender'],'unspecified')
        for gender in ('male','female','diverse','unspecified'):
            profile['gender']=gender
            result=self.client.put(f'/api/v1/admin/tf/{self.tf}',json=profile)
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(self.client.get('/api/v1/admin/tf').json()[0]['gender'],gender)
        profile['gender']='other'
        self.assertEqual(self.client.put(f'/api/v1/admin/tf/{self.tf}',json=profile).status_code,422)
        self.assertEqual(self.client.get('/api/v1/admin/tf').json()[0]['gender'],'unspecified')
        _,reader=self.active_staff({'employees':1},'gender-reader')
        self.assertEqual(reader.put(f'/api/v1/admin/tf/{self.tf}',json=profile).status_code,403)
        profile['gender']='female';profile.update(username='787765',personnel_number='00123',password='initial-secret-12345',email='787765@example.com')
        self.assertEqual(self.client.post('/api/v1/admin/tf',json=profile).status_code,201)
        self.assertEqual(next(row for row in self.client.get('/api/v1/admin/tf').json() if row['username']=='787765')['gender'],'female')

    def old_related_rows(self,db,staff_id):
        old_id=self.tf
        wm=WorkMonth(tf_user_id=old_id,year=2026,month=10);db.add(wm);db.flush()
        db.add(ReportDispatch(tf_user_id=old_id,work_month_id=wm.id,recipient_email='old@example.com',filename='old.pdf',pdf_data=b'old'))
        staff_month=WorkMonth(tf_user_id=staff_id,year=2026,month=10);db.add(staff_month);db.flush()
        db.add(WorkEntry(work_month_id=staff_month.id,client_id='staff-entry',kind='Sonstige Erfassung',entry_date=date(2026,10,1),start_time='09:00',end_time='17:00'))
        entry=WorkEntry(work_month_id=wm.id,client_id='old-entry',kind='Zugfahrt',entry_date=date(2026,10,1),start_time='21:00',end_time='09:00');db.add(entry);db.flush()
        db.add(WorkEntryDates(entry_id=entry.id,end_date=date(2026,10,2)))
        db.add(WorkEntryLock(entry_id=entry.id,actor_id=1,reason='old'))
        db.add(WorkEntryAudit(entry_id=entry.id,actor_id=1,action='created',reason='old'))
        db.add(WorkTimeChange(entry_id=entry.id,tf_user_id=old_id,admin_user_id=1,entry_date=date(2026,10,1),previous_start='20:00',previous_end='08:00',new_start='21:00',new_end='09:00',reason='old',recipient_email='old@example.com',email_body='old'))
        pm=PlanMonth(tf_user_id=old_id,year=2026,month=10);db.add(pm);db.flush()
        db.add(PlanDay(plan_month_id=pm.id,day=date(2026,10,1),kind='Arbeitstag'))
        change=PlanChange(tf_user_id=old_id,admin_user_id=1,day=date(2026,10,1),previous_kind='Ungeplant',new_kind='Arbeitstag',previous_note='',new_note='',source='manual');db.add(change);db.flush()
        db.add(PlanDutyAudit(change_id=change.id,previous_shift='standard',new_shift='border_night'))
        db.add(PlanDuty(tf_user_id=old_id,day=date(2026,10,1),shift='border_night'))
        model=ShiftModel(name='Preserved model',blocks='[]',revision=1);db.add(model);db.flush()
        db.add(ShiftAssignment(model_id=model.id,tf_user_id=old_id,admin_user_id=1,start_date=date(2026,10,1),end_date=date(2026,10,2),cycle_start=date(2026,10,1),model_snapshot='{}',overwrite=False,changed_days=1))
        db.add(MailboxAccount(tf_user_id=old_id,address='old@example.com',username='old',password_encrypted='old'));db.flush()
        db.add(MailboxSettings(tf_user_id=old_id,config_json='{}',tokens_encrypted='old'))
        db.add(MailboxAuthorization(tf_user_id=old_id,actor_id=1,device_encrypted='old',expires_at=date(2027,1,1),next_poll_at=date(2027,1,1),interval=5))
        db.add(MailboxOAuthState(state_hash='old',tf_user_id=old_id,actor_id=1,encrypted_payload='old',expires_at=date(2027,1,1)))
        db.add(MailDraft(actor_id=1,tf_user_id=old_id,recipient='old@example.com',subject='old',body='old'))
        db.add(UserLocale(user_id=old_id,language='pl'))
        db.add(AccountAudit(actor_id=old_id,target_id=old_id,action='old'))
        db.add(TfNumberMigration(user_id=old_id,previous_username='old',tf_number=int(db.get(User,old_id).username)))
        db.add(TfBahnCardValidity(user_id=old_id,valid_until=date(2027,1,1)))
        db.add(ProfilePhoto(user_id=old_id,image_data=b'old'))
        db.commit();self.old_token=issue_token(db,db.get(User,old_id))

    def test_replace_all_deletes_fk_closure_preserves_staff_and_creates_distribution(self):
        staff=self.create_staff({'employees':1},'preserved-staff')
        with Session(self.engine) as db:
            self.old_related_rows(db,staff)
            result=replace_all_tf(db,today=date(2026,10,11),seed=23);db.commit()
            self.assertEqual(result['created'],20)
            self.assertIsNone(db.get(User,self.tf))
            self.assertEqual(db.get(User,1).role,'admin');self.assertEqual(db.get(User,staff).username,'preserved-staff')
            self.assertEqual(len(db.scalars(select(ShiftModel)).all()),1)
            for model in (ReportDispatch,WorkEntryDates,WorkTimeChange,WorkEntryLock,WorkEntryAudit,PlanMonth,PlanDay,PlanChange,PlanDuty,PlanDutyAudit,ShiftAssignment,MailboxAccount,MailboxSettings,MailboxAuthorization,MailboxOAuthState,MailDraft,TfNumberMigration):
                self.assertEqual(len(db.scalars(select(model)).all()),0,model.__name__)
            self.assertEqual(len(db.scalars(select(WorkMonth)).all()),1)
            self.assertEqual(len(db.scalars(select(WorkEntry)).all()),1)
            self.assertEqual(db.scalar(select(WorkMonth)).tf_user_id,staff)
            self.assertEqual(db.execute(text('PRAGMA foreign_key_check')).all(),[])
            users=db.scalars(select(User).where(User.role=='tf')).all();self.assertEqual(len(users),20)
            profiles=db.scalars(select(TfProfile)).all();employment=db.scalars(select(TfEmployment)).all()
            self.assertEqual(Counter(i.gender for i in db.scalars(select(TfIdentity))),Counter(male=14,female=4,diverse=1,unspecified=1))
            self.assertEqual(Counter(i.driver_type for i in db.scalars(select(TfDutyProfile))),Counter(route=15,border=3,both=2))
            self.assertEqual(Counter(i.bahncard for i in profiles),Counter({100:18,50:1,0:1}))
            self.assertEqual(Counter(i.federal_state for i in profiles)['BE'],4)
            self.assertEqual(len({i.federal_state for i in profiles}),16)
            self.assertTrue(all(i.weekly_minutes==2400 for i in employment))
            self.assertTrue(all(i.vacation_days==30 and i.email=='omueller369@gmail.com' for i in profiles))
            self.assertTrue(any(i.personnel_number.startswith('0') for i in profiles))
            self.assertTrue(all(len(i.personnel_number)==5 and i.personnel_number.isdigit() for i in profiles))
            expiries=[i.valid_until for i in db.scalars(select(TfBahnCardValidity))]
            self.assertEqual(len(set(expiries)),19)
            self.assertTrue(all(120<=(i-date(2026,10,11)).days<=365 for i in expiries))
            self.assertTrue(all(verify_password(PASSWORD,u.password_hash) and u.password_hash!=PASSWORD for u in users))
            self.assertTrue(all(db.get(AccountPolicy,u.id).must_change_password for u in users))
            photos=list(db.scalars(select(ProfilePhoto)));self.assertEqual(len(photos),20)
            self.assertEqual(len({p.image_data for p in photos}),20)
            for photo in photos:
                with Image.open(io.BytesIO(photo.image_data)) as image:self.assertEqual(image.format,'JPEG');self.assertLessEqual(max(image.size),640)
            login_name=users[0].username
        self.assertEqual(self.client.get('/api/v1/account/me',headers={'Authorization':'Bearer '+self.old_token}).status_code,401)
        login=self.client.post('/api/v1/tf/login',json={'username':login_name,'password':PASSWORD})
        self.assertEqual(login.status_code,200,login.text);self.assertTrue(login.json()['password_change_required'])
        web=self.client.post('/api/v1/account/login',json={'username':login_name,'password':PASSWORD})
        self.assertEqual(web.status_code,200,web.text)

    def test_failure_rolls_back_and_preview_is_valid(self):
        for today in (date(2026,10,11),date(2028,2,29)):
            records=build_records(today,seed=23,unavailable=['787001']);validate_records(records,today)
            self.assertNotIn('787001',[r['username'] for r in records])
        with Session(self.engine) as db:
            # Force failure after deletion and some inserts; transaction restores old users.
            from lokzeitleiste.accounts import seed_demo_tf
            real_hash=seed_demo_tf.hash_password
            count=[0]
            def fail(password):
                count[0]+=1
                if count[0]==3:raise RuntimeError('simulated failure')
                return real_hash(password)
            with patch.object(seed_demo_tf,'hash_password',side_effect=fail):
                with self.assertRaises(RuntimeError):replace_all_tf(db,today=date(2026,10,11),seed=23)
            db.rollback()
            self.assertIsNotNone(db.get(User,self.tf))
            self.assertEqual(len(db.scalars(select(User).where(User.role=='tf')).all()),1)

    def test_gender_upgrade_from_old_and_interim_schema(self):
        from lokzeitleiste.accounts.tf_profiles import ensure_gender_column, migrate_legacy_gender
        with Session(self.engine) as db:
            db.delete(db.get(TfIdentity,self.tf));db.flush()
            db.execute(text('ALTER TABLE tf_profiles DROP COLUMN gender'))
            ensure_gender_column(db)
            db.execute(text("UPDATE tf_profiles SET gender='weiblich'"))
            migrate_legacy_gender(db);db.commit()
            self.assertEqual(db.get(TfIdentity,self.tf).gender,'female')
            db.get(TfIdentity,self.tf).gender='diverse';db.commit()
            migrate_legacy_gender(db);db.commit()
            self.assertEqual(db.get(TfIdentity,self.tf).gender,'diverse')
