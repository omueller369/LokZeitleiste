import unittest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from lokzeitleiste.main import app
from lokzeitleiste.models import TfNote
import test_tf_portal


class TfNotesTest(unittest.TestCase):
    setUp = test_tf_portal.TfPortalTest.setUp
    tearDown = test_tf_portal.TfPortalTest.tearDown

    def create(self, title='Mein Titel', text='Erste Zeile\nZweite Zeile'):
        result = self.driver.post('/api/v1/tf/notes', json=dict(title=title, text=text))
        self.assertEqual(result.status_code, 201, result.text)
        return result.json()

    def test_crud_persistence_order_and_unchanged_creation_date(self):
        first = self.create(title='  Erstellt  ')
        second = self.create(title='Zweite Notiz')
        listing = self.driver.get('/api/v1/tf/notes')
        self.assertEqual([row['id'] for row in listing.json()], [second['id'], first['id']])
        self.assertNotIn('text', listing.json()[0])
        self.assertIn('no-store', listing.headers['cache-control'])
        self.assertEqual(first['title'], 'Erstellt')
        self.assertTrue(first['created_at'].endswith('Z'))
        path = '/api/v1/tf/notes/'+str(first['id'])
        self.assertEqual(self.driver.get(path).json()['text'], 'Erste Zeile\nZweite Zeile')
        changed = self.driver.put(path, json=dict(title='Geändert', text='<script>alert(1)</script>\nText', expected_revision=1))
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual(changed.json()['created_at'], first['created_at'])
        self.assertEqual(changed.json()['revision'], 2)
        with Session(self.engine) as db:
            self.assertEqual(db.get(TfNote,first['id']).title, 'Geändert')
        self.assertEqual(self.driver.delete(path+'?expected_revision=2').status_code, 200)
        self.assertEqual(self.driver.get(path).status_code, 404)
        self.assertEqual(len(self.driver.get('/api/v1/tf/notes').json()), 1)

    def test_private_to_owner_and_not_available_to_staff_or_logged_out(self):
        note = self.create()
        path = '/api/v1/tf/notes/'+str(note['id'])
        self.create_tf('787111', 'NOTE-OTHER')
        other = TestClient(app, base_url='https://testserver')
        self.staff_clients.append(other)
        other.post('/api/v1/account/login', json={'username':'787111','password':'tf-secret-12345'})
        self.assertEqual(other.get('/api/v1/tf/notes').json(), [])
        for result in [other.get(path), other.put(path,json=dict(title='Fremd',text='X',expected_revision=1)),
                       other.delete(path+'?expected_revision=1')]:
            self.assertEqual(result.status_code,404,result.text)
        self.assertEqual(self.client.get('/api/v1/tf/notes').status_code,403)
        self.assertEqual(self.client.post('/api/v1/tf/notes',json=dict(title='X',text='X')).status_code,403)
        self.driver.cookies.clear()
        self.assertEqual(self.driver.get('/api/v1/tf/notes').status_code,401)

    def test_validation_unicode_and_no_owner_injection(self):
        note = self.create(text='😀'*1000)
        self.assertEqual(len(note['text']),1000)
        for values in [dict(title='',text='Text'),dict(title='   ',text='Text'),dict(title='X'*121,text='Text'),
                       dict(title='X',text=''),dict(title='X',text='  \n'),dict(title='X',text='😀'*1001),
                       dict(title='X',text='Text',owner_id=self.tf)]:
            self.assertEqual(self.driver.post('/api/v1/tf/notes',json=values).status_code,422,values.get('title'))
        self.assertEqual(len(self.driver.get('/api/v1/tf/notes').json()),1)

    def test_stale_update_and_delete_do_not_lose_changes(self):
        note = self.create()
        path = '/api/v1/tf/notes/'+str(note['id'])
        values = dict(title='Aktueller Stand',text='Nicht verlieren',expected_revision=1)
        self.assertEqual(self.driver.put(path,json=values).status_code,200)
        values['text']='Veraltet'
        self.assertEqual(self.driver.put(path,json=values).status_code,409)
        self.assertEqual(self.driver.delete(path+'?expected_revision=1').status_code,409)
        self.assertEqual(self.driver.get(path).json()['text'],'Nicht verlieren')
        self.assertEqual(self.driver.delete(path).status_code,422)

    def test_page_and_static_script(self):
        response = self.driver.get('/tf/notizen')
        self.assertEqual(response.status_code,200)
        self.assertIn('CtlText.source',self.driver.get('/tf/notes.js').text)
        self.assertIn('notesWorkspace',response.text)
        self.assertEqual(self.client.get('/tf/notizen',follow_redirects=False).status_code,303)
