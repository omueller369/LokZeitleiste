import io,os,tempfile,unittest
from uuid import uuid4
from unittest.mock import patch
from pypdf import PdfReader
from PIL import Image
from fastapi.testclient import TestClient
from lokzeitleiste.main import app
import test_brake_sheets
class NationalBrakeTest(unittest.TestCase):
    tearDown=test_brake_sheets.BrakeSheetTest.tearDown
    data=test_brake_sheets.BrakeSheetTest.data
    create=test_brake_sheets.BrakeSheetTest.create
    setUp=test_brake_sheets.BrakeSheetTest.setUp
    base='/api/v1/tf/national-brake-sheets'
    def sheet(self,**changes):
        return dict(dict(departure_date='2026-10-26',trains=[dict(number='00123',station=' b '),dict(number='98765',station='BHBF')],locos=[dict(vehicle_id=self.vehicle['id'],vehicle_revision=1)],brake_mode='G',wagon_weight=1000,wagon_brake=700,wagon_axles=13,required_percent=80,wagon_length=200,braked_axles=13,last_vehicle='318012345678',brakes_multi=20,brakes_d=10,brakes_k=10,brakes_matrossow=1),**changes)
    def test_formulas_positions_and_limits(self):
        r=self.driver.post(self.base+'/calculate',json=self.sheet());self.assertEqual(r.status_code,200,r.text);r=r.json()
        for section,key,value in [('total','weight','1084.5'),('total','brake','775'),('loco','length','19'),('total','length','219')]:self.assertEqual(str(r[section][key]),value)
        self.assertEqual(r['total']['axles'],17);self.assertEqual(r['required_axles'],11);self.assertEqual(r['available'],71);self.assertEqual(r['missing'],-9);self.assertEqual(r['preview_missing'],[])
        for mode,weight in [('G','75'),('P','111'),('R','123')]:self.assertEqual(self.driver.post(self.base+'/calculate',json=self.sheet(brake_mode=mode)).json()['loco']['brake'],int(weight))
        self.assertEqual(self.driver.post(self.base+'/calculate',json=self.sheet(required_percent=50)).json()['missing'],'/')
        for key in ['wagon_weight','wagon_brake','wagon_axles','required_percent','wagon_length','braked_axles','brakes_single','brakes_multi','brakes_d','brakes_k','brakes_matrossow']:
            for n in [0,5000]:self.assertEqual(self.driver.post(self.base+'/calculate',json=self.sheet(**{key:n})).status_code,200,(key,n))
            for n in [-1,5001,1.5,True,'12']:self.assertEqual(self.driver.post(self.base+'/calculate',json=self.sheet(**{key:n})).status_code,422,(key,n))
        self.assertEqual(self.driver.post(self.base+'/calculate',json=self.sheet(locos=[dict(vehicle_id=self.vehicle['id'],vehicle_revision=1)]*2)).status_code,422)
        self.assertEqual(self.driver.post(self.base+'/calculate',json=self.sheet(trains=[dict(number='1234',station='B'),{}])).status_code,422)
        self.assertEqual(self.driver.post(self.base+'/calculate',json=self.sheet(trains=[dict(number='00123',station='B · Berlin'),{}])).status_code,422)
    def test_two_loco_round_once_and_speed(self):
        second=self.create(vehicle_number='918061850020',length_m='20.001',weight_kg=80000,axle_count=4,brake_shoe='K')
        locos=[dict(vehicle_id=v['id'],vehicle_revision=1) for v in [self.vehicle,second]]
        r=self.driver.post(self.base+'/calculate',json=self.sheet(locos=locos)).json();self.assertEqual(r['loco']['length'],39);self.assertEqual(r['total']['length'],239);self.assertEqual(r['loco']['axles'],8)
        self.assertEqual(self.driver.post(self.base+'/calculate',json=self.sheet(locos=locos+[locos[0]])).status_code,422)
        self.assertEqual(self.driver.post(self.base+'/calculate',json=self.sheet(speeds=[dict(lower=True,value=5001),{},{}])).status_code,422)
        self.assertIn('Geschwindigkeit',str(self.driver.post(self.base+'/calculate',json=self.sheet(speeds=[dict(lower=True),{},{}])).json()['preview_missing']))
    def test_preview_archive_and_draft_conflicts(self):
        id=str(uuid4());path=self.base+'/'+id
        r=self.driver.put(path,json=dict(expected_revision=0,sheet=self.sheet()));self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['sheet']['trains'][0]['station'],'B');name=r.json()['created_by_name'];self.assertTrue(name)
        self.assertEqual(self.driver.put(path,json=dict(expected_revision=0,sheet=self.sheet())).status_code,409)
        self.assertEqual(self.driver.post(path+'/preview',json={'expected_revision':2}).status_code,409)
        preview=self.driver.post(path+'/preview',json={'expected_revision':1});self.assertEqual(preview.status_code,200,preview.text[:100] if preview.status_code!=200 else '')
        self.assertEqual(Image.open(io.BytesIO(preview.content)).size,(1680,2380))
        anonymous=TestClient(app,base_url='https://testserver');self.assertEqual(anonymous.get(path).status_code,401)
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'LOKZEITLEISTE_FILES_ROOT':folder}),patch('lokzeitleiste.reports.mailer._send_message') as mail:
            archive=self.driver.post(path+'/archive',json={'expected_revision':1});self.assertEqual(archive.status_code,200,archive.text);mail.assert_not_called()
            data=archive.json();self.assertTrue(data['document_path'].startswith('Dokumente/Zugfahrten/2026/10/26/00123/'))
            pdf=self.driver.get(data['download_url']);self.assertEqual(pdf.status_code,200)
            reader=PdfReader(io.BytesIO(pdf.content));self.assertEqual(len(reader.pages),1);self.assertEqual(len(reader.pages[0].images),0);text=reader.pages[0].extract_text();self.assertIn('00123',text);self.assertIn(name,text);self.assertNotIn(self.vehicle['vehicle_number'],text)
    def test_incomplete_draft_and_stale_vehicle(self):
        path=self.base+'/'+str(uuid4());self.assertEqual(self.driver.put(path,json={'expected_revision':0,'sheet':{}}).status_code,200)
        self.assertEqual(self.driver.post(path+'/archive',json={'expected_revision':1}).status_code,422)
        s=self.sheet();s['locos'][0]['vehicle_revision']=999;self.assertEqual(self.driver.post(self.base+'/calculate',json=s).status_code,409)
    def test_cross_owner_and_administrator_cannot_read_or_write(self):
        path=self.base+'/'+str(uuid4());self.assertEqual(self.driver.put(path,json={'expected_revision':0,'sheet':self.sheet()}).status_code,200)
        self.assertEqual(self.create_tf('787101','P-OTHER').status_code,201)
        other=TestClient(app,base_url='https://testserver');self.staff_clients.append(other);other.post('/api/v1/account/login',json={'username':'787101','password':'tf-secret-12345'})
        self.assertEqual(other.get(self.base).json(),[])
        for suffix in ['/preview','/archive']:self.assertEqual(other.post(path+suffix,json={'expected_revision':1}).status_code,404)
        self.assertEqual(other.get(path).status_code,404);self.assertEqual(other.put(path,json={'expected_revision':1,'sheet':self.sheet()}).status_code,404)
        self.assertEqual(self.client.get(path).status_code,403)

    def test_single_train_and_empty_pdf_fields_struck(self):
        from lokzeitleiste.national_brake_sheets import Sheet,calculate
        from lokzeitleiste.national_brake_image import Drawing,render
        from sqlalchemy.orm import Session
        sheet=Sheet(**self.sheet(trains=[dict(number='00123',station='B')],last_vehicle='',brakes_d=None))
        with Session(self.engine) as db:result=calculate(db,sheet)
        with patch.object(Drawing,'strike',autospec=True) as struck:
            render(sheet,result,'Test TF')
            boxes=[tuple(c.args[1:]) for c in struck.call_args_list]
        self.assertIn((278,226,130,17),boxes)
        self.assertIn((278,271,42,14),boxes)
        self.assertIn((82,534,196,22),boxes)
        self.assertNotIn((278,126,42,15),boxes)

    def test_zero_is_printed_not_struck(self):
        from lokzeitleiste.national_brake_sheets import Sheet,calculate
        from lokzeitleiste.national_brake_image import Drawing,render
        from sqlalchemy.orm import Session
        sheet=Sheet(**self.sheet(brakes_single=0,brakes_multi=0,brakes_d=0,brakes_k=0,brakes_matrossow=0))
        with Session(self.engine) as db:result=calculate(db,sheet)
        with patch.object(Drawing,'strike',autospec=True) as struck:
            render(sheet,result,'Test TF')
        boxes=[tuple(c.args[1:]) for c in struck.call_args_list]
        for y in [243,257,271,285,299]:self.assertNotIn((278,y,42,14),boxes)

    def test_speeds_and_uniform_results_with_red_deficit(self):
        from lokzeitleiste.national_brake_sheets import Sheet,calculate
        from lokzeitleiste.national_brake_image import Drawing,render
        from sqlalchemy.orm import Session
        for value in [0,5000]:self.assertEqual(self.driver.post(self.base+'/calculate',json=self.sheet(speeds=[dict(lower=True,value=value),{},{}])).status_code,200)
        sheet=Sheet(**self.sheet())
        with Session(self.engine) as db:result=calculate(db,sheet)
        with patch.object(Drawing,'text',autospec=True) as text:
            render(sheet,result,'Test TF')
        highlighted=[c for c in text.call_args_list if c.kwargs.get('color')=='#0645ad']
        self.assertEqual(len(highlighted),0)
        red=[c for c in text.call_args_list if c.kwargs.get('color')=='#c40000']
        self.assertEqual(len(red),1)
        self.assertEqual(red[0].args[3],result['missing'])
        with patch.object(Drawing,'text',autospec=True) as normal:
            render(sheet,dict(result,missing='/'),'Test TF')
        self.assertFalse(any(c.kwargs.get('color')=='#c40000' for c in normal.call_args_list))
        numeric_results=[c for c in text.call_args_list if len(c.args)>3 and c.args[3] in (result['available'],result['missing'],result['required_axles'])]
        self.assertTrue(numeric_results)
        self.assertTrue(all(c.args[4]==7 and not c.kwargs.get('bold',False) for c in numeric_results))
