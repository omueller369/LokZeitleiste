import unittest
from datetime import date
from unittest.mock import patch
from sqlalchemy import select
from sqlalchemy.orm import Session
import test_accounts
from lokzeitleiste.models import User, TfProfile, ProfilePhoto, AccountPolicy, AccountAudit, WorkMonth, WorkEntry
from lokzeitleiste.security import verify_password
from lokzeitleiste.accounts.import_demo_tf import import_demo_tf, PREFIX
from lokzeitleiste.accounts.seed_demo_tf import replace_all_tf, PASSWORD


class ImportDemoTfTest(unittest.TestCase):
    setUp=test_accounts.AccountsTest.setUp
    tearDown=test_accounts.AccountsTest.tearDown

    def test_add_preserves_existing_accounts_and_repeat_keeps_passwords_and_work(self):
        with Session(self.engine) as db:
            existing=db.get(User,self.tf);before=existing.password_hash
            profile=db.get(TfProfile,self.tf);profile.personnel_number='00001'
            month=WorkMonth(tf_user_id=self.tf,year=2026,month=9);db.add(month);db.flush()
            entry=WorkEntry(work_month_id=month.id,client_id='preserved',kind='Zugfahrt',entry_date=date(2026,9,1),start_time='09:00',end_time='17:00');db.add(entry);db.commit();identity=entry.id
            result=import_demo_tf(db,today=date(2026,10,21),seed=23);db.commit()
            self.assertEqual(result['created'],20);self.assertEqual(result['existing'],0)
            self.assertEqual(len(db.scalars(select(User).where(User.role=='tf')).all()),21)
            self.assertEqual(db.get(User,self.tf).password_hash,before)
            self.assertIsNotNone(db.get(WorkEntry,identity))
            numbers=[p['username'] for p in result['people']]
            self.assertEqual(len(set(numbers)),20)
            self.assertTrue(all(len(n)==6 and n.startswith('787') for n in numbers))
            personnel=[p['personnel_number'] for p in result['people']]
            self.assertNotIn('00001',personnel);self.assertEqual(len(set(personnel)),20)
            for person in result['people']:
                self.assertIsNotNone(db.get(ProfilePhoto,person['id']))
                self.assertTrue(verify_password(PASSWORD,db.get(User,person['id']).password_hash))
                self.assertTrue(db.get(AccountPolicy,person['id']).must_change_password)
            target=db.get(User,result['people'][0]['id']);target.password_hash='preserve-edited-password'
            db.delete(db.get(ProfilePhoto,target.id));db.commit()
            repeated=import_demo_tf(db,today=date(2027,1,1),seed=7);db.commit()
            self.assertEqual(repeated['created'],0);self.assertEqual(repeated['existing'],20)
            self.assertEqual(repeated['photos_restored'],1)
            self.assertEqual(db.get(User,target.id).password_hash,'preserve-edited-password')
            self.assertEqual([p['username'] for p in repeated['people']],numbers)
            self.assertEqual(len(db.scalars(select(AccountAudit).where(AccountAudit.action.like(PREFIX+'%'))).all()),20)

    def test_previous_demo_seed_is_adopted_without_duplicate_people(self):
        with Session(self.engine) as db:
            original=replace_all_tf(db,today=date(2026,10,11),seed=23);db.commit()
            numbers={p['username'] for p in original['people']}
            first=db.scalar(select(User).where(User.role=='tf'))
            db.delete(db.get(ProfilePhoto,first.id));db.commit()
            result=import_demo_tf(db,today=date(2026,10,21),seed=99);db.commit()
            self.assertEqual(result['created'],0);self.assertEqual(result['existing'],20)
            self.assertEqual(result['photos_restored'],1)
            self.assertEqual({p['username'] for p in result['people']},numbers)
            self.assertEqual(len(db.scalars(select(ProfilePhoto)).all()),20)

    def test_failure_rolls_back_every_insert(self):
        from lokzeitleiste.accounts import import_demo_tf as module
        real=module.hash_password;count=[0]
        def fail(value):
            count[0]+=1
            if count[0]==3:raise RuntimeError('simulated import failure')
            return real(value)
        with Session(self.engine) as db:
            with patch.object(module,'hash_password',side_effect=fail):
                with self.assertRaises(RuntimeError):import_demo_tf(db,today=date(2026,10,21))
            db.rollback()
            self.assertEqual(len(db.scalars(select(User).where(User.role=='tf')).all()),1)
            self.assertEqual(len(db.scalars(select(AccountAudit).where(AccountAudit.action.like(PREFIX+'%'))).all()),0)

    def test_missing_photo_and_conflicting_existing_photo_do_not_overwrite_data(self):
        from lokzeitleiste.accounts import import_demo_tf as module
        with Session(self.engine) as db:
            with patch.object(module,'normalize',side_effect=ValueError('invalid photo')):
                with self.assertRaises(ValueError):import_demo_tf(db,today=date(2026,10,21))
            db.rollback()
            self.assertEqual(len(db.scalars(select(User).where(User.role=='tf')).all()),1)
            replace_all_tf(db,today=date(2026,10,11),seed=23);db.commit()
            photo=db.scalar(select(ProfilePhoto));photo.image_data=b'existing custom photo';db.commit()
            with self.assertRaisesRegex(ValueError,'Abweichendes vorhandenes Foto'):
                import_demo_tf(db,today=date(2026,10,21))
            db.rollback();self.assertEqual(db.get(ProfilePhoto,photo.user_id).image_data,b'existing custom photo')
