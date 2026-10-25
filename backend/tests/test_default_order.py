import unittest
from sqlalchemy.orm import Session
from sqlalchemy import select
import test_accounts
from lokzeitleiste.models import AppDefaultValue,AppDefaultOrder,SystemChangeLog
from lokzeitleiste.app_defaults import ensure_defaults

class DefaultOrderTest(unittest.TestCase):
    setUp=test_accounts.AccountsTest.setUp
    tearDown=test_accounts.AccountsTest.tearDown
    payload=test_accounts.AccountsTest.payload
    create_staff=test_accounts.AccountsTest.create_staff
    staff_login=test_accounts.AccountsTest.staff_login
    change=test_accounts.AccountsTest.change
    active_staff=test_accounts.AccountsTest.active_staff
    def test_reasons_persist_and_tf_choices_follow_order(self):
        rows=self.client.get('/api/v1/admin/app-defaults').json();ids=[r['id'] for r in rows if r['category']=='reason'];path='/api/v1/admin/app-defaults/order/reason'
        self.assertEqual(self.client.get(path).json()['revision'],0)
        response=self.client.put(path,json={'ids':ids[::-1],'expected_revision':0});self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.client.get(path).json()['ids'],ids[::-1])
        choices=self.client.get('/api/v1/admin/app-defaults').json();self.assertEqual([r['id'] for r in choices if r['category']=='reason'],ids[::-1])
        token=self.client.post('/api/v1/account/login',json={'username':'787100','password':'tf-secret-12345'}).json()['access_token']
        choices=self.client.get('/api/v1/tf/app-defaults',headers={'Authorization':'Bearer '+token}).json();self.assertEqual([r['id'] for r in choices if r['category']=='reason'],ids[::-1])
        # Explicit admin bearer session after the TF login.
        self.client.post('/api/v1/admin/login',json={'username':'admin','password':'admin-secret-12345'})
        self.assertEqual(self.client.put(path,json={'ids':ids,'expected_revision':0}).status_code,409)
        self.assertEqual(self.client.put(path,json={'ids':ids[:-1],'expected_revision':1}).status_code,409)
        self.assertEqual(self.client.put(path,json={'ids':[ids[0]]*3,'expected_revision':1}).status_code,422)
        with Session(self.engine) as db:self.assertTrue(db.scalar(select(SystemChangeLog).where(SystemChangeLog.change.like('%app_default_orders%'))))
    def test_categories_damage_domains_and_permissions(self):
        base='/api/v1/admin/app-defaults/loco-handover';categories=[]
        for label in ['Alpha','Beta','Gamma']:categories.append(self.client.post(base+'/category',json={'label':label}).json()['id'])
        path='/api/v1/admin/app-defaults/order/category';r=self.client.put(path,json={'ids':categories[::-1],'expected_revision':0});self.assertEqual(r.status_code,200,r.text)
        self.assertEqual([r['id'] for r in self.client.get(base).json() if r['kind']=='category'],categories[::-1])
        children=[]
        for label in ['A','B','C']:children.append(self.client.post(base+'/damage',json={'label':label,'parent_id':categories[0]}).json()['id'])
        path=f'/api/v1/admin/app-defaults/order/damage:{categories[0]}';self.assertEqual(self.client.put(path,json={'ids':children[::-1],'expected_revision':0}).status_code,200)
        wrong=f'/api/v1/admin/app-defaults/order/damage:{categories[1]}';self.assertEqual(self.client.put(wrong,json={'ids':children,'expected_revision':0}).status_code,409)
        _,reader=self.active_staff({'app_defaults':1},'sort-reader');self.assertEqual(reader.get(path).status_code,200);self.assertEqual(reader.put(path,json={'ids':children,'expected_revision':1}).status_code,403)
        _,writer=self.active_staff({'app_defaults':2},'sort-writer');self.assertEqual(writer.put(path,json={'ids':children,'expected_revision':1}).status_code,200)
        domain_ids=[]
        for name in ['a.example.com','b.example.com','c.example.com']:domain_ids.append(self.client.post('/api/v1/admin/app-defaults/email-domains',json={'name':name}).json()['id'])
        ids=[r['id'] for r in self.client.get('/api/v1/admin/email-domains').json()];self.assertEqual(self.client.put('/api/v1/admin/app-defaults/order/email-domains',json={'ids':ids[::-1],'expected_revision':0}).status_code,200)
        self.assertEqual([r['id'] for r in self.client.get('/api/v1/admin/email-domains').json()],ids[::-1])
        self.assertEqual(self.client.get('/api/v1/admin/app-defaults/order/arbitrary').status_code,422)
