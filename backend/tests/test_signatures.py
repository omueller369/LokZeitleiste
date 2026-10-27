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
        im=Image.open(io.BytesIO(first.content));self.assertEqual(im.mode,'RGBA');self.assertEqual(im.getpixel((0,0))[3],0);self.assertEqual(im.getchannel('A').getbbox(),(0,0,im.width,im.height));self.assertIn('no-store',first.headers['cache-control'])
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
        self.assertGreaterEqual(bounds[0],int(502*sx));self.assertLessEqual(bounds[2],round(889*sx));self.assertGreaterEqual(bounds[1],int(1730*sy));self.assertLessEqual(bounds[3],round(1775*sy))
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

    def test_render_trims_legacy_margins_and_enlarges_small_signature(self):
        from lokzeitleiste.signatures import normalize
        from lokzeitleiste.brake_sheet_image import render,TEMPLATE
        from lokzeitleiste.brake_sheets import Sheet,calculate
        from datetime import datetime
        from sqlalchemy.orm import Session
        image=Image.new('RGBA',(1000,500),(0,0,0,0));ImageDraw.Draw(image).rectangle((490,245,509,254),fill='black')
        raw=io.BytesIO();image.save(raw,format='PNG')
        trimmed=Image.open(io.BytesIO(normalize(raw.getvalue())));self.assertEqual(trimmed.size,(20,10))
        sheet=Sheet(**self.sheet(departure_date='2026-10-27'))
        with Session(self.engine) as db:result=calculate(db,sheet)
        with Image.open(TEMPLATE) as source:w,h=source.size
        signed=Image.open(io.BytesIO(render(sheet,result,datetime(2026,10,27),'Test TF',transparent=True,signature=raw.getvalue()))).convert('RGBA')
        x0,y0,x1,y1=round(702*w/1335),round(1732*h/1888),round(886*w/1335),round(1773*h/1888)
        bounds=signed.getchannel('A').crop((x0,y0,x1,y1)).getbbox();self.assertIsNotNone(bounds)
        self.assertGreaterEqual(bounds[3]-bounds[1],y1-y0-1)
    def test_positioned_capture_background_geometry_and_exact_pdf_position(self):
        import json
        from lokzeitleiste.models import UserSignaturePlacement,User
        from lokzeitleiste.signatures import VIEWPORT
        from lokzeitleiste.brake_sheet_image import render
        from lokzeitleiste.brake_sheets import Sheet,calculate
        from datetime import datetime
        from sqlalchemy import select
        # The ink intentionally crosses field 40's upper/right borders.
        image=Image.new('RGBA',(1000,500),(0,0,0,0));ImageDraw.Draw(image).rectangle((600,100,899,349),fill='black')
        raw=io.BytesIO();image.save(raw,format='PNG')
        guide=self.driver.get(self.base+'/background');self.assertEqual(guide.status_code,200)
        self.assertEqual(Image.open(io.BytesIO(guide.content)).size,(1000,500))
        self.assertEqual(self.client.get(self.base+'/background').status_code,403)
        saved=self.driver.put(self.base,data={'capture_mode':'field40-v1'},files={'file':('sig.png',raw.getvalue(),'image/png')});self.assertEqual(saved.status_code,200,saved.text)
        ink=Image.open(io.BytesIO(saved.content));self.assertEqual(ink.size,(300,250));self.assertEqual(ink.mode,'RGBA')
        with Session(self.engine) as db:
            user=db.scalar(select(User).where(User.username=='787100'));placement=db.get(UserSignaturePlacement,user.id);geometry=json.loads(placement.geometry_json)
            self.assertEqual(geometry,[820.0,1710.0,90.0,75.0])
            sheet=Sheet(**self.sheet(departure_date='2026-10-27'));result=calculate(db,sheet)
        rendered=Image.open(io.BytesIO(render(sheet,result,datetime(2026,10,27),'Mira Beispiel',transparent=True,signature=saved.content,signature_position=geometry)))
        sx=rendered.width/1335;sy=rendered.height/1888
        # Signature keeps its captured extents; it is not fitted inside the field.
        self.assertGreater(rendered.getpixel((round(900*sx),round(1780*sy)))[3],200)
        self.assertEqual(self.driver.put(self.base,data={'capture_mode':'wrong'},files={'file':('sig.png',raw.getvalue(),'image/png')}).status_code,422)
        self.assertEqual(self.driver.put(self.base,data={'capture_mode':'field40-v1'},files={'file':('sig.png',sample(),'image/png')}).status_code,422)
        self.assertEqual(self.driver.put(self.base,files={'file':('sig.png',sample(),'image/png')}).status_code,200)
        with Session(self.engine) as db:self.assertIsNone(db.get(UserSignaturePlacement,user.id))
    def test_left_name_guide_and_v2_capture_match(self):
        import json
        from lokzeitleiste.signatures import guide_layout
        from lokzeitleiste.models import User,UserSignaturePlacement
        from lokzeitleiste.brake_sheet_image import TEMPLATE,field40_name
        from sqlalchemy import select
        with Image.open(TEMPLATE) as source:original=source.convert('RGB')
        named=original.copy();field40_name(named,'Oliver Müller')
        box=ImageChops.difference(original,named).getbbox();sx=original.width/1335
        self.assertLess(box[0],510*sx);self.assertLess(box[2],698*sx)
        image=Image.new('RGBA',(1000,500),(0,0,0,0));ImageDraw.Draw(image).rectangle((500,200,799,299),fill='black');raw=io.BytesIO();image.save(raw,format='PNG')
        r=self.driver.put(self.base,data={'capture_mode':'field40-left-v2'},files={'file':('sig.png',raw.getvalue(),'image/png')});self.assertEqual(r.status_code,200,r.text)
        with Session(self.engine) as db:
            user=db.scalar(select(User).where(User.username=='787100'));geometry=json.loads(db.get(UserSignaturePlacement,user.id).geometry_json)
        _,viewport=guide_layout('Mira Beispiel');x0,y0,x1,y1=viewport
        self.assertAlmostEqual(geometry[0],x0+(x1-x0)*.5);self.assertAlmostEqual(geometry[1],y0+(y1-y0)*.4)
        self.assertAlmostEqual(geometry[2],(x1-x0)*.3);self.assertAlmostEqual(geometry[3],(y1-y0)*.2)
        guide=self.driver.get(self.base+'/background?mode=field40-left-v2');self.assertEqual(guide.status_code,200);self.assertEqual(Image.open(io.BytesIO(guide.content)).size,(1000,500))
