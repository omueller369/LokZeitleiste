import unittest
import csv
from pathlib import Path
import test_accounts
from lokzeitleiste.i18n import catalog,translate,language,display
from lokzeitleiste.pdf_locale import markup


class I18nTest(unittest.TestCase):
    setUp=test_accounts.AccountsTest.setUp
    tearDown=test_accounts.AccountsTest.tearDown

    def test_seven_complete_catalogues_and_arabic_display(self):
        data=catalog();self.assertEqual(set(data),{'de','en','pl','ru','tr','ar','es'})
        for lang in data:self.assertEqual(set(data[lang]),set(data['de']));self.assertTrue(all(data[lang].values()))
        self.assertEqual(translate('Speichern','en'),'Save')
        self.assertEqual(translate('2. Personalplanung','es'),'2. Planificación de personal')
        self.assertEqual(language('pl-PL, en;q=0.8'),'pl');self.assertEqual(language('xx'),'de')
        self.assertNotEqual(display('Speichern','ar'),translate('Speichern','ar'))
        result=markup('<b>Speichern</b> &lt;Mira&gt;','ar')
        self.assertTrue(result.startswith('<b>'));self.assertIn('</b>',result);self.assertNotIn('<Mira>',result)
        root=Path(__file__).resolve().parents[2]
        self.assertEqual((root/'backend/lokzeitleiste/locales/catalog.json').read_bytes(),(root/'app/src/main/assets/catalog.json').read_bytes())

    def test_individual_locale_persistence_validation_and_api_errors(self):
        path='/api/v1/account/locale'
        self.assertEqual(self.client.get(path).json(),{'language':'de','configured':False})
        for lang in ['en','pl','ru','tr','ar','es','de']:
            response=self.client.put(path,json={'language':lang})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(self.client.get(path).json(),{'language':lang,'configured':True})
        self.assertEqual(self.client.put(path,json={'language':'xx'}).status_code,422)
        response=self.client.get('/api/v1/admin/tf/99999/hours/2026',headers={'Accept-Language':'en'})
        self.assertEqual(response.status_code,404);self.assertEqual(response.json()['detail'],'Train driver not found')
        self.client.post('/api/v1/admin/logout')
        self.assertEqual(self.client.get(path).status_code,401)
