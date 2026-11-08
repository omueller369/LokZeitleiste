"""Synthetic XLSX fixtures for dynamic rows and exact import arithmetic."""
from io import BytesIO
from decimal import Decimal
import unittest
from openpyxl import Workbook, load_workbook
from lokzeitleiste.wagon_import import parse, number, ImportError
import test_brake_sheets


def workbook(count=8, offset=0, missing_p=False, length='15.01', total=True):
    book=Workbook();sheet=book.active;sheet.title='Dynamic'
    for col,text in [(4,'Gültig ab Bhf.'),(5,'Gültig bis Bhf.')]:sheet.cell(4+offset,col,text)
    sheet.cell(5+offset,4,'Origin Station');sheet.cell(5+offset,5,'FIRST SECOND THIRD')
    for col,value in [(1,'Pos.'),(2,'Fahrzeugnummer'),(4,'LüP [m]'),(6,'Gesamt gewicht'),(8,'Bremsgewicht')]:sheet.cell(8+offset,col,value)
    sheet.cell(9+offset,8,'P');sheet.cell(9+offset,9,'G')
    for i in range(count):
        row=10+offset+i
        for col,value in [(1,i+1),(2,str(330000000000+i)),(4,length),(6,'80.01'),(9,59)]:sheet.cell(row,col,value)
        if not missing_p:sheet.cell(row,8,70)
    if total:
        row=10+offset+count;sheet.cell(row,2,'Summe:');sheet.cell(row,4,float(Decimal(length)*count));sheet.cell(row,6,float(Decimal('80.01')*count));sheet.cell(row,9,59*count)
        if not missing_p:sheet.cell(row,8,70*count)
    output=BytesIO();book.save(output);book.close();return output.getvalue()

def p_text_workbook():
    from zipfile import ZipFile
    from xml.etree import ElementTree as ET
    data=workbook(30);out=BytesIO();ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with ZipFile(BytesIO(data)) as original,ZipFile(out,'w') as target:
        for item in original.infolist():
            content=original.read(item.filename)
            if item.filename=='xl/worksheets/sheet1.xml':
                root=ET.fromstring(content)
                for row in root.findall('m:sheetData/m:row',ns):
                    for cell in list(row):
                        address=cell.attrib.get('r','')
                        if address.startswith('I') and address[1:].isdigit() and 10<=int(address[1:])<=39:row.remove(cell)
                        elif address.startswith('H') and address[1:].isdigit() and 15<=int(address[1:])<=39:
                            cell.clear();cell.set('r',address);cell.set('t','inlineStr');inline=ET.SubElement(cell,'{'+ns['m']+'}is');ET.SubElement(inline,'{'+ns['m']+'}t').text='70'
                        elif address in ['H40','I40']:
                            cell.clear();cell.set('r',address);ET.SubElement(cell,'{'+ns['m']+'}v').text='350'
                content=ET.tostring(root)
            target.writestr(item,content)
    return out.getvalue()

def all_text_workbook(count=8,offset=0,total=True):
    book=load_workbook(BytesIO(workbook(count,offset,total=total)));sheet=book.active
    sheet.cell(8+offset,5,'Ladungs- gewicht \\ Masa ładunku [t]')
    values={4:'15,01',5:'24,50',6:'80,01',8:'70',9:'59'}
    for i in range(count):
        for column,value in values.items():sheet.cell(10+offset+i,column,float(value.replace(',','.')) if i<2 else '\u00a0'+value+' ')
    if total:
        for column,value in values.items():sheet.cell(10+offset+count,column,float(Decimal(value.replace(',','.'))*2))
    out=BytesIO();book.save(out);book.close();return out.getvalue()

def mixed_workbook(count=8,length='15.01',zeros=False):
    book=load_workbook(BytesIO(workbook(count,length=length)))
    sheet=book.active
    for index in range(count):
        sheet.cell(10+index,8 if index<5 else 9).value=0 if zeros else None
    sheet.cell(10+count,8).value=70*max(0,count-5)
    sheet.cell(10+count,9).value=59*min(count,5)
    out=BytesIO();book.save(out);book.close();return out.getvalue()

class WagonImportTest(unittest.TestCase):
    def test_mixed_import_choices_have_independent_exact_arithmetic(self):
        for zeros in (False,True):
            source=parse(mixed_workbook(10,length='51.001',zeros=zeros))['wagon_import']
            self.assertEqual(source.detected_mode(),'G+P')
            for policy,mode,expected in [('all_g','G',645),('mixed','G+P',572),('unchanged','G+P',645)]:
                chosen=source.model_copy(update={'brake_policy':policy})
                self.assertEqual(chosen.values(mode)['brake'],expected)
                if policy=='mixed':
                    self.assertEqual(chosen.brake_components(mode),
                        dict(g=Decimal(295),g_counted=Decimal('221.25'),p=Decimal(350),p_counted=Decimal(350),total=Decimal('571.25')))
                restored=type(chosen).model_validate_json(chosen.model_dump_json())
                self.assertEqual(restored.values(mode),chosen.values(mode))
            self.assertEqual(source.brake_policy,'standard')
            self.assertEqual(source.values('G+P')['brake'],554)

    def test_numeric_text_formats(self):
        for text in ['2640,08','2640.08','2.640,08','2,640.08','2\u202f640,08']:
            self.assertEqual(number(text),Decimal('2640.08'))
        for text in ['unknown','NaN','Infinity','-1','=SUM(D10:D17)','1.2,3','1,23.4']:
            with self.assertRaises(ImportError):number(text)
    def test_dynamic_rows_and_first_word(self):
        for count,offset in [(2,0),(8,3),(30,5)]:
            result=parse(workbook(count,offset));source=result['wagon_import'];values=source.values('G')
            self.assertEqual(result['station_to'],'FIRST');self.assertEqual(result['station_from'],'Origin Station')
            self.assertEqual(result['last_vehicle'],str(330000000000+count-1));self.assertEqual(values['count'],count);self.assertEqual(values['brake'],59*count)
            self.assertEqual(values['length'],int((Decimal('15.01')*count).to_integral_value(rounding='ROUND_CEILING')));self.assertEqual(source.total_row,10+offset+count)
    def test_round_once_and_500m_boundary(self):
        for length,expected in [('50',572),('50.001',554)]:
            self.assertEqual(parse(workbook(10,length=length))['wagon_import'].values('G+P')['brake'],expected)
        self.assertEqual(parse(workbook(5))['wagon_import'].values('G+P')['brake'],222)
    def test_missing_p_and_no_summary(self):
        source=parse(workbook(missing_p=True))['wagon_import'];self.assertEqual(source.values('G')['brake'],472)
        for mode in ['P','G+P']:
            with self.assertRaisesRegex(ImportError,'missing_brake'):source.values(mode)
        self.assertEqual(parse(workbook(total=False))['wagon_import'].values('P')['brake'],560)
    def test_stale_brake_summary_is_rejected(self):
        source=parse(workbook())['wagon_import'];source.g_total=Decimal(1000)
        with self.assertRaisesRegex(ImportError,'format'):source.values('G')

    def test_text_numbers_and_incorrect_summary(self):
        source=parse(p_text_workbook())['wagon_import']
        self.assertEqual(source.detected_mode(),'P');self.assertEqual(source.p_total,2100);self.assertIsNone(source.g_total)
        self.assertEqual(source.reported_p_total,350);self.assertEqual(source.values('P')['brake'],2100)
        self.assertEqual({d['column'] for d in source.summary_differences()},{'G','P'})

    def test_unambiguous_mode_detection(self):
        source=parse(workbook())['wagon_import'];self.assertIsNone(source.detected_mode())
        for index,row in enumerate(source.rows):
            if index<5:row.p=None
            else:row.g=None
        self.assertEqual(source.detected_mode(),'G+P');self.assertEqual(source.values('G+P')['brake'],432)

    def test_all_numeric_columns_recomputed_from_text(self):
        for count,offset,total in [(8,0,True),(12,3,True),(30,5,False)]:
            source=parse(all_text_workbook(count,offset,total))['wagon_import'];values=source.values('G')
            for field,per_wagon in [('length','15.01'),('cargo','24.50'),('weight','80.01'),('p','70'),('g','59')]:
                self.assertEqual(getattr(source,field+'_total'),Decimal(per_wagon)*count)
            self.assertEqual(values['weight'],int((Decimal('80.01')*count).to_integral_value(rounding='ROUND_CEILING')))
            self.assertEqual([c['column'] for c in source.column_totals()],['D','E','F','H','I'])
            self.assertEqual(len(source.summary_differences()),5 if total else 0)
            self.assertEqual(source.reported_length_total,Decimal('30.02') if total else None)
    def test_non_numeric_text_and_tampered_totals_are_rejected(self):
        book=load_workbook(BytesIO(all_text_workbook()));book.active['F10']='unknown';out=BytesIO();book.save(out);book.close()
        with self.assertRaisesRegex(ImportError,'format'):parse(out.getvalue())
        for field in ('length_total','weight_total'):
            source=parse(all_text_workbook())['wagon_import'];setattr(source,field,Decimal(400))
            with self.assertRaisesRegex(ImportError,'format'):source.values('G')

    def test_invalid_file_and_mode(self):
        for content in [b'not xlsx',b'x'*(5*1024*1024+1)]:
            with self.assertRaises(ImportError):parse(content)
        with self.assertRaisesRegex(ImportError,'mode'):parse(workbook())['wagon_import'].values('R')

class WagonImportApiTest(unittest.TestCase):
    setUp=test_brake_sheets.BrakeSheetTest.setUp
    tearDown=test_brake_sheets.BrakeSheetTest.tearDown
    data=test_brake_sheets.BrakeSheetTest.data
    create=test_brake_sheets.BrakeSheetTest.create
    sheet=test_brake_sheets.BrakeSheetTest.sheet
    base=test_brake_sheets.BrakeSheetTest.base
    def test_preview_calculation_round_trip_and_permissions(self):
        response=self.driver.post(self.base+'/import-wagons',files={'file':('wagons.xlsx',workbook())},data={'mode':'G+P'})
        self.assertEqual(response.status_code,200,response.text);payload=response.json()
        self.assertEqual(payload['station_to'],'FIRST');self.assertEqual(payload['wagon']['brake'],432);self.assertEqual(self.driver.get(self.base).json(),[])
        data=self.sheet(wagon_import=payload['wagon_import'],wagon=payload['wagon'],brake_mode='G+P')
        result=self.driver.post(self.base+'/calculate',json=data);self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['b']['brake'],432);self.assertEqual(Decimal(str(result.json()['a']['brake'])),Decimal(str(self.vehicle['brake_g_25'])))
        data['brake_mode']='P';result=self.driver.post(self.base+'/calculate',json=data);self.assertEqual(result.json()['b']['brake'],560)
        from uuid import uuid4
        draft=self.driver.put(self.base+'/'+str(uuid4()),json={'expected_revision':0,'sheet':data});self.assertEqual(draft.status_code,200,draft.text)
        saved=self.driver.get(self.base+'/'+draft.json()['id']).json();self.assertEqual(saved['sheet']['wagon_import']['sheet'],'Dynamic');self.assertEqual(saved['calculation']['b']['brake'],560)
        response=self.client.post(self.base+'/import-wagons',files={'file':('wagons.xlsx',workbook())});self.assertEqual(response.status_code,403)
    def test_mixed_choices_are_explicit_and_survive_save_reload(self):
        from uuid import uuid4
        response=self.driver.post(self.base+'/import-wagons',files={'file':('mixed.xlsx',mixed_workbook())},data={'mode':'G'})
        self.assertEqual(response.status_code,200,response.text)
        choices={choice['policy']:choice for choice in response.json()['choices']}
        self.assertEqual(set(choices),{'all_g','mixed','unchanged'})
        for policy,total in [('all_g',505),('mixed',432),('unchanged',505)]:
            choice=choices[policy]
            data=self.sheet(wagon_import=choice['wagon_import'],wagon=choice['wagon'],brake_mode=choice['brake_mode'])
            saved=self.driver.put(self.base+'/'+str(uuid4()),json={'expected_revision':0,'sheet':data})
            self.assertEqual(saved.status_code,200,saved.text)
            reread=self.driver.get(self.base+'/'+saved.json()['id']).json()
            self.assertEqual(reread['sheet']['wagon_import']['brake_policy'],policy)
            self.assertEqual(reread['calculation']['b']['brake'],total)
        g=choices['all_g']
        self.assertTrue(all(row['position']=='G' for row in g['rows']))
        self.assertEqual([row['brake'] for row in g['rows']][-3:],[70,70,70])
        self.assertEqual({row['column']:row['total'] for row in g['column_totals']}['I'],505)
        self.assertEqual({row['column']:row['total'] for row in g['column_totals']}['H'],0)

    def test_mode_proposal_and_summary_warnings_do_not_save(self):
        response=self.driver.post(self.base+'/import-wagons',files={'file':('wagons.xlsx',p_text_workbook())},data={'mode':'G'})
        self.assertEqual(response.status_code,200,response.text);data=response.json()
        self.assertEqual(data['requested_brake_mode'],'G');self.assertEqual(data['brake_mode'],'P');self.assertEqual(data['wagon']['brake'],2100)
        self.assertEqual(len(data['notices']),3);self.assertTrue(any('350' in text and '2100' in text for text in data['notices']))
        self.assertEqual(self.driver.get(self.base).json(),[])
        # This proposes G, rather than making up missing P values.
        response=self.driver.post(self.base+'/import-wagons',files={'file':('wagons.xlsx',workbook(missing_p=True))},data={'mode':'G+P'})
        self.assertEqual(response.status_code,200,response.text);self.assertEqual(response.json()['brake_mode'],'G')

    def test_upload_validation(self):
        for name,content,mode in [('file.xls',workbook(),'G'),('file.xlsx',b'broken','G')]:
            response=self.driver.post(self.base+'/import-wagons',files={'file':(name,content)},data={'mode':mode});self.assertEqual(response.status_code,422,response.text)

    def test_all_column_totals_preview_and_saved_calculation(self):
        response=self.driver.post(self.base+'/import-wagons',files={'file':('text.xlsx',all_text_workbook())},data={'mode':'G'})
        self.assertEqual(response.status_code,200,response.text);payload=response.json()
        self.assertEqual(len(payload['notices']),5);self.assertTrue(any('30.02 m' in n and '120.08 m' in n for n in payload['notices']))
        totals={c['column']:Decimal(str(c['total'])) for c in payload['column_totals']}
        self.assertEqual(totals,{'D':Decimal('120.08'),'E':Decimal('196'),'F':Decimal('640.08'),'H':Decimal('560'),'I':Decimal('472')})
        data=self.sheet(wagon_import=payload['wagon_import'],wagon=payload['wagon'],brake_mode='G')
        result=self.driver.post(self.base+'/calculate',json=data);self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['b']['weight'],641);self.assertEqual(result.json()['b']['length'],121)
        self.assertEqual(result.json()['b']['brake'],472)
        from uuid import uuid4
        saved=self.driver.put(self.base+'/'+str(uuid4()),json={'expected_revision':0,'sheet':data})
        self.assertEqual(saved.status_code,200,saved.text)
        restored=self.driver.get(self.base+'/'+saved.json()['id']).json()
        self.assertEqual(Decimal(str(restored['sheet']['wagon_import']['cargo_total'])),Decimal('196'))
        self.assertEqual(restored['calculation']['b']['weight'],641)
