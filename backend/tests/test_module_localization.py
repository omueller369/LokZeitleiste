"""Module coverage, stable contracts, public locale assets and keyed output."""
import importlib.util
import json
import re
import unittest
from pathlib import Path
import test_accounts
from lokzeitleiste.localization import messages, source, text, resolve_placeholders
from lokzeitleiste.i18n import translate

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'backend/lokzeitleiste'


class ModuleMessagesTest(unittest.TestCase):
    def test_complete_module_keys_and_reproducible_outputs(self):
        spec = importlib.util.spec_from_file_location('build_translations', ROOT/'tools/build-translations.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        for path, content in builder.compile_messages().items():
            self.assertEqual(path.read_text(), content, str(path))
        manifest = json.loads((BASE/'locales/manifest.json').read_text())
        self.assertGreater(len(manifest), 100)
        for module, paths in manifest.items():
            self.assertEqual(set(paths), {'de', 'pl', 'en'})
        for file in (BASE/'static').glob('*'):
            if file.suffix not in ('.html', '.js') or file.name in ('messages.js', 'i18n.js'):
                continue
            for key in re.findall(r'(?:\{\{|CtlText.source\(["\'])([a-z][a-z0-9_]*\.text_[a-f0-9]{12})', file.read_text()):
                for locale in ('de', 'pl', 'en'):
                    self.assertIn(key, messages()[locale], str(file))
            if file.suffix == '.html':
                self.assertLess(file.read_text().index('/locales/messages.js'), file.read_text().index('/auth-session.js'))

    def test_keyed_text_and_canonical_contracts(self):
        de = messages()['de']
        key = next(k for k, v in de.items() if v == 'Speichern')
        self.assertEqual(source(key), 'Speichern')
        self.assertEqual(text(key, 'pl'), 'Zapisz')
        self.assertEqual(text(key, 'en'), 'Save')
        self.assertEqual(resolve_placeholders('{{'+key+'}}', 'en'), 'Save')
        for message in ('Notiz gespeichert.', 'Standzeit löschen', 'Nachtmodus einschalten'):
            self.assertNotEqual(translate(message, 'pl'), message)
            self.assertNotEqual(translate(message, 'en'), message)
        for locale in ('de', 'pl', 'en'):
            for key, value in messages()[locale].items():
                self.assertEqual(re.findall(r'%[sd]', value), re.findall(r'%[sd]', de[key]), key)


class ModuleAssetTest(unittest.TestCase):
    setUp = test_accounts.AccountsTest.setUp
    tearDown = test_accounts.AccountsTest.tearDown

    def test_public_assets_and_localized_html(self):
        manifest = self.client.get('/locales/manifest.json').json()
        module = 'portal_tf_help_content'
        for locale in ('de', 'pl', 'en'):
            response = self.client.get(manifest[module][locale])
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json())
        bundle = self.client.get('/locales/messages.js')
        self.assertEqual(bundle.status_code, 200)
        self.assertIn('CtlMessages', bundle.text)
        for path in ('/locales/missing/de.json', '/locales/portal_tf_help_content/ru.json'):
            self.assertEqual(self.client.get(path).status_code, 404)
        for path in ('/tf', '/admin/start', '/account'):
            page = self.client.get(path, headers={'Accept-Language':'pl'})
            self.assertEqual(page.status_code, 200)
            self.assertNotRegex(page.text, r'\{\{[a-z_]+\.text_')
            self.assertIn('/locales/messages.js', page.text)
