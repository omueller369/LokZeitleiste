import unittest
from uuid import uuid4
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select
from lokzeitleiste.main import app
from lokzeitleiste.models import BrakeSheetDraft,AccountPolicy,VehicleRetirement
import test_vehicles

class BrakeSheetTest(unittest.TestCase):
    tearDown=test_vehicles.VehicleTest.tearDown
    data=test_vehicles.VehicleTest.data
    create=test_vehicles.VehicleTest.create
    base='/api/v1/tf/brake-sheets'
    def setUp(self):
        test_vehicles.VehicleTest.setUp(self)
        self.driver=TestClient(app,base_url='https://testserver');self.staff_clients.append(self.driver)
        self.driver.post('/api/v1/account/login',json={'username':'787100','password':'tf-secret-12345'})
        self.vehicle=self.create(length_m='18.950',weight_kg=84500,axle_count=4,brake_shoe='D')
    def sheet(self,**changes):
        data=dict(issuer='CTL DE',train_numbers=['00123','98765'],brake_mode='G',station_from='BHF · Berlin',station_to='Warszawa',class_de='D4',class_pl='C',locos=[dict(vehicle_id=self.vehicle['id'],vehicle_revision=1,note='Test')],required_percent=130)
        return dict(data,**changes)
    def test_calculation_unit_conversion_floor_and_negative_only(self):
        response=self.driver.post(self.base+'/calculate',json=self.sheet());self.assertEqual(response.status_code,200,response.text)
        r=response.json();self.assertEqual(Decimal(str(r['a']['weight'])),Decimal('84.5'));self.assertEqual(Decimal(str(r['total']['weight'])),Decimal('84.5'));self.assertEqual(Decimal(str(r['total']['length'])),Decimal('18.95'));self.assertEqual(r['total']['count'],1)
        expected=int(Decimal(10100)/Decimal('84.5'));self.assertEqual(r['available'],expected);self.assertEqual(r['missing'],expected-130)
        result=self.driver.post(self.base+'/calculate',json=self.sheet(required_percent=50)).json();self.assertEqual(result['missing'],'/');self.assertEqual(result['cast_iron'],'/')
        result=self.driver.post(self.base+'/calculate',json=self.sheet(required_percent=expected)).json();self.assertEqual(result['missing'],'/')
    def test_modes_loco_positions_and_manual_weight(self):
        for mode,position,weight in [('G','G',101),('G+P','G',75),('P','P',111),('R','R',123),('LL+P','P',Decimal('88.125'))]:
            locos=[dict(vehicle_id=self.vehicle['id'],vehicle_revision=1,position='P',manual_brake='88.125',note='12345678901234567890')]
            response=self.driver.post(self.base+'/calculate',json=self.sheet(brake_mode=mode,locos=locos));self.assertEqual(response.status_code,200,response.text)
            line=response.json()['lines'][0];self.assertEqual(line['position'],position);self.assertEqual(Decimal(str(line['brake_weight'])),weight);self.assertEqual(len(line['note']),20);self.assertEqual(line['spring_unit'],'kN');self.assertEqual(line['spring_brake'],55)
        response=self.driver.post(self.base+'/calculate',json=self.sheet(brake_mode='LL+P'));self.assertIsNone(response.json()['available'])
    def test_wagon_ranges_and_combined_totals(self):
        wagon=dict(count=100,length=720,holding='5.5',brake=700,weight=1000)
        response=self.driver.post(self.base+'/calculate',json=self.sheet(wagon=wagon,holding_loco='12.5',holding_unit='t',required_percent=80))
        self.assertEqual(response.status_code,200,response.text);r=response.json()
        self.assertEqual(r['total']['count'],101);self.assertEqual(Decimal(str(r['total']['length'])),Decimal('738.95'))
        self.assertEqual(Decimal(str(r['total']['weight'])),Decimal('1084.5'));self.assertEqual(r['total']['brake'],801)
        self.assertEqual(r['total']['holding'],18);self.assertEqual(r['available'],73);self.assertEqual(r['missing'],-7)
        for key,low,high in [('count',100,5000),('length',10,720),('brake',100,5000),('weight',100,5000)]:
            for value in [low,high]:
                self.assertEqual(self.driver.post(self.base+'/calculate',json=self.sheet(wagon={key:value})).status_code,200)
            for value in [low-1,high+1]:
                self.assertEqual(self.driver.post(self.base+'/calculate',json=self.sheet(wagon={key:value})).status_code,422)

    def test_five_locomotives_and_sixth_is_rejected(self):
        rows=[self.vehicle]
        for n in range(2,6):rows.append(self.create(vehicle_number=f'91 80 6185 {n:03d}-0',length_m='20',weight_kg=100000,axle_count=4,brake_shoe='K'))
        locos=[dict(vehicle_id=r['id'],vehicle_revision=r['revision']) for r in rows]
        result=self.driver.post(self.base+'/calculate',json=self.sheet(locos=locos,holding_loco='12.5',holding_unit='t'))
        self.assertEqual(result.status_code,200,result.text);data=result.json()
        self.assertEqual(data['a']['count'],5);self.assertEqual(Decimal(str(data['a']['length'])),Decimal('98.95'))
        self.assertEqual(Decimal(str(data['a']['weight'])),Decimal('484.5'));self.assertEqual(data['a']['brake'],505)
        self.assertEqual(data['total']['holding'],12.5)
        self.assertEqual(self.driver.post(self.base+'/calculate',json=self.sheet(locos=locos+[locos[0]])).status_code,422)

    def test_draft_creation_metadata_ownership_and_conflict(self):
        id=str(uuid4());path=self.base+'/'+id
        first=self.driver.put(path,json=dict(expected_revision=0,sheet=self.sheet(),created_by_name='Falsch'));self.assertEqual(first.status_code,200,first.text)
        r=first.json();self.assertNotEqual(r['created_by_name'],'Falsch');self.assertTrue(r['created_at'].endswith('Z'));self.assertEqual(r['sheet']['class_pl'],'D');self.assertEqual(r['sheet']['section_from'],'BHF · Berlin');self.assertEqual(r['sheet']['section_to'],'Warszawa');self.assertEqual(r['sheet']['train_numbers'][0],'00123')
        self.assertNotIn('verification',r['sheet']);self.assertEqual(self.driver.get(path).json()['revision'],1)
        self.assertEqual(self.driver.put(path,json=dict(expected_revision=0,sheet=self.sheet())).status_code,409)
        second=self.driver.put(path,json=dict(expected_revision=1,sheet=self.sheet(train_numbers=['00123','12345','00001'])));self.assertEqual(second.status_code,200,second.text)
        self.assertEqual(second.json()['created_at'],r['created_at']);self.assertEqual(second.json()['created_by_name'],r['created_by_name'])
        with Session(self.engine) as db:db.get(BrakeSheetDraft,id).owner_id=999;db.commit()
        self.assertEqual(self.driver.get(path).status_code,404);self.assertEqual(self.driver.get(self.base).json(),[])
        self.assertEqual(self.driver.put(path,json=dict(expected_revision=2,sheet=self.sheet())).status_code,404)
    def test_privacy_permissions_and_vehicle_revision(self):
        anon=TestClient(app,base_url='https://testserver');self.staff_clients.append(anon)
        self.assertEqual(anon.get(self.base).status_code,401);self.assertEqual(self.client.get(self.base).status_code,403)
        choices=self.driver.get(self.base+'/vehicles').json();self.assertNotIn('leasing_email',choices[0]);self.assertNotIn('hotline',choices[0])
        self.assertIn('no-store',self.driver.get(self.base+'/vehicles').headers['cache-control'])
        response=self.client.put('/api/v1/admin/vehicles/'+str(self.vehicle['id']),json=self.data(expected_revision=1,name='Neu'));self.assertEqual(response.status_code,200)
        self.assertEqual(self.driver.post(self.base+'/calculate',json=self.sheet()).status_code,409)
        with Session(self.engine) as db:db.add(VehicleRetirement(vehicle_id=self.vehicle['id']));db.commit()
        self.assertEqual(self.driver.get(self.base+'/vehicles').json(),[]);self.assertEqual(self.driver.post(self.base+'/calculate',json=self.sheet()).status_code,422)
    def test_missing_data_does_not_produce_fake_totals_and_validation(self):
        empty=self.create(vehicle_number='91 80 6185 002-3')
        data=self.sheet(locos=[dict(vehicle_id=empty['id'],vehicle_revision=1)])
        result=self.driver.post(self.base+'/calculate',json=data).json();self.assertIsNone(result['a']['length']);self.assertIsNone(result['a']['weight']);self.assertIsNone(result['available']);self.assertIsNone(result['missing'])
        for changes in [dict(train_numbers=['1234']),dict(train_numbers=['12ABC']),dict(required_percent=49),dict(required_percent=151),dict(wagon=dict(weight=10000)),dict(wagon=dict(weight=10)),dict(second_from='Warszawa'),dict(locos=[dict(vehicle_id=self.vehicle['id'],vehicle_revision=1,note='x'*21)]),dict(locos=self.sheet()['locos']*2)]:
            response=self.driver.post(self.base+'/calculate',json=self.sheet(**changes));self.assertEqual(response.status_code,422,(changes,response.text))
