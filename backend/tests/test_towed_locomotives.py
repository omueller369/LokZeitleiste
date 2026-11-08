import unittest
from uuid import uuid4
from decimal import Decimal
from unittest.mock import patch
from io import BytesIO
from PIL import ImageDraw
from pypdf import PdfReader
import test_brake_sheets

class TowedLocomotiveTest(unittest.TestCase):
    setUp=test_brake_sheets.BrakeSheetTest.setUp
    tearDown=test_brake_sheets.BrakeSheetTest.tearDown
    data=test_brake_sheets.BrakeSheetTest.data
    create=test_brake_sheets.BrakeSheetTest.create
    sheet=test_brake_sheets.BrakeSheetTest.sheet
    base=test_brake_sheets.BrakeSheetTest.base
    def payload(self,zero=False,two=True):
        head=self.create(vehicle_number='91 80 6185 002-0',length_m='30',weight_kg=90000,axle_count=6,brake_shoe='D')
        tail=self.create(vehicle_number='91 80 6185 003-8',length_m='10',weight_kg=80000,axle_count=4,brake_shoe='D')
        imported=dict(rows=[dict(number=str(330000000000+i),length='80',weight='80',g='40',p='80') for i in range(6)],sheet='Test',first_row=10,last_row=15,total_row=16,length_total='480',weight_total='480',g_total='240',p_total='480')
        towed=[dict(vehicle_id=head['id'],vehicle_revision=1,position=1,brake_position='G',brake_weight='80',count_g=not zero,destination='Stop X',stop_order=1)]
        if two:towed.append(dict(vehicle_id=tail['id'],vehicle_revision=1,position=8,brake_position='P',brake_weight='60',destination='Stop Y',stop_order=2))
        return self.sheet(departure_date='2026-11-04',station_from='Origin',station_to='Final',brake_mode='G+P',remarks='User remark',countries=[dict(country='DE',category='G',vmax=100),dict(country='PL',category='G',vmax=100),{},{}],required_percent=59,wagon_import=imported,wagon=dict(count=6,length=480,weight=480,brake=230),towed=towed)
    def save(self,payload,id=None,revision=0):
        response=self.driver.put(self.base+'/'+(id or str(uuid4())),json=dict(expected_revision=revision,sheet=payload));self.assertEqual(response.status_code,200,response.text);return response.json()
    def test_ordered_dropoffs_and_recomputed_boundaries(self):
        saved=self.save(self.payload());self.assertEqual(saved['sheet']['station_to'],'Stop X');self.assertEqual(saved['sheet']['final_station'],'Final');self.assertEqual(len(saved['sections']),3)
        results=[self.driver.get(self.base+'/'+link['id']).json() for link in saved['sections']]
        self.assertEqual([(x['sheet']['station_from'],x['sheet']['station_to']) for x in results],[('Origin','Stop X'),('Stop X','Stop Y'),('Stop Y','Final')])
        for key,expected in [('count',[8,7,6]),('length',[520,490,480]),('weight',[650,560,480]),('brake',[389,290,230])]:self.assertEqual([x['calculation']['b'][key] for x in results],expected)
        self.assertEqual([x['sheet']['first_vehicle'] for x in results],['918061850020','330000000000','330000000000'])
        self.assertEqual([x['sheet']['last_vehicle'] for x in results],['918061850038','918061850038','330000000005'])
        self.assertIn('918061850020',results[0]['calculation']['special']);self.assertIn('Stop X',results[0]['calculation']['special']);self.assertNotIn('918061850020',results[1]['calculation']['special']);self.assertEqual(results[2]['calculation']['special'],'')
        for result in results:self.assertEqual(Decimal(str(result['calculation']['a']['brake'])),Decimal(75))
        self.assertEqual(results[1]['sheet']['towed'][0]['position'],7)
        child=results[1];self.assertEqual(self.driver.put(self.base+'/'+child['id'],json=dict(expected_revision=child['revision'],sheet=child['sheet'])).status_code,409)
    def test_zero_g_still_counts_vehicle_length_and_weight(self):
        payload=self.payload(zero=True,two=False);result=self.save(payload)['calculation'];self.assertEqual(result['b'],dict(count=7,length=510,weight=570,holding=None,brake=272));self.assertEqual(result['towed'][0]['brake_weight'],0)
        payload['towed'][0]['count_g']=None;self.assertEqual(self.driver.post(self.base+'/calculate',json=payload).status_code,422)
    def test_reject_duplicate_positions_vehicles_and_stop_order(self):
        payload=self.payload();payload['towed'][1]['position']=1;self.assertEqual(self.driver.post(self.base+'/calculate',json=payload).status_code,422)
        payload['towed'][1]['position']=8;payload['towed'][1]['stop_order']=1;self.assertEqual(self.driver.post(self.base+'/calculate',json=payload).status_code,422)
        payload['towed'][1]['stop_order']=2;payload['towed'][0]['vehicle_id']=self.vehicle['id'];self.assertEqual(self.driver.post(self.base+'/calculate',json=payload).status_code,422)
        payload['wagon_import']=None;self.assertEqual(self.driver.post(self.base+'/calculate',json=payload).status_code,422)
    def test_idempotent_regeneration_and_superseded_sections(self):
        saved=self.save(self.payload());initial=[x['id'] for x in saved['sections']]
        again=self.save(saved['sheet'],saved['id'],saved['revision']);self.assertEqual([x['id'] for x in again['sections']],initial)
        payload=again['sheet'];payload['towed']=[];final=self.save(payload,again['id'],again['revision']);self.assertEqual(final['sheet']['station_to'],'Final');self.assertEqual(len(final['sections']),1)
        self.assertFalse({x['id'] for x in self.driver.get(self.base).json()}&set(initial[1:]))
        stale=self.driver.get(self.base+'/'+initial[1]).json();self.assertTrue(stale['sheet']['section_superseded']);self.assertEqual(self.driver.post(self.base+'/'+stale['id']+'/preview',json={'expected_revision':stale['revision']}).status_code,422)
        self.assertEqual(self.client.get(self.base+'/'+final['id']).status_code,403)
    def test_pdf_notice_and_separate_documents(self):
        saved=self.save(self.payload());filenames=[];archived=[];texts=[];original=ImageDraw.ImageDraw.text
        def capture(draw,xy,value,*args,**kwargs):texts.append(str(value));return original(draw,xy,value,*args,**kwargs)
        for link in saved['sections']:
            result=self.driver.get(self.base+'/'+link['id']).json();self.assertEqual(result['calculation']['preview_missing'],[])
            with patch.object(ImageDraw.ImageDraw,'text',capture):response=self.driver.post(self.base+'/'+link['id']+'/archive',json={'expected_revision':result['revision']})
            self.assertEqual(response.status_code,200,response.text);filenames.append(response.json()['filename'])
            content=self.driver.get(response.json()['download_url']);archived.append((response.json()['download_url'],content.content));self.assertEqual(len(PdfReader(BytesIO(content.content)).pages),1)
        self.assertEqual(len(set(filenames)),3);self.assertTrue(all('-A0' in name for name in filenames));self.assertTrue(any('im Schlepp' in value for value in texts))
        again=self.save(saved['sheet'],saved['id'],saved['revision'])
        newer=self.driver.post(self.base+'/'+again['id']+'/archive',json={'expected_revision':again['revision']});self.assertEqual(newer.status_code,200,newer.text);self.assertNotIn(newer.json()['filename'],filenames)
        for url,content in archived:self.assertEqual(self.driver.get(url).content,content)

    def test_two_column_form_after_single_dropoff(self):
        payload=self.payload(two=False)
        payload['special']='Manual field 9'
        result=self.save(payload)['calculation']
        self.assertEqual(result['remarks'],'User remark')
        self.assertIn('Manual field 9',result['special'])
        self.assertIn('Tfz 918061850020 läuft von Origin bis Stop X im Schlepp an Position(en): 1 mit.',result['special'])
        second=result['second']
        self.assertEqual((second['station_from'],second['station_to']),('Stop X','Final'))
        after=second['calculation']
        self.assertEqual(after['first_vehicle'],'330000000000')
        self.assertEqual(after['last_vehicle'],'330000000005')
        self.assertEqual(after['b']['count'],6)
        self.assertEqual(after['b']['weight'],480)
        self.assertEqual(after['b']['length'],480)
        self.assertEqual(after['b']['brake'],230)
        self.assertEqual(after['total']['brake'],305)
        self.assertEqual(after['available'],54)
        self.assertEqual(after['missing'],-5)
        self.assertNotIn('second',after)

    def test_render_keeps_final_destination_and_fills_following_columns(self):
        from datetime import datetime
        from lokzeitleiste.brake_sheets import Sheet
        from lokzeitleiste.brake_sheet_image import render
        saved=self.save(self.payload(two=False))
        texts=[];original=ImageDraw.ImageDraw.text
        def capture(draw,xy,value,*args,**kwargs):
            texts.append((xy[0]/(draw._image.width/1335),xy[1]/(draw._image.height/1888),str(value)))
            return original(draw,xy,value,*args,**kwargs)
        with patch.object(ImageDraw.ImageDraw,'text',capture):
            render(Sheet(**saved['sheet']),saved['calculation'],datetime(2026,11,8),'Tester')
        self.assertTrue(any(323<=x<619 and 210<=y<236 and v=='Final' for x,y,v in texts))
        self.assertTrue(any(607<=x<833 and 627<=y<654 and v=='Stop X' for x,y,v in texts))
        self.assertTrue(any(843<=x<1069 and 627<=y<654 and v=='Stop X' for x,y,v in texts))
        self.assertTrue(any(1079<=x<1299 and 627<=y<654 and v=='Final' for x,y,v in texts))
        self.assertTrue(any(1006<=x<1139 and 860<=y<896 and v=='6' for x,y,v in texts))
        self.assertTrue(any(1148<=x<1299 and 1090<=y<1131 and v=='54' for x,y,v in texts))
        self.assertTrue(any(590<=x<1295 and 303<=y<591 and 'im Schlepp' in v for x,y,v in texts))

    def test_towed_to_final_has_notice_without_empty_following_section(self):
        payload=self.payload(two=False)
        payload['towed'][0]['destination']='Final'
        result=self.save(payload)['calculation']
        self.assertNotIn('second',result)
        self.assertIn('bis Final im Schlepp',result['special'])
        self.assertEqual(result['remarks'],'User remark')
