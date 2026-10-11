import unittest
from datetime import date
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import test_accounts
from lokzeitleiste.main import app
from lokzeitleiste.models import User, TfProfile, TfEmployment, TfNumberMigration, RailwayStation
from lokzeitleiste.security import hash_password, issue_token, user_from_token
from lokzeitleiste.accounts.tf_profiles import migrate_existing, monthly_minutes, seed_stations


class TfProfilesTest(unittest.TestCase):
    setUp=test_accounts.AccountsTest.setUp
    tearDown=test_accounts.AccountsTest.tearDown

    def profile(self):
        return next(row for row in self.client.get('/api/v1/admin/tf').json() if row['id']==self.tf)

    def login(self):
        return self.client.post('/api/v1/tf/login',json={'username':self.profile()['username'],'password':'tf-secret-12345'})

    def test_numeric_number_creation_unique_edit_and_old_session_revocation(self):
        profile=self.profile();base=f'/api/v1/admin/tf/{self.tf}'
        for invalid in ('old-login','12345','1234567','012345','123.45'):
            profile['username']=invalid
            self.assertEqual(self.client.put(base,json=profile).status_code,422)
        token=self.login().json()['access_token']
        profile['username']=789456
        self.assertEqual(self.client.put(base,json=profile).status_code,200)
        self.assertEqual(self.profile()['tf_number'],789456)
        self.assertEqual(self.profile()['username'],'789456')
        self.assertEqual(self.client.get('/api/v1/account/me',headers={'Authorization':'Bearer '+token}).status_code,401)
        self.assertEqual(self.login().status_code,200)
        duplicate=dict(self.profile(),password='initial-secret-12345',personnel_number='ANOTHER')
        self.assertEqual(self.client.post('/api/v1/admin/tf',json=duplicate).status_code,409)
        profile['username']='admin'
        self.assertEqual(self.client.put(base,json=profile).status_code,422)

    def test_addresses_postal_integrity_and_state(self):
        profile=self.profile();base=f'/api/v1/admin/tf/{self.tf}'
        second=dict(profile['addresses'][0],street='Andere Straße',federal_state='BB',is_postal=False)
        profile['addresses'].append(second)
        self.assertEqual(self.client.put(base,json=profile).status_code,200)
        for values in ([False,False],[True,True]):
            for a,postal in zip(profile['addresses'],values):a['is_postal']=postal
            self.assertEqual(self.client.put(base,json=profile).status_code,422)
            self.assertTrue(self.profile()['addresses'][0]['is_postal'])
        profile['addresses']=[dict(second,is_postal=True)]
        self.assertEqual(self.client.put(base,json=profile).status_code,200)
        self.assertEqual(self.profile()['federal_state'],'BB')
        profile['addresses']=[]
        self.assertEqual(self.client.put(base,json=profile).status_code,422)
        self.assertEqual(len(self.profile()['addresses']),1)

    def test_exit_date_and_immediate_block_for_cookie_and_bearer(self):
        base=f'/api/v1/admin/tf/{self.tf}'
        with patch('lokzeitleiste.accounts.tf_profiles.berlin_today',return_value=date(2026,10,11)):
            token=self.login().json()['access_token']
            cookie_client=TestClient(app,base_url='https://testserver')
            self.assertEqual(cookie_client.post('/api/v1/account/login',json={'username':self.profile()['username'],'password':'tf-secret-12345'}).status_code,200)
            profile=self.profile();profile['exit_date']='2026-10-12'
            self.assertEqual(self.client.put(base,json=profile).status_code,200)
            self.assertEqual(self.client.get('/api/v1/account/me',headers={'Authorization':'Bearer '+token}).status_code,200)
            profile['immediate_block']=True
            self.assertEqual(self.client.put(base,json=profile).status_code,200)
            self.assertFalse(self.profile()['active'])
            self.assertEqual(self.login().status_code,401)
            self.assertEqual(cookie_client.get('/api/v1/account/me').status_code,401)
            self.assertEqual(self.client.get('/api/v1/account/me',headers={'Authorization':'Bearer '+token}).status_code,401)
            profile['immediate_block']=False
            self.assertEqual(self.client.put(base,json=profile).status_code,200)
            token=self.login().json()['access_token']
            cookie_client.close()
        with patch('lokzeitleiste.accounts.tf_profiles.berlin_today',return_value=date(2026,10,12)):
            self.assertEqual(self.login().status_code,401)
            self.assertEqual(self.client.get('/api/v1/account/me',headers={'Authorization':'Bearer '+token}).status_code,401)
        profile=self.profile();profile['exit_date']='2019-12-31'
        self.assertEqual(self.client.put(base,json=profile).status_code,422)

    def test_weekly_monthly_plan_calculation_and_station_search(self):
        profile=self.profile();profile['weekly_minutes']=2700;profile['driver_type']='both';profile['nationality']='PL'
        with Session(self.engine) as db:
            db.add(RailwayStation(code='BLS',name='Berlin Hauptbahnhof'))
            db.add(RailwayStation(code='TEST',name='Testbahnhof'))
            db.commit()
        rows=self.client.get('/api/v1/admin/stations',params={'q':'BLS'}).json();self.assertEqual(rows[0]['name'],'Berlin Hauptbahnhof')
        rows=self.client.get('/api/v1/admin/stations',params={'q':'Hauptbahnhof'}).json();self.assertEqual(rows[0]['code'],'BLS')
        self.assertEqual(self.client.get('/api/v1/admin/stations',params={'q':'%'}).json(),[])
        profile['home_station']='BLS'
        self.assertEqual(self.client.put(f'/api/v1/admin/tf/{self.tf}',json=profile).status_code,200)
        self.assertEqual(self.profile()['home_station_name'],'Berlin Hauptbahnhof')
        profile['home_station']='UNKNOWN'
        self.assertEqual(self.client.put(f'/api/v1/admin/tf/{self.tf}',json=profile).status_code,422)
        profile['home_station']=None;profile['nationality']='ZZ'
        self.assertEqual(self.client.put(f'/api/v1/admin/tf/{self.tf}',json=profile).status_code,422)
        metadata=self.client.get('/api/v1/admin/tf-metadata').json();self.assertEqual(len(metadata['countries']),249)
        with Session(self.engine) as db:self.assertEqual(monthly_minutes(db,self.tf,2026,9),22*540)
        result=self.client.put(f'/api/v1/admin/tf/{self.tf}/plan/2026/5',json={'expected_revision':0,'days':[
            {'date':'2026-05-01','kind':'Arbeitstag'}, {'date':'2026-05-04','kind':'Arbeitstag'},
            {'date':'2026-05-05','kind':'Urlaub'}, {'date':'2026-05-06','kind':'Arbeitstag','shift':'border_night'}]})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['target_minutes'],540+480+720)
        self.assertEqual(result.json()['contract_monthly_minutes'],18*540)

    def test_atomic_idempotent_legacy_migration_and_minimum_hours(self):
        with Session(self.engine) as db:
            db.add(User(username='787000',password_hash=hash_password('staff-secret-12345'),role='staff'))
            legacy=User(username='legacy-tf',password_hash=hash_password('legacy-secret-12345'),role='tf');db.add(legacy);db.flush()
            legacy_id=legacy.id
            db.add(TfProfile(user_id=legacy.id,last_name='Alt',first_name='Test',personnel_number='LEGACY',target_hours_minutes=9600,vacation_days=30,birth_date=date(1990,1,1),bahncard=50,email='legacy@example.com',federal_state='BE'))
            numeric=User(username='787001',password_hash='unused',role='tf');db.add(numeric);db.flush()
            db.add(TfProfile(user_id=numeric.id,last_name='Alt',first_name='Numerisch',personnel_number='LEGACY-NUM',target_hours_minutes=14400,vacation_days=30,birth_date=date(1990,1,1),bahncard=0,email='numeric@example.com',federal_state='BE'))
            db.commit();token=issue_token(db,legacy)
            with patch('lokzeitleiste.accounts.tf_profiles.secrets.SystemRandom.shuffle',lambda self,values:values.sort()):
                self.assertEqual(migrate_existing(db),2)
            db.commit()
            self.assertEqual(legacy.username,'787001')
            self.assertEqual(numeric.username,'787002')
            self.assertEqual(db.get(TfEmployment,numeric.id).weekly_minutes,3323)
            number=legacy.username
            self.assertRegex(number,r'^787[0-9]{3}$');self.assertNotEqual(number,'787000')
            self.assertEqual(db.get(TfEmployment,legacy_id).weekly_minutes,2400)
            self.assertIsNone(user_from_token(db,token))
            self.assertEqual(db.get(TfNumberMigration,legacy_id).previous_username,'legacy-tf')
            self.assertEqual(migrate_existing(db),0);db.commit();self.assertEqual(legacy.username,number)
        self.assertEqual(self.client.post('/api/v1/tf/login',json={'username':'legacy-tf','password':'legacy-secret-12345'}).status_code,401)
        login=self.client.post('/api/v1/tf/login',json={'username':number,'password':'legacy-secret-12345'})
        self.assertEqual(login.status_code,200);self.assertEqual(login.json()['previous_username'],'legacy-tf')
        # Capacity is checked before any username is changed.
        with Session(self.engine) as db:
            extra=User(username='capacity-tf',password_hash=hash_password('capacity-secret-12345'),role='tf');db.add(extra);db.flush()
            db.add(TfProfile(user_id=extra.id,last_name='Alt',first_name='Test',personnel_number='CAPACITY',target_hours_minutes=9600,vacation_days=30,birth_date=date(1990,1,1),bahncard=0,email='capacity@example.com',federal_state='BE'))
            used=set(db.query(User.username).all())
            for n in range(787000,788000):
                if (str(n),) not in used:db.add(User(username=str(n),password_hash='unused',role='staff'))
            db.commit()
            with self.assertRaises(RuntimeError):migrate_existing(db)
            db.rollback();self.assertEqual(db.get(User,extra.id).username,'capacity-tf')
