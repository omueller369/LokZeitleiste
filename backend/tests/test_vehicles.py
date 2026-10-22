import unittest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select,func
import test_accounts
from lokzeitleiste.main import app
from lokzeitleiste.models import RailwayVehicle,AccountPolicy

class VehicleTest(unittest.TestCase):
    setUp=test_accounts.AccountsTest.setUp
    tearDown=test_accounts.AccountsTest.tearDown
    payload=test_accounts.AccountsTest.payload
    create_staff=test_accounts.AccountsTest.create_staff
    staff_login=test_accounts.AccountsTest.staff_login
    change=test_accounts.AccountsTest.change
    active_staff=test_accounts.AccountsTest.active_staff

    def data(self,**changes):
        result=dict(vehicle_number='91 80 6185 001-2',status='ready',status_note='',series='185',lessor='Leasing AG',hotline='+49 00123',name='Testlok',power_kw='5600',brake_r=123,brake_p=111,brake_g=101,spring_brake=55,spring_unit='kN',next_revision='2028-02-29',mileage=1234567,notes='Zeile 1\nZeile 2')
        return dict(result,**changes)

    def create(self,**changes):
        response=self.client.post('/api/v1/admin/vehicles',json=self.data(**changes));self.assertEqual(response.status_code,201,response.text);return response.json()

    def test_roundtrip_statuses_and_integer_brake_calculation(self):
        row=self.create(brake_g_25=999);self.assertEqual(row['brake_g_25'],75)
        self.assertEqual(row['spring_unit'],'kN');self.assertEqual(row['notes'],'Zeile 1\nZeile 2')
        path='/api/v1/admin/vehicles/'+str(row['id'])
        self.assertEqual(self.client.get(path).json(),row)
        for revision,(status,reason,color) in enumerate([('unavailable','Defekt','#ffdada'),('limited','Nur Rangieren','#fff0b3'),('ready','Nicht übernehmen','#d9f2df')],1):
            changed=self.client.put(path,json=self.data(expected_revision=revision,status=status,status_note=reason,brake_g=999))
            self.assertEqual(changed.status_code,200,changed.text);current=changed.json()
            self.assertEqual(current['brake_g_25'],749);self.assertEqual(current['status_color'],color)
            self.assertEqual(current['status_note'],reason if status!='ready' else '')
        self.assertEqual(self.client.put(path,json=self.data(expected_revision=1)).status_code,409)
        self.assertEqual(self.client.get(path).json()['revision'],4)

    def test_vehicle_number_normalization_duplicate_and_leading_zeros(self):
        row=self.create(vehicle_number='00 01 0002 003-4');self.assertEqual(row['vehicle_number'],'00 01 0002 003-4')
        self.assertEqual(self.client.post('/api/v1/admin/vehicles',json=self.data(vehicle_number='000100020034')).status_code,409)
        second=self.create()
        self.assertEqual(self.client.put('/api/v1/admin/vehicles/'+str(second['id']),json=self.data(vehicle_number='000100020034',expected_revision=1)).status_code,409)
        self.assertEqual(self.client.get('/api/v1/admin/vehicles/'+str(second['id'])).json()['vehicle_number'],self.data()['vehicle_number'])

    def test_validation_and_status_reason(self):
        for changes in [dict(status='wrong'),dict(status='unavailable',status_note=' '),dict(status='limited'),dict(vehicle_number='91AB61850012'),dict(vehicle_number='123'),dict(brake_r=1000),dict(brake_p=-1),dict(brake_g=2.5),dict(spring_brake=True),dict(spring_unit='kg'),dict(mileage=10000000),dict(mileage=-1),dict(next_revision='2027-02-29'),dict(notes='x'*4097)]:
            response=self.client.post('/api/v1/admin/vehicles',json=self.data(**changes));self.assertEqual(response.status_code,422,(changes,response.text))
        with Session(self.engine) as db:self.assertEqual(db.scalar(select(func.count()).select_from(RailwayVehicle)),0)

    def test_search_filter_and_role_permissions(self):
        row=self.create();self.create(vehicle_number='00 00 0000 001-1',status='limited',status_note='Test')
        self.assertEqual(len(self.client.get('/api/v1/admin/vehicles',params={'q':'Leasing'}).json()),2)
        self.assertEqual(self.client.get('/api/v1/admin/vehicles',params={'status':'limited'}).json()[0]['status'],'limited')
        self.assertEqual(self.client.get('/api/v1/admin/vehicles',params={'q':'%'}).json(),[])
        _,reader=self.active_staff({'vehicles':1},'vehicles-reader')
        self.assertEqual(reader.get('/api/v1/admin/vehicles').status_code,200)
        self.assertEqual(reader.post('/api/v1/admin/vehicles',json=self.data()).status_code,403)
        self.assertEqual(reader.put('/api/v1/admin/vehicles/'+str(row['id']),json=self.data(expected_revision=1)).status_code,403)
        _,writer=self.active_staff({'vehicles':2},'vehicles-writer')
        self.assertEqual(writer.put('/api/v1/admin/vehicles/'+str(row['id']),json=self.data(expected_revision=1,name='Geändert')).status_code,200)
        _,denied=self.active_staff({'planning':3},'vehicles-denied');self.assertEqual(denied.get('/api/v1/admin/vehicles').status_code,403)
        driver=TestClient(app,base_url='https://testserver');self.staff_clients.append(driver)
        driver.post('/api/v1/account/login',json={'username':'787100','password':'tf-secret-12345'})
        self.assertEqual(driver.get('/api/v1/admin/vehicles').status_code,401)
        driver.cookies.clear();self.assertEqual(driver.get('/api/v1/admin/vehicles').status_code,401)
        self.assertEqual(self.client.get('/api/v1/admin/vehicles/99999').status_code,404)
        self.assertEqual(self.client.get('/admin/vehicles').status_code,200)

    def test_initial_password_gate_and_permission_catalogue(self):
        self.create_staff({'vehicles':2},'vehicle-initial');client,_=self.staff_login('vehicle-initial')
        self.assertEqual(client.get('/api/v1/admin/vehicles').status_code,403)
        modules=self.client.get('/api/v1/admin/modules').json()
        self.assertTrue(any(row['id']=='vehicles' for row in modules))


    def test_identity_not_cached_and_missing_permission_still_denied(self):
        response=self.client.get('/api/v1/admin/me')
        self.assertEqual(response.json()['permissions']['vehicles'],3)
        self.assertEqual(response.headers['cache-control'],'private, no-store')
        self.assertIn('Cookie',response.headers['vary'])
        self.assertEqual(self.client.get('/admin/vehicles').headers['cache-control'],'no-cache')
        self.assertEqual(self.client.get('/admin/backend-nav.js').headers['cache-control'],'no-cache')
        _,staff=self.active_staff({},'vehicle-no-permission')
        self.assertEqual(staff.get('/api/v1/admin/me').json()['permissions']['vehicles'],0)
        self.assertEqual(staff.get('/api/v1/admin/vehicles').status_code,403)
