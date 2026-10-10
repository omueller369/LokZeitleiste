import json
import unittest
from urllib.parse import urlsplit,parse_qs
from unittest.mock import patch,MagicMock
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session
from lokzeitleiste.models import MailboxSettings,MailboxAccount,MailboxOAuthState
from lokzeitleiste.mailbox import google,oauth,service
import test_accounts


class GoogleMailTest(unittest.TestCase):
    setUp=test_accounts.AccountsTest.setUp
    tearDown=test_accounts.AccountsTest.tearDown
    active_staff=test_accounts.AccountsTest.active_staff
    create_staff=test_accounts.AccountsTest.create_staff
    payload=test_accounts.AccountsTest.payload
    staff_login=test_accounts.AccountsTest.staff_login
    change=test_accounts.AccountsTest.change

    def env(self):return patch.dict('os.environ',{'MAILBOX_ENCRYPTION_KEY':Fernet.generate_key().decode(),'MAILBOX_GOOGLE_CLIENT_ID':'mock.apps.googleusercontent.com','MAILBOX_GOOGLE_CLIENT_SECRET':'mock-google-app-secret'})

    def start(self):
        self.client.headers['Origin']='http://localhost'
        response=self.client.post(f'/api/v1/admin/email/{self.tf}/google/start')
        self.assertEqual(response.status_code,200,response.text)
        params=parse_qs(urlsplit(response.json()['url']).query)
        self.assertEqual(params['code_challenge_method'],['S256']);self.assertEqual(params['scope'],[google.SCOPE]);self.assertNotIn('mock-google-app-secret',response.text)
        cookie=response.cookies[google.COOKIE]
        return params['state'][0],cookie

    def callback(self,state,cookie):
        return self.client.get(google.CALLBACK+'?state='+state+'&code=mock-code',headers={'Cookie':google.COOKIE+'='+cookie},follow_redirects=False)

    def test_google_api_link_refresh_and_no_secret_exposure(self):
        with self.env(),patch('lokzeitleiste.main.PUBLIC_ORIGIN','http://localhost'):
            state,cookie=self.start()
            result={'access_token':'mock-google-access','refresh_token':'mock-google-refresh','expires_in':3600,'scope':google.SCOPE}
            with patch.object(google,'request_json',side_effect=[result,{'emailAddress':'linked@gmail.com'}]) as remote:
                response=self.callback(state,cookie);self.assertEqual(response.status_code,303,response.text);self.assertIn('oauth_connected=1',response.headers['location'])
                self.assertEqual(remote.call_args_list[1].args[0],'https://gmail.googleapis.com/gmail/v1/users/me/profile')
            path=f'/api/v1/admin/email/{self.tf}/config';cfg=self.client.get(path).json()
            self.assertEqual(cfg['address'],'linked@gmail.com');self.assertEqual(cfg['servers']['auth_method'],'oauth2');self.assertTrue(cfg['oauth_connected']);self.assertNotIn('mock-google-access',json.dumps(cfg));self.assertNotIn('refresh_token',json.dumps(cfg))
            self.assertEqual(self.callback(state,cookie).status_code,409)
            with Session(self.engine) as db:
                account=db.get(MailboxAccount,self.tf);row=db.get(MailboxSettings,self.tf);account._settings=row;account._db=db
                self.assertNotIn('mock-google-refresh',row.tokens_encrypted)
                token=oauth.unseal(row.tokens_encrypted);token['expires_at']=0;row.tokens_encrypted=oauth.seal(token);db.commit()
                with patch.object(google,'request_json',return_value={'access_token':'mock-refreshed','expires_in':3600}):
                    self.assertEqual(google.access_token(account),'mock-refreshed');self.assertEqual(oauth.unseal(row.tokens_encrypted)['refresh_token'],'mock-google-refresh')
                imap=MagicMock()
                with patch.object(service.imaplib,'IMAP4_SSL',return_value=imap):
                    with service.connection(account):pass
                    imap.login.assert_not_called();self.assertIn(b'auth=Bearer mock-refreshed',imap.authenticate.call_args.args[1](b''))

    def test_callback_state_browser_session_and_rights_protection(self):
        _,reader=self.active_staff({'email':1},'google-reader')
        reader.headers['Origin']='http://localhost'
        with self.env(),patch('lokzeitleiste.main.PUBLIC_ORIGIN','http://localhost'):
            self.assertEqual(reader.post(f'/api/v1/admin/email/{self.tf}/google/start').status_code,403)
            state,cookie=self.start()
            self.assertEqual(self.callback(state,'wrong-cookie').status_code,403)
            with patch.object(google,'request_json') as remote:
                self.assertEqual(self.callback('unknown-state',cookie).status_code,409);remote.assert_not_called()
            self.client.post('/api/v1/admin/logout')
            self.assertEqual(self.callback(state,cookie).status_code,401)


if __name__=='__main__':unittest.main()
