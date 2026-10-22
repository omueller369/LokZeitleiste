import unittest
from datetime import date
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
import test_planning
from lokzeitleiste.main import app
from lokzeitleiste.models import User,TfProfile,ModulePermission,PlanChange,PlanMonth,TfDutyProfile
from lokzeitleiste.security import hash_password

BASE='/api/v1/admin/planning/collective'
class CollectivePlanningTest(unittest.TestCase):
    setUp=test_planning.PlanningTest.setUp
    tearDown=test_planning.PlanningTest.tearDown
    put=test_planning.PlanningTest.put
    def other(self,role='tf',level=None):
        with Session(self.engine) as db:
            user=User(username='other-'+role,password_hash=hash_password('other-secret'),role=role);db.add(user);db.flush();identifier=user.id
            if role=='tf':db.add(TfProfile(user_id=identifier,first_name='Adam',last_name='Zweiter',personnel_number='00999',target_hours_minutes=9600,vacation_days=30,birth_date=date(1990,1,1),bahncard=0,email='test@example.com',federal_state='BE'))
            if level is not None:db.add(ModulePermission(user_id=identifier,module='planning',level=level))
            db.commit();return identifier
    def data(self,ids=None):
        ids=ids or [self.tf_id,self.other()]
        return {'groups':[dict(tf_id=id,year=2026,days=[dict(date='2026-10-01',kind='Ruhetag'),dict(date='2026-11-02',kind='Urlaub')],expected_revisions={'10':0,'11':0}) for id in ids]}
    def preview(self,data):
        response=self.client.post(BASE+'/preview',json=data);self.assertEqual(response.status_code,200,response.text);return response.json()
    def apply(self,data,review):return self.client.post(BASE+'/apply',json={**data,'confirmation':review['confirmation'],'confirmed':True})

    def test_review_and_atomic_multi_tf_multi_month_save(self):
        data=self.data();review=self.preview(data);self.assertEqual(review['changed_days'],4);self.assertEqual(review['tf_count'],2)
        self.assertEqual(review['changes'][0]['before']['kind'],'Ungeplant');self.assertEqual(review['changes'][0]['after']['kind'],'Ruhetag')
        with Session(self.engine) as db:self.assertEqual(db.scalar(select(func.count()).select_from(PlanMonth)),0)
        self.assertEqual(self.client.post(BASE+'/apply',json={**data,'confirmation':review['confirmation']}).status_code,422)
        result=self.apply(data,review);self.assertEqual(result.status_code,200,result.text);self.assertEqual(result.json()['changed_days'],4)
        for group in data['groups']:
            month=self.client.get(f"/api/v1/admin/tf/{group['tf_id']}/plan/2026/10").json();self.assertEqual(month['days'][0]['kind'],'Ruhetag');self.assertEqual(month['days'][1]['kind'],'Ungeplant')
        with Session(self.engine) as db:self.assertEqual(len(list(db.scalars(select(PlanChange).where(PlanChange.source=='collective')))),4)

    def test_conflict_on_second_tf_rolls_back_entire_batch(self):
        data=self.data();review=self.preview(data);second=data['groups'][1]['tf_id']
        self.client.put(f'/api/v1/admin/tf/{second}/plan/2026/10',json={'expected_revision':0,'days':[{'date':'2026-10-03','kind':'Ruhetag'}]})
        self.assertEqual(self.apply(data,review).status_code,409)
        month=self.client.get(self.base+'/2026/10').json();self.assertEqual(month['revision'],0);self.assertEqual(month['days'][0]['kind'],'Ungeplant')

    def test_changed_request_requires_fresh_confirmation(self):
        data=self.data([self.tf_id]);review=self.preview(data);data['groups'][0]['days'][0]['kind']='Arbeitstag'
        self.assertEqual(self.apply(data,review).status_code,409)
        self.assertEqual(self.client.get(self.base+'/2026/10').json()['revision'],0)

    def test_invalid_tf_or_shift_prevents_every_change(self):
        data=self.data([self.tf_id,99999]);self.assertEqual(self.client.post(BASE+'/preview',json=data).status_code,404)
        data=self.data();data['groups'][1]['days'][0].update(kind='Arbeitstag',shift='border_night')
        self.assertEqual(self.client.post(BASE+'/preview',json=data).status_code,422)
        self.assertEqual(self.client.get(self.base+'/2026/10').json()['revision'],0)

    def test_mixed_driver_types_resolve_automatic_work_shift_and_notes(self):
        second=self.other()
        with Session(self.engine) as db:db.add(TfDutyProfile(user_id=second,driver_type='border'));db.commit()
        data=self.data([self.tf_id,second])
        for group in data['groups']:group['days'][0].update(kind='Arbeitstag',note='Test')
        review=self.preview(data);first=review['changes'][0];border=review['changes'][2]
        self.assertEqual(first['after']['shift'],'standard');self.assertEqual(first['after']['target_minutes'],480)
        self.assertEqual(border['after']['shift'],'border_day');self.assertEqual(border['after']['target_minutes'],720)
        self.assertEqual(self.apply(data,review).status_code,200)

    def test_reader_cannot_preview_or_commit_and_duplicate_group_rejected(self):
        self.other(role='staff',level=1);reader=TestClient(app,base_url='https://testserver');self.addCleanup(reader.close)
        reader.post('/api/v1/admin/login',json={'username':'other-staff','password':'other-secret'})
        data=self.data([self.tf_id]);review=self.preview(data)
        self.assertEqual(reader.post(BASE+'/preview',json=data).status_code,403)
        self.assertEqual(reader.post(BASE+'/apply',json={**data,'confirmation':review['confirmation'],'confirmed':True}).status_code,403)
        data['groups']*=2;self.assertEqual(self.client.post(BASE+'/preview',json=data).status_code,422)
