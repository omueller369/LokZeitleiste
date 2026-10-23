import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import test_accounts
from lokzeitleiste.main import app
from lokzeitleiste.models import TfEmployment

class AndroidSessionTest(unittest.TestCase):
    setUp=test_accounts.AccountsTest.setUp
    tearDown=test_accounts.AccountsTest.tearDown
    def test_native_token_cookie_handoff_and_blocking(self):
        native=TestClient(app,base_url='https://testserver');self.staff_clients.append(native)
        result=native.post('/api/v1/tf/login',json={'username':'787100','password':'tf-secret-12345'})
        self.assertEqual(result.status_code,200,result.text)
        token=result.json()['access_token']
        web=TestClient(app,base_url='https://testserver');self.staff_clients.append(web)
        web.cookies.set('admin_session',token)
        self.assertEqual(web.get('/tf').status_code,200)
        self.assertEqual(web.get('/api/v1/tf/portal').json()['id'],self.tf)
        self.assertEqual(web.get('/api/v1/tf/portal/plan/2026/10').status_code,200)
        self.assertEqual(web.get('/api/v1/documents/tree').status_code,200)
        self.assertEqual(web.get('/api/v1/admin/tf').status_code,401)
        with Session(self.engine) as db:
            db.get(TfEmployment,self.tf).immediate_block=True;db.commit()
        self.assertEqual(web.get('/api/v1/tf/portal').status_code,401)
        self.assertEqual(native.get('/api/v1/account/me',headers={'Authorization':'Bearer '+token}).status_code,401)

    def test_cookie_mutations_still_require_configured_origin(self):
        web=TestClient(app,base_url='https://testserver');self.staff_clients.append(web)
        token=web.post('/api/v1/tf/login',json={'username':'787100','password':'tf-secret-12345'}).json()['access_token']
        web.cookies.set('admin_session',token)
        with patch('lokzeitleiste.main.PUBLIC_ORIGIN','https://testserver'):
            self.assertEqual(web.put('/api/v1/account/locale',json={'language':'en'}).status_code,403)
            self.assertEqual(web.put('/api/v1/account/locale',json={'language':'en'},headers={'Origin':'https://testserver'}).status_code,200)
