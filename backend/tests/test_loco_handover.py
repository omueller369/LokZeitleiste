import unittest
from fastapi.testclient import TestClient
import test_vehicles
from lokzeitleiste.main import app

class LocoHandoverTest(unittest.TestCase):
    setUp=test_vehicles.VehicleTest.setUp
    tearDown=test_vehicles.VehicleTest.tearDown
    payload=test_vehicles.VehicleTest.payload
    create_staff=test_vehicles.VehicleTest.create_staff
    staff_login=test_vehicles.VehicleTest.staff_login
    change=test_vehicles.VehicleTest.change
    active_staff=test_vehicles.VehicleTest.active_staff
    data=test_vehicles.VehicleTest.data
    create=test_vehicles.VehicleTest.create
    path='/api/v1/admin/loco-handover/vehicles'

    def test_same_live_vehicles_order_and_status(self):
        first=self.create(name='Testlok')
        self.create(vehicle_number='00 00 0000 001-1',status='limited',status_note='Nur Rangieren',name='Lok 2')
        source=self.client.get('/api/v1/admin/vehicles').json()
        rows=self.client.get(self.path).json()
        self.assertEqual([r['vehicle_number'] for r in rows],[r['vehicle_number'] for r in source])
        keys={'id','vehicle_number','name','status','status_label','status_note'}
        self.assertEqual(rows,[{k:r[k] for k in keys} for r in source])
        self.assertTrue(all(set(r)==keys for r in rows))
        result=self.client.put('/api/v1/admin/vehicles/'+str(first['id']),json=self.data(expected_revision=1,status='unavailable',status_note='Defekt',name='Geändert'))
        self.assertEqual(result.status_code,200,result.text)
        row=next(r for r in self.client.get(self.path).json() if r['id']==first['id'])
        self.assertEqual((row['name'],row['status'],row['status_note']),('Geändert','unavailable','Defekt'))

    def test_independent_read_permission_and_no_mutation_routes(self):
        self.create()
        _,reader=self.active_staff({'loco_handover':1},'handover-reader')
        self.assertEqual(reader.get(self.path).status_code,200)
        self.assertEqual(reader.get('/api/v1/admin/vehicles').status_code,403)
        modules=reader.get('/api/v1/admin/start').json()['modules']
        self.assertIn('loco_handover',{m['id'] for m in modules})
        self.assertNotIn('vehicles',{m['id'] for m in modules})
        self.assertEqual(reader.post(self.path,json={}).status_code,405)
        self.assertEqual(reader.put(self.path,json={}).status_code,405)
        _,other=self.active_staff({'vehicles':3},'handover-denied')
        self.assertEqual(other.get(self.path).status_code,403)
        self.assertNotIn('loco_handover',{m['id'] for m in other.get('/api/v1/admin/start').json()['modules']})
        anonymous=TestClient(app,base_url='https://testserver');self.staff_clients.append(anonymous)
        self.assertEqual(anonymous.get(self.path).status_code,401)
        anonymous.post('/api/v1/account/login',json={'username':'787100','password':'tf-secret-12345'})
        self.assertEqual(anonymous.get(self.path).status_code,401)

    def test_search_filter_validation_and_columns(self):
        self.create();self.create(vehicle_number='00 00 0000 001-1',status='limited',status_note='Test')
        self.assertEqual(len(self.client.get(self.path,params={'q':'Leasing'}).json()),2)
        self.assertEqual(len(self.client.get(self.path,params={'status':'limited'}).json()),1)
        self.assertEqual(self.client.get(self.path,params={'q':'%'}).json(),[])
        self.assertEqual(self.client.get(self.path,params={'status':'other'}).status_code,422)
        page=self.client.get('/admin/loco-handover');self.assertEqual(page.status_code,200)
        self.assertIn('<th>Status</th><th>Fahrzeugnummer</th><th>Name</th>',page.text)
        self.assertIn('vehicle-legend',page.text)
        self.assertNotIn('id="vehicleNew"',page.text)

    def test_details_statuses_format_projection_and_permissions(self):
        row=self.create(vehicle_number='00 01 0002 003-4',series='Testserie')
        path=self.path+'/'+str(row['id'])
        _,reader=self.active_staff({'loco_handover':1},'handover-detail-reader')
        detail=reader.get(path);self.assertEqual(detail.status_code,200,detail.text)
        self.assertEqual(detail.json()['vehicle_number'],'00 01 0002 003-4')
        self.assertEqual(detail.json()['series'],'Testserie')
        self.assertEqual(set(detail.json()),{'id','vehicle_number','name','series','status','status_label','status_color','status_note'})
        self.assertEqual(detail.json()['status_note'],'')
        for revision,(status,note,color) in enumerate([('limited','Nur Rangieren','#fff0b3'),('unavailable','Defekt','#ffdada'),('ready','Resttext','#d9f2df')],1):
            updated=self.client.put('/api/v1/admin/vehicles/'+str(row['id']),json=self.data(vehicle_number=row['vehicle_number'],expected_revision=revision,status=status,status_note=note))
            self.assertEqual(updated.status_code,200,updated.text)
            data=reader.get(path).json();self.assertEqual(data['status'],status);self.assertEqual(data['status_color'],color);self.assertEqual(data['status_note'],note if status!='ready' else '')
        self.assertEqual(reader.get(self.path+'/999999').status_code,404)
        self.assertEqual(reader.put(path,json={}).status_code,405)
        _,denied=self.active_staff({'vehicles':3},'handover-detail-denied')
        self.assertEqual(denied.get(path).status_code,403)
        page=self.client.get('/admin/loco-handover').text
        for label in ('Übergabeprotokoll','PZB','Störungen','Übergabeprotokolle'):
            self.assertIn(label,page)

    def test_tf_portal_uses_shared_live_read_only_module(self):
        row=self.create(status='limited',status_note='Nur Rangieren')
        driver=TestClient(app,base_url='https://testserver');self.staff_clients.append(driver)
        path='/api/v1/tf/loco-handover/vehicles'
        self.assertEqual(driver.get(path).status_code,401)
        driver.post('/api/v1/account/login',json={'username':'787100','password':'tf-secret-12345'})
        page=driver.get('/tf/lokuebergabebuch')
        self.assertEqual(page.status_code,200)
        self.assertIn('id="vehicleRows"',page.text)
        self.assertIn('href="/tf">TF Portal',page.text)
        self.assertNotIn('/admin/backend-nav.js',page.text)
        self.assertEqual(driver.get(path).json(),self.client.get(self.path).json())
        self.assertEqual(driver.get(path+'/'+str(row['id'])).json(),self.client.get(self.path+'/'+str(row['id'])).json())
        self.assertEqual(driver.post(path,json={}).status_code,405)
        self.assertEqual(driver.put(path+'/'+str(row['id']),json={}).status_code,405)
        self.assertEqual(driver.get(self.path).status_code,401)
        self.assertEqual(self.client.get(path).status_code,403)
        self.client.post('/api/v1/admin/accounts/'+str(self.tf)+'/reset-password',json={'initial_password':'abcdef'})
        self.assertEqual(driver.get(path).status_code,401)
        driver.post('/api/v1/account/login',json={'username':'787100','password':'abcdef'})
        self.assertEqual(driver.get(path).status_code,403)
