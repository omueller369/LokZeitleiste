import unittest
from fastapi.testclient import TestClient
import test_vehicles
from lokzeitleiste.main import app

BASE='/api/v1/admin/app-defaults/loco-handover'
class HandoverDefaultsTest(unittest.TestCase):
    setUp=test_vehicles.VehicleTest.setUp
    tearDown=test_vehicles.VehicleTest.tearDown
    payload=test_vehicles.VehicleTest.payload
    create_staff=test_vehicles.VehicleTest.create_staff
    staff_login=test_vehicles.VehicleTest.staff_login
    change=test_vehicles.VehicleTest.change
    active_staff=test_vehicles.VehicleTest.active_staff
    def add(self,kind,**data):
        response=self.client.post(BASE+'/'+kind,json=data)
        self.assertEqual(response.status_code,201,response.text)
        return response.json()
    def update(self,row,**changes):
        return self.client.put(BASE+'/value/'+str(row['id']),json={**row,'expected_revision':row['revision'],**changes})
    def test_contacts_pzb_edit_revision_and_separate_vocabulary(self):
        self.assertEqual(self.client.get(BASE).json(),[])
        first=self.add('recipient',label=' Frau A ',email='a@example.com')
        self.add('recipient',label='Herr B',email='b@example.com')
        reason=self.add('pzb',label='x'*255)
        self.assertEqual(first['label'],'Frau A')
        changed=self.update(first,label='Frau A Neu',email='neu@example.com')
        self.assertEqual(changed.status_code,200,changed.text)
        self.assertEqual(changed.json()['revision'],2)
        self.assertEqual(self.update(first,label='Alt').status_code,409)
        self.assertEqual(self.client.post(BASE+'/recipient',json={'label':'Frau A Neu','email':'anderer@example.com'}).status_code,409)
        self.assertEqual(self.update(reason,label='PZB geändert').status_code,200)
        self.assertEqual(len(self.client.get(BASE).json()),3)
        self.assertTrue(all(row['category'] in ('reason','cause') for row in self.client.get('/api/v1/admin/app-defaults').json()))
    def test_category_hotline_damage_scopes_and_editing(self):
        a=self.add('category',label='Bremse',hotline_name='Technik',hotline_email='technik@example.com')
        b=self.add('category',label='Antrieb')
        damage=self.add('damage',label='Vorne',parent_id=a['id'])
        self.add('damage',label='Vorne',parent_id=b['id'])
        self.assertEqual(self.client.post(BASE+'/damage',json={'label':' vorne ','parent_id':a['id']}).status_code,409)
        self.assertEqual(self.update(a,label='Bremsanlage',hotline_email='neu@example.com').status_code,200)
        self.assertEqual(self.update(damage,label='Hinten').json()['parent_id'],a['id'])
        rows=self.client.get(BASE).json()
        self.assertEqual(next(r for r in rows if r['id']==a['id'])['hotline_email'],'neu@example.com')
        self.assertEqual({r['parent_id'] for r in rows if r['kind']=='damage'},{a['id'],b['id']})
    def test_validation_and_grants(self):
        pzb=self.add('pzb',label='Test')
        for kind,data in [('pzb',{'label':'x'*256}),('pzb',{'label':'  '}),('recipient',{'label':'X'}),('recipient',{'label':'X','email':'invalid'}),('category',{'label':'x'*101}),('category',{'label':'X','hotline_name':'Nur Name'}),('category',{'label':'X','hotline_name':'Hotline','hotline_email':'no'}),('damage',{'label':'X'}),('damage',{'label':'X','parent_id':999999}),('damage',{'label':'X','parent_id':pzb['id']}),('pzb',{'label':'X','parent_id':pzb['id']})]:
            response=self.client.post(BASE+'/'+kind,json=data);self.assertEqual(response.status_code,422,(kind,data,response.text))
        _,reader=self.active_staff({'app_defaults':1},'handover-default-reader')
        self.assertEqual(reader.get(BASE).status_code,200)
        self.assertEqual(reader.post(BASE+'/pzb',json={'label':'No'}).status_code,403)
        self.assertEqual(reader.put(BASE+'/value/'+str(pzb['id']),json={'label':'No','expected_revision':1}).status_code,403)
        _,writer=self.active_staff({'app_defaults':2},'handover-default-writer')
        self.assertEqual(writer.post(BASE+'/pzb',json={'label':'Writer'}).status_code,201)
        _,denied=self.active_staff({'loco_handover':3},'handover-default-denied')
        self.assertEqual(denied.get(BASE).status_code,403)
        anonymous=TestClient(app,base_url='https://testserver');self.staff_clients.append(anonymous)
        self.assertEqual(anonymous.get(BASE).status_code,401)
        anonymous.post('/api/v1/account/login',json={'username':'787100','password':'tf-secret-12345'})
        self.assertEqual(anonymous.get(BASE).status_code,401)
        self.assertEqual(self.client.get('/admin/loco-handover-defaults.js').status_code,200)
