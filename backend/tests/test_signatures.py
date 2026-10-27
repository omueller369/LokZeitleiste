import io,unittest
from unittest.mock import patch
from PIL import Image,ImageDraw,ImageChops
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import test_brake_sheets
from lokzeitleiste.main import app
from lokzeitleiste.models import UserSignature

def sample(white=False,variant=False):
    image=Image.new('RGBA',(500,160),'white' if white else (0,0,0,0));d=ImageDraw.Draw(image)
    d.line([(20,100),(80,30),(100,120),(240 if not variant else 340,60)],fill='black',width=5)
    output=io.BytesIO();image.save(output,format='PNG');return output.getvalue()
class SignatureTest(unittest.TestCase):
    setUp=test_brake_sheets.BrakeSheetTest.setUp
    tearDown=test_brake_sheets.BrakeSheetTest.tearDown
    data=test_brake_sheets.BrakeSheetTest.data
    create=test_brake_sheets.BrakeSheetTest.create
    sheet=test_brake_sheets.BrakeSheetTest.sheet
    base='/api/v1/tf/me/signature'
    def test_private_transparent_replace_and_validation(self):
        self.assertEqual(self.driver.get(self.base).status_code,404)
        first=self.driver.put(self.base,files={'file':('sig.png',sample(True),'image/png')});self.assertEqual(first.status_code,200,first.text)
        im=Image.open(io.BytesIO(first.content));self.assertEqual(im.mode,'RGBA');self.assertEqual(im.getpixel((0,0))[3],0);self.assertIsNotNone(im.getchannel('A').getbbox());self.assertIn('no-store',first.headers['cache-control'])
        second=self.driver.put(self.base,files={'file':('sig.png',sample(variant=True),'image/png')});self.assertEqual(second.status_code,200);self.assertNotEqual(first.content,second.content)
        self.assertEqual(self.driver.get(self.base).content,second.content)
        self.assertEqual(self.client.get(self.base).status_code,403)
        self.assertEqual(self.create_tf('787101','P-SIG-OTHER').status_code,201)
        other=TestClient(app,base_url='https://testserver');self.staff_clients.append(other);other.post('/api/v1/account/login',json={'username':'787101','password':'tf-secret-12345'})
        self.assertEqual(other.get(self.base).status_code,404)
        for data,code in [(b'not image',422),(b'a'*(1024*1024+1),413)]:self.assertEqual(self.driver.put(self.base,files={'file':('sig.png',data,'image/png')}).status_code,code)
        empty=io.BytesIO();Image.new('RGBA',(100,100),(0,0,0,0)).save(empty,format='PNG')
        self.assertEqual(self.driver.put(self.base,files={'file':('empty.png',empty.getvalue(),'image/png')}).status_code,422)
        self.assertEqual(self.driver.get(self.base).content,second.content)
    def test_signature_appears_only_in_field40_and_flows_through_preview_archive_mail(self):
        from uuid import uuid4
        from datetime import datetime
        from lokzeitleiste.brake_sheets import Sheet,calculate
        from lokzeitleiste.brake_sheet_image import render
        sheet=Sheet(**self.sheet(departure_date='2026-10-27',station_from='B',station_to='BHBF',first_vehicle='918061850012',last_vehicle='918061850053',countries=[dict(country='DE',category='G'),dict(country='PL',category='P'),{},{}],wagon=dict(count=20,length=200,brake=700,weight=1000)))
        self.driver.put(self.base,files={'file':('sig.png',sample(),'image/png')});signature=self.driver.get(self.base).content
        with Session(self.engine) as db:r=calculate(db,sheet)
        normal=Image.open(io.BytesIO(render(sheet,r,datetime(2026,10,27,10),'Test TF'))).convert('RGB')
        signed=Image.open(io.BytesIO(render(sheet,r,datetime(2026,10,27,10),'Test TF',signature=signature))).convert('RGB')
        bounds=ImageChops.difference(normal,signed).getbbox();self.assertIsNotNone(bounds)
        sx=normal.width/1335;sy=normal.height/1888
        self.assertGreaterEqual(bounds[0],int(502*sx));self.assertLessEqual(bounds[2],round(885*sx));self.assertGreaterEqual(bounds[1],int(1751*sy));self.assertLessEqual(bounds[3],round(1771*sy))
        path='/api/v1/tf/brake-sheets/'+str(uuid4());self.assertEqual(self.driver.put(path,json={'expected_revision':0,'sheet':sheet.model_dump(mode='json')}).status_code,200)
        with patch('lokzeitleiste.brake_sheet_image.render',wraps=render) as renderer:
            self.assertEqual(self.driver.post(path+'/preview',json={'expected_revision':1}).status_code,200)
            self.assertEqual(renderer.call_args.kwargs['signature'],signature)
        with patch('lokzeitleiste.brake_sheet_image.render_pdf',return_value=b'%PDF-test') as pdf:
            self.assertEqual(self.driver.post(path+'/archive',json={'expected_revision':1}).status_code,200)
            self.assertEqual(pdf.call_args.kwargs['signature'],signature)
        with patch('lokzeitleiste.brake_sheet_mail.render',return_value=b'PNG') as png,patch('lokzeitleiste.brake_sheet_mail.render_pdf',return_value=b'%PDF-test') as pdf:
            self.assertEqual(self.driver.post(path+'/mail',json={'expected_revision':1}).status_code,200)
            self.assertEqual(png.call_args.kwargs['signature'],signature);self.assertEqual(pdf.call_args.kwargs['signature'],signature)
