import unittest
from collections import Counter
from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from lokzeitleiste.db import Base
from lokzeitleiste.models import User, TfProfile, WorkMonth, WorkEntry, ReportDispatch, SessionToken
from lokzeitleiste.seed_tf import replace_tf
from lokzeitleiste.security import verify_password


class TfSeedTest(unittest.TestCase):
    def test_replacement_preserves_admin_and_matches_requested_distribution(self):
        engine = create_engine('sqlite://')
        Base.metadata.create_all(engine)
        today = date(2026, 10, 11)
        with Session(engine) as db, db.begin():
            admin = User(username='admin', password_hash='admin-hash', role='admin')
            old = User(username='old-tf', password_hash='old-hash', role='tf')
            db.add_all([admin, old]); db.flush()
            db.add(TfProfile(user_id=old.id, first_name='Old', last_name='TF', personnel_number='old', target_hours_minutes=0, vacation_days=0, birth_date=date(1980,1,1), bahncard=50))
            month = WorkMonth(tf_user_id=old.id, year=2025, month=1)
            db.add(month); db.flush()
            db.add(WorkEntry(work_month_id=month.id, client_id='old-entry', kind='Zugfahrt', entry_date=today, start_time='08:00', end_time='10:00'))
            db.add(ReportDispatch(tf_user_id=old.id, work_month_id=month.id, recipient_email='old@example.com', filename='old.pdf'))
            db.add(SessionToken(user_id=old.id, token_hash='old-token', expires_at=__import__('datetime').datetime(2027,1,1)))
            db.flush()
            replace_tf(db, today)
            db.expire_all()
            users = db.scalars(select(User).where(User.role == 'tf')).all()
            profiles = db.scalars(select(TfProfile)).all()
            self.assertEqual(len(users), 20)
            self.assertEqual(db.scalar(select(User).where(User.role=='admin')).username, 'admin')
            for model in [WorkMonth, WorkEntry, ReportDispatch, SessionToken]:
                self.assertEqual(db.scalars(select(model)).all(), [])
            self.assertEqual(Counter(p.gender for p in profiles), {'männlich':14, 'weiblich':4, 'divers':1, 'keine Angabe':1})
            self.assertEqual(Counter(p.qualification for p in profiles), {'Grenz-TF':3, 'Grenz- und Strecken-TF':2, 'Strecken-TF':15})
            self.assertEqual(Counter(p.bahncard for p in profiles), {100:18, 50:1, 0:1})
            self.assertEqual({u.username for u in users}, {str(n) for n in range(787001,787021)})
            self.assertTrue(all(verify_password('tomcom123456', u.password_hash) for u in users))
            self.assertTrue(all(p.weekly_hours_minutes==2400 and p.photo_placeholder=='Bild folgt' for p in profiles))
            self.assertTrue(all(date(1995,1,1)<=p.joined_on<=today for p in profiles))
            validity=[(p.bahncard_valid_until-today).days for p in profiles if p.bahncard]
            self.assertEqual(len(set(validity)), 19)
            self.assertTrue(all(120<=days<=365 for days in validity))
            self.assertIsNone(next(p for p in profiles if not p.bahncard).bahncard_valid_until)
            replace_tf(db,today)
            self.assertEqual(len(db.scalars(select(TfProfile)).all()),20)
