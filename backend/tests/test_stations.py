import io
import unittest
from unittest.mock import patch
from PIL import Image
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select
import test_accounts
from lokzeitleiste.main import app
from lokzeitleiste.models import RailwayStation,TfStation,TfStationPlan,AccountPolicy
from lokzeitleiste.work_reports.receipts import MAX_FILE


class StationDirectoryTest(unittest.TestCase):
    tearDown=test_accounts.AccountsTest.tearDown

    def setUp(self):
        test_accounts.AccountsTest.setUp(self)
        with self.engine.connect() as connection:connection.exec_driver_sql('PRAGMA foreign_keys=ON')
        with Session(self.engine) as db:
            for code,name in [('BBB','Berlin Beispiel'),('AAA','Aachen Beispiel'),('CCC','Berlin Süd')]:
                db.add(RailwayStation(code=code,name=name))
            db.commit()
        self.driver=TestClient(app,base_url='https://testserver');self.staff_clients.append(self.driver)
        self.driver.post('/api/v1/account/login',json={'username':'787100','password':'tf-secret-12345'})

    def create(self,code='BBB',contacts=None):
        result=self.driver.post('/api/v1/tf/stations',json=dict(code=code,contacts=contacts or []))
        self.assertEqual(result.status_code,201,result.text)
        return result.json()

    def png(self):
        buffer=io.BytesIO();Image.new('RGB',(20,20),'blue').save(buffer,format='PNG');return buffer.getvalue()

    def test_module_page_catalog_selection_sort_and_search(self):
        page=self.driver.get('/tf/bahnhoefe');self.assertEqual(page.status_code,200)
        self.assertIn('Bahnhofsverzeichnis',page.text);self.assertIn('/tf/stations.js',page.text)
        redirect=self.client.get('/tf/bahnhoefe',follow_redirects=False)
        self.assertEqual(redirect.status_code,303)
        self.assertEqual(redirect.headers['location'],'/account?area=tf')
        self.assertEqual(self.client.get('/api/v1/tf/stations',headers={'X-CTL-Area':'backend'}).status_code,403)
        self.assertEqual([r['code'] for r in self.driver.get('/api/v1/tf/stations/catalog',params={'q':'bbb'}).json()],['BBB'])
        self.assertEqual([r['code'] for r in self.driver.get('/api/v1/tf/stations/catalog',params={'q':'Berlin'}).json()],['BBB','CCC'])
        self.assertEqual(self.driver.get('/api/v1/tf/stations/catalog',params={'q':'%'}).json(),[])
        self.create();self.create('AAA')
        listing=self.driver.get('/api/v1/tf/stations').json();self.assertEqual([r['code'] for r in listing],['AAA','BBB'])
        self.assertEqual(self.driver.get('/api/v1/tf/stations',params={'q':'berlin'}).json()[0]['name'],'Berlin Beispiel')
        self.assertEqual(self.driver.get('/api/v1/tf/stations',params={'q':'%'}).json(),[])
        self.assertEqual(self.driver.post('/api/v1/tf/stations',json={'code':'NOPE'}).status_code,422)
        self.assertEqual(self.driver.post('/api/v1/tf/stations',json={'code':'BBB'}).status_code,409)

    def test_all_categories_multiple_labels_numbers_and_edit(self):
        contacts=[dict(category=kind,label=f'Kontakt {index}',number=f'00{index} / +49 123') for kind in ('landline','mobile','bada','long_dial','local_radio') for index in (1,2)]
        row=self.create(contacts=contacts);self.assertEqual(row['contacts'],contacts)
        path=f'/api/v1/tf/stations/{row["id"]}'
        read=self.driver.get(path).json();self.assertEqual(read['contacts'],contacts)
        changed=self.driver.put(path,json=dict(expected_revision=row['revision'],contacts=[dict(category='bada',label=' Fdl ',number=' 00123#45 ')]))
        self.assertEqual(changed.status_code,200,changed.text)
        self.assertEqual(changed.json()['contacts'],[dict(category='bada',label='Fdl',number='00123#45')])
        self.assertEqual(changed.json()['revision'],2)
        self.assertEqual(self.driver.put(path,json=dict(expected_revision=1,contacts=[])).status_code,409)

    def test_contact_validation_and_bounds(self):
        for contact in [dict(category='bad',label='Fdl',number='1'),dict(category='mobile',label=' ',number='1'),dict(category='bada',label='Fdl',number=''),dict(category='bada',label='Fdl',number='x'*61)]:
            self.assertEqual(self.driver.post('/api/v1/tf/stations',json={'code':'BBB','contacts':[contact]}).status_code,422)
        contacts=[dict(category='landline',label='Fdl',number='001')]*101
        self.assertEqual(self.driver.post('/api/v1/tf/stations',json={'code':'BBB','contacts':contacts}).status_code,422)

    def test_plan_upload_download_replace_delete_and_revision(self):
        row=self.create();path=f'/api/v1/tf/stations/{row["id"]}'
        data=self.png()
        uploaded=self.driver.put(path+'/plan',data={'expected_revision':row['revision']},files={'file':('Bahnhof ü.png',data,'image/png')})
        self.assertEqual(uploaded.status_code,200,uploaded.text)
        row=uploaded.json();self.assertEqual(row['revision'],2)
        self.assertEqual(row['plan']['filename'],'Bahnhof ü.png')
        downloaded=self.driver.get(path+'/plan');self.assertEqual(downloaded.content,data)
        self.assertEqual(downloaded.headers['x-content-type-options'],'nosniff')
        self.assertIn('attachment',downloaded.headers['content-disposition'])
        self.assertEqual(self.driver.delete(path+'/plan',params={'expected_revision':1}).status_code,409)
        self.assertEqual(self.driver.put(path+'/plan',data={'expected_revision':2},files={'file':('bad.pdf',b'not a PDF','application/pdf')}).status_code,422)
        self.assertEqual(self.driver.get(path+'/plan').content,data)
        result=self.driver.delete(path+'/plan',params={'expected_revision':2});self.assertEqual(result.status_code,200,result.text)
        self.assertIsNone(result.json()['plan']);self.assertEqual(result.json()['revision'],3)
        self.assertEqual(self.driver.get(path+'/plan').status_code,404)

    def test_pdf_plan_and_size_limit(self):
        from reportlab.pdfgen.canvas import Canvas
        buffer=io.BytesIO();pdf=Canvas(buffer);pdf.drawString(20,20,'Test station plan');pdf.save()
        row=self.create();path=f'/api/v1/tf/stations/{row["id"]}/plan'
        self.assertEqual(self.driver.put(path,data={'expected_revision':1},files={'file':('plan.pdf',buffer.getvalue(),'application/pdf')}).status_code,200)
        self.assertEqual(self.driver.put(path,data={'expected_revision':2},files={'file':('large.png',b'x'*(MAX_FILE+1),'image/png')}).status_code,413)
        self.assertEqual(self.driver.put(path,content=b'x'*(MAX_FILE+65537),headers={'Content-Type':'multipart/form-data; boundary=x'}).status_code,413)
        self.assertEqual(self.driver.get(path).content,buffer.getvalue())

    def test_driver_isolation_and_cascading_delete(self):
        row=self.create();path=f'/api/v1/tf/stations/{row["id"]}'
        self.driver.put(path+'/plan',data={'expected_revision':1},files={'file':('plan.png',self.png(),'image/png')})
        self.create_tf('787200','OTHER-STATION-TF')
        other=TestClient(app,base_url='https://testserver');self.staff_clients.append(other)
        other.post('/api/v1/account/login',json={'username':'787200','password':'tf-secret-12345'})
        self.assertEqual(other.get('/api/v1/tf/stations').json(),[])
        for action in (lambda:other.get(path),lambda:other.get(path+'/plan'),lambda:other.put(path,json=dict(expected_revision=2,contacts=[])),lambda:other.delete(path,params={'expected_revision':2}),lambda:other.delete(path+'/plan',params={'expected_revision':2}),lambda:other.put(path+'/plan',data={'expected_revision':2},files={'file':('plan.png',self.png(),'image/png')})):
            self.assertEqual(action().status_code,404)
        self.assertEqual(other.post('/api/v1/tf/stations',json=dict(code='BBB',contacts=[])).status_code,201)
        self.assertEqual(self.driver.delete(path,params={'expected_revision':1}).status_code,409)
        self.assertEqual(self.driver.delete(path,params={'expected_revision':2}).status_code,200)
        with Session(self.engine) as db:self.assertIsNone(db.get(TfStationPlan,row['id']))
        self.assertEqual(len(other.get('/api/v1/tf/stations').json()),1)

    def test_tf_reset_removes_station_and_plan_records(self):
        from lokzeitleiste.accounts.seed_demo_tf import delete_tf_records
        row=self.create();path=f'/api/v1/tf/stations/{row["id"]}/plan'
        uploaded=self.driver.put(path,data={'expected_revision':1},files={'file':('plan.png',self.png(),'image/png')})
        self.assertEqual(uploaded.status_code,200,uploaded.text)
        with Session(self.engine) as db:
            delete_tf_records(db);db.commit()
            self.assertIsNone(db.get(TfStation,row['id']))
            self.assertIsNone(db.get(TfStationPlan,row['id']))

    def test_role_password_change_gate_and_logged_out_access(self):
        self.assertEqual(self.client.get('/api/v1/tf/stations').status_code,403)
        with Session(self.engine) as db:db.get(AccountPolicy,self.tf).must_change_password=True;db.commit()
        self.assertEqual(self.driver.get('/api/v1/tf/stations').status_code,403)
        self.assertEqual(self.driver.get('/tf/bahnhoefe',follow_redirects=False).status_code,303)
        self.driver.cookies.clear();self.assertEqual(self.driver.get('/api/v1/tf/stations').status_code,401)

    def test_station_notes_limits_roundtrip_and_partial_update(self):
        notes=dict(locomotive_parking='L'*120,train_securing='Z'*120,special_features='Zeile 1\nZeile 2\n'+'ä'*1008)
        self.assertEqual(len(notes['special_features']),1024)
        response=self.driver.post('/api/v1/tf/stations',json={'code':'BBB',**notes})
        self.assertEqual(response.status_code,201,response.text);row=response.json()
        path='/api/v1/tf/stations/'+str(row['id'])
        for field,value in notes.items():self.assertEqual(row[field],value)
        for field,limit in [('locomotive_parking',120),('train_securing',120),('special_features',1024)]:
            self.assertEqual(self.driver.put(path,json={'expected_revision':1,field:'x'*(limit+1)}).status_code,422)
        changed=self.driver.put(path,json={'expected_revision':1,'contacts':[]})
        self.assertEqual(changed.status_code,200,changed.text)
        for field,value in notes.items():self.assertEqual(changed.json()[field],value)
        clear=self.driver.put(path,json={'expected_revision':2,'locomotive_parking':'','train_securing':'','special_features':''})
        self.assertEqual(clear.status_code,200,clear.text)
        for field in notes:self.assertEqual(clear.json()[field],'')

    def test_existing_station_notes_default_empty(self):
        row=self.create()
        for field in ['locomotive_parking','train_securing','special_features']:self.assertEqual(row[field],'')

    def test_rename_preserves_station_data_and_validates_identity(self):
        row=self.driver.post('/api/v1/tf/stations',json={'code':'BBB','special_features':'Hinweis','contacts':[dict(category='bada',label='Fdl',number='00123')]}).json()
        path='/api/v1/tf/stations/'+str(row['id'])
        self.driver.put(path+'/plan',data={'expected_revision':1},files={'file':('plan.png',self.png(),'image/png')})
        for fields in [{'code':' '},{'name':' '},{'code':None},{'name':None},{'code':'X'*11},{'name':'X'*201}]:
            self.assertEqual(self.driver.put(path,json={'expected_revision':2,**fields}).status_code,422)
        result=self.driver.put(path,json={'expected_revision':2,'code':' zz1 ','name':' Neuer Bahnhof ','contacts':row['contacts']})
        self.assertEqual(result.status_code,200,result.text);data=result.json()
        self.assertEqual((data['id'],data['code'],data['name'],data['revision']),(row['id'],'ZZ1','Neuer Bahnhof',3))
        self.assertEqual(data['contacts'],row['contacts']);self.assertEqual(data['special_features'],'Hinweis')
        self.assertEqual(self.driver.get(path+'/plan').content,self.png())
        self.assertEqual(self.driver.get('/api/v1/tf/stations',params={'q':'ZZ1'}).json()[0]['name'],'Neuer Bahnhof')
        self.assertEqual(self.driver.get('/api/v1/tf/stations/catalog',params={'q':'BBB'}).json()[0]['name'],'Berlin Beispiel')
        self.assertEqual(self.driver.put(path,json={'expected_revision':2,'name':'Veraltet'}).status_code,409)

    def test_duplicate_rename_warns_without_mutation_and_allows_retry(self):
        first=self.create('AAA');second=self.create('BBB');path='/api/v1/tf/stations/'+str(second['id'])
        for fields in [dict(code='aaa',name='Anderer Name'),dict(code='NEW',name=' aachen beispiel ')]:
            response=self.driver.put(path,json={'expected_revision':1,**fields})
            self.assertEqual(response.status_code,409,response.text);self.assertEqual(response.headers['x-station-conflict'],'identity');self.assertIn('anderen Namen',response.json()['detail'])
            stored=self.driver.get(path).json();self.assertEqual((stored['code'],stored['name'],stored['revision']),('BBB','Berlin Beispiel',1))
        response=self.driver.put(path,json={'expected_revision':1,'code':'NEW','name':'Eigener Bahnhof'})
        self.assertEqual(response.status_code,200,response.text)
        self.create_tf('787200','RENAME-OTHER')
        other=TestClient(app,base_url='https://testserver');self.staff_clients.append(other)
        other.post('/api/v1/account/login',json={'username':'787200','password':'tf-secret-12345'})
        own=other.post('/api/v1/tf/stations',json={'code':'BBB'}).json()
        self.assertEqual(other.put('/api/v1/tf/stations/'+str(own['id']),json={'expected_revision':1,'code':'NEW','name':'Eigener Bahnhof'}).status_code,200)
        self.assertEqual(other.put(path,json={'expected_revision':2,'name':'Fremd'}).status_code,404)
