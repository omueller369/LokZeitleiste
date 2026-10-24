import unittest
from sqlalchemy.orm import Session
from sqlalchemy import select,func
import test_accounts
from lokzeitleiste.models import LeasingCompany,VehicleLeasing,RailwayVehicle
from lokzeitleiste.leasing import seed_and_migrate
import test_vehicles

class LeasingTest(unittest.TestCase):
    setUp=test_accounts.AccountsTest.setUp
    tearDown=test_accounts.AccountsTest.tearDown
    payload=test_accounts.AccountsTest.payload
    create_staff=test_accounts.AccountsTest.create_staff
    staff_login=test_accounts.AccountsTest.staff_login
    change=test_accounts.AccountsTest.change
    active_staff=test_accounts.AccountsTest.active_staff
    def create(self,**changes):
        response=self.client.post('/api/v1/admin/leasing',json=dict(company='Railpool Test',contact='Hans Zimmer',email='railpool@example.com',postal_code='0123456',**changes))
        self.assertEqual(response.status_code,201,response.text);return response.json()
    def test_create_update_validation_and_revision(self):
        row=self.create();self.assertEqual(row['country'],'DE');self.assertEqual(row['postal_code'],'0123456')
        path='/api/v1/admin/leasing/'+str(row['id'])
        data={key:value for key,value in row.items() if key not in ('id','revision')};data.update(expected_revision=1,notes='x'*1000)
        response=self.client.put(path,json=data);self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['notes'],'x'*1000);self.assertEqual(response.json()['revision'],2)
        self.assertEqual(self.client.put(path,json=data).status_code,409)
        for key,value in [('company','  '),('email','broken'),('country','XX'),('postal_code','12345678'),('notes','x'*1001)]:
            body=dict(data);body[key]=value;self.assertEqual(self.client.post('/api/v1/admin/leasing',json=body).status_code,422,(key,value))
        self.assertEqual(self.client.post('/api/v1/admin/leasing',json={'company':'Railpool Test'}).status_code,409)
        self.assertIn('DE',self.client.get('/api/v1/admin/leasing/countries').json())
    def test_vehicle_link_live_contact_and_permissions(self):
        row=self.create();body=test_vehicles.VehicleTest.data(self,leasing_company_id=row['id']);response=self.client.post('/api/v1/admin/vehicles',json=body)
        self.assertEqual(response.status_code,201,response.text);vehicle=response.json();self.assertEqual(vehicle['lessor'],row['company']);self.assertEqual(vehicle['leasing_email'],row['email'])
        changed=self.client.put('/api/v1/admin/leasing/'+str(row['id']),json={'company':'Railpool Neu','hotline':'0800-123','email':'neu@example.com','expected_revision':1});self.assertEqual(changed.status_code,200)
        actual=self.client.get('/api/v1/admin/vehicles/'+str(vehicle['id'])).json();self.assertEqual(actual['hotline'],'0800-123');self.assertEqual(actual['leasing_email'],'neu@example.com');self.assertEqual(actual['lessor'],'Railpool Neu');self.assertEqual(len(self.client.get('/api/v1/admin/vehicles',params={'q':'Railpool Neu'}).json()),1)
        details=self.client.get('/api/v1/admin/loco-handover/vehicles/'+str(vehicle['id'])).json();self.assertEqual(details['hotline'],'0800-123');self.assertEqual(details['leasing_email'],'neu@example.com')
        body.update(expected_revision=1,leasing_company_id=99999);self.assertEqual(self.client.put('/api/v1/admin/vehicles/'+str(vehicle['id']),json=body).status_code,422)
        self.assertEqual(self.client.get('/api/v1/admin/vehicles/'+str(vehicle['id'])).json()['revision'],1)
        _,reader=self.active_staff({'leasing':1},'leasing-reader');self.assertEqual(reader.get('/api/v1/admin/leasing').status_code,200);self.assertEqual(reader.post('/api/v1/admin/leasing',json={'company':'No'}).status_code,403)
        _,writer=self.active_staff({'leasing':2},'leasing-writer');self.assertEqual(writer.post('/api/v1/admin/leasing',json={'company':'Writer'}).status_code,201)
        _,vehicle_reader=self.active_staff({'vehicles':1},'leasing-vehicle');self.assertEqual(vehicle_reader.get('/api/v1/admin/leasing').status_code,200);self.assertEqual(vehicle_reader.post('/api/v1/admin/leasing',json={'company':'No'}).status_code,403)
        _,denied=self.active_staff({'planning':3},'leasing-denied');self.assertEqual(denied.get('/api/v1/admin/leasing').status_code,403)
    def test_update_seed_is_idempotent_and_preserves_existing(self):
        vehicle=self.client.post('/api/v1/admin/vehicles',json=test_vehicles.VehicleTest.data(self,lessor='Alte Firma',hotline='123')).json()
        with Session(self.engine) as db:
            seed_and_migrate(db);db.commit();seed_and_migrate(db);db.commit()
            self.assertEqual(db.scalar(select(func.count()).select_from(LeasingCompany)),2)
            demo=db.scalar(select(LeasingCompany).where(LeasingCompany.company=='Railpool'));self.assertEqual(demo.contact,'Hans Zimmer');demo.contact='Geändert';db.commit();seed_and_migrate(db);db.commit();self.assertEqual(demo.contact,'Geändert');demo.company='Railpool Umbenannt';db.commit();seed_and_migrate(db);db.commit();self.assertEqual(db.scalar(select(func.count()).select_from(LeasingCompany)),2)
            link=db.get(VehicleLeasing,vehicle['id']);self.assertEqual(db.get(LeasingCompany,link.company_id).company,'Alte Firma')
            self.assertEqual(db.get(RailwayVehicle,vehicle['id']).name,'Testlok')
