import io,json,unittest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select,func
from sqlalchemy.orm import Session
import test_vehicles
from lokzeitleiste.main import app
from lokzeitleiste.models import RailwayStation,LocoHandoverProtocol,LocoHandoverAttachment

class HandoverProtocolTest(unittest.TestCase):
    setUp=test_vehicles.VehicleTest.setUp
    tearDown=test_vehicles.VehicleTest.tearDown
    payload=test_vehicles.VehicleTest.payload
    create_staff=test_vehicles.VehicleTest.create_staff
    staff_login=test_vehicles.VehicleTest.staff_login
    change=test_vehicles.VehicleTest.change
    active_staff=test_vehicles.VehicleTest.active_staff
    data=test_vehicles.VehicleTest.data
    create=test_vehicles.VehicleTest.create
    def setup_protocol(self):
        vehicle=self.create(status='limited',status_note='Bremse prüfen')
        with Session(self.engine) as db:
            if not db.get(RailwayStation,'BGO'):db.add(RailwayStation(code='BGO',name='Görlitz'));db.commit()
        driver=TestClient(app,base_url='https://testserver');self.staff_clients.append(driver)
        driver.post('/api/v1/account/login',json={'username':'787100','password':'tf-secret-12345'})
        return vehicle,driver,'/api/v1/tf/loco-handover/vehicles/'+str(vehicle['id'])+'/protocols'
    def protocol_data(self,**changes):
        return dict(dict(occurred_at='2026-10-23T09:05',duty='V1',train_number='000123',station_code='BGO',notes='Hinweis\nZweite Zeile',meter_180='12345678',meter_280='00000001',mileage='12345678'),**changes)
    def post(self,client,path,data=None,files=None):
        return client.post(path,data={'payload':json.dumps(data or self.protocol_data())},files=files or [])
    def test_shared_vehicle_protocols_second_tf_and_attachments(self):
        vehicle,driver,path=self.setup_protocol()
        contact=self.client.post('/api/v1/admin/app-defaults/loco-handover/recipient',json={'label':'Leitstelle','email':'leitstelle@example.com'}).json()
        image=io.BytesIO();Image.new('RGB',(2,2)).save(image,'PNG')
        created=self.post(driver,path,self.protocol_data(recipient_id=contact['id']),[('files',('foto.png',image.getvalue(),'image/png'))])
        self.assertEqual(created.status_code,201,created.text);row=created.json()
        self.assertEqual(row['train_number'],'000123');self.assertEqual(row['station_name'],'Görlitz');self.assertEqual(row['recipient_name'],'Leitstelle')
        self.assertNotIn('787100',row['author_name']);self.assertNotIn('author_id',row)
        self.create_tf('787111','P-OTHER')
        other=TestClient(app,base_url='https://testserver');self.staff_clients.append(other)
        other.post('/api/v1/account/login',json={'username':'787111','password':'tf-secret-12345'})
        listing=other.get(path);self.assertEqual(listing.status_code,200,listing.text);self.assertEqual(listing.json(),[row])
        details=other.get(path+'/'+str(row['id'])).json();self.assertEqual(details['files'][0]['filename'],'foto.png')
        download=path+'/'+str(row['id'])+'/files/'+str(details['files'][0]['id'])
        self.assertEqual(other.get(download).content,image.getvalue())
        self.assertIn('attachment',other.get(download).headers['content-disposition'])
        self.assertEqual(self.client.get(path.replace('/tf/','/admin/')).json(),[row])
        self.client.put('/api/v1/admin/app-defaults/loco-handover/value/'+str(contact['id']),json={'label':'Neue Leitstelle','email':'neu@example.com','expected_revision':1})
        self.assertEqual(other.get(path+'/'+str(row['id'])).json()['recipient_name'],'Leitstelle')
        self.assertEqual(other.get(download+'0').status_code,404)
        second=self.create(vehicle_number='00 01 0002 003-4')
        self.assertEqual(other.get(path.replace(str(vehicle['id'])+'/protocols',str(second['id'])+'/protocols')+'/'+str(row['id'])).status_code,404)
        self.assertEqual(other.get('/api/v1/tf/loco-handover/stations',params={'q':'Görlitz'}).json(),[{'code':'BGO','name':'Görlitz'}])
        self.assertEqual(other.get('/api/v1/tf/loco-handover/recipients').json(),[{'id':contact['id'],'label':'Neue Leitstelle'}])
    def test_validation_no_partial_save_and_permissions(self):
        vehicle,driver,path=self.setup_protocol()
        for changes in [dict(train_number='1234567'),dict(train_number='12A'),dict(meter_180='123456789'),dict(meter_280='-1'),dict(mileage='1.5'),dict(notes='x'*1001),dict(duty='V2'),dict(station_code='UNKNOWN'),dict(recipient_id=999999),dict(occurred_at='2026-10-23T09:05Z')]:
            response=self.post(driver,path,self.protocol_data(**changes));self.assertEqual(response.status_code,422,(changes,response.text))
        image=io.BytesIO();Image.new('RGB',(2,2)).save(image,'PNG')
        response=self.post(driver,path,files=[('files',('good.png',image.getvalue(),'image/png')),('files',('bad.png',b'bad','image/png'))]);self.assertEqual(response.status_code,422)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(LocoHandoverProtocol)),0)
            self.assertEqual(db.scalar(select(func.count()).select_from(LocoHandoverAttachment)),0)
        _,reader=self.active_staff({'loco_handover':1},'protocol-reader');adminpath=path.replace('/tf/','/admin/')
        self.assertEqual(reader.get(adminpath).status_code,200);self.assertEqual(self.post(reader,adminpath).status_code,403)
        _,writer=self.active_staff({'loco_handover':2},'protocol-writer')
        created=self.post(writer,adminpath);self.assertEqual(created.status_code,201,created.text);self.assertEqual(created.json()['author_name'],'Mira Büro')
        anonymous=TestClient(app,base_url='https://testserver');self.staff_clients.append(anonymous)
        self.assertEqual(anonymous.get(path).status_code,401)
        self.assertEqual(self.post(anonymous,path).status_code,401)
        self.assertEqual(driver.get(adminpath).status_code,401)
