"""Synthetic XLSX fixtures for dynamic rows and exact import arithmetic."""
from io import BytesIO
from decimal import Decimal
import unittest
from openpyxl import Workbook
from lokzeitleiste.wagon_import import parse, ImportError
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

class WagonImportTest(unittest.TestCase):
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
    def test_upload_validation(self):
        for name,content,mode in [('file.xls',workbook(),'G'),('file.xlsx',b'broken','G'),('file.xlsx',workbook(missing_p=True),'G+P')]:
            response=self.driver.post(self.base+'/import-wagons',files={'file':(name,content)},data={'mode':mode});self.assertEqual(response.status_code,422,response.text)
