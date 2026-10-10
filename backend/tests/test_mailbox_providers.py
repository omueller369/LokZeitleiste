import json
import time
import unittest
from datetime import timedelta
from unittest.mock import patch, MagicMock
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session
from lokzeitleiste.models import MailboxAccount, MailboxSettings, MailboxAuthorization, now_utc
from lokzeitleiste.mailbox import service, oauth
from lokzeitleiste.mailbox.providers import PROVIDERS
from lokzeitleiste.mailbox.api import MessageInput
import test_mailbox


class ProviderTest(test_mailbox.MailboxTest):
    def payload_config(self,provider='google'):
        return dict(address='tf@example.com',username='tf@example.com',password='mock-app-password',servers=dict(PROVIDERS[provider],provider=provider,smtp_username=''))

    def test_provider_save_update_secret_reentry_and_connections(self):
        path=f'/api/v1/admin/email/{self.tf}'
        with patch.dict('os.environ',{'MAILBOX_ENCRYPTION_KEY':Fernet.generate_key().decode()}):
            for provider in PROVIDERS:
                payload=self.payload_config(provider)
                if provider=='manual':payload['servers'].update(imap_host='imap.manual.example',smtp_host='smtp.manual.example')
                response=self.client.put(path+'/config',json=payload);self.assertEqual(response.status_code,200,response.text)
                cfg=self.client.get(path+'/config').json();self.assertEqual(cfg['servers']['provider'],provider)
                self.assertNotIn('mock-app-password',json.dumps(cfg));self.assertNotIn('tokens_encrypted',cfg)
            payload=self.payload_config('apple');self.client.put(path+'/config',json=payload)
            payload.pop('password');self.assertEqual(self.client.put(path+'/config',json=payload).status_code,200)
            payload['servers']['smtp_host']='smtp.other.example'
            self.assertEqual(self.client.put(path+'/config',json=payload).status_code,422)
            payload['password']='mock-new-password';payload['servers']['imap_security']='starttls';payload['servers']['imap_port']=143
            self.assertEqual(self.client.put(path+'/config',json=payload).status_code,200)
            with Session(self.engine) as db:
                account=db.get(MailboxAccount,self.tf);account._settings=db.get(MailboxSettings,self.tf);account._db=db
                imap=MagicMock()
                with patch.object(service.imaplib,'IMAP4',return_value=imap) as constructor:
                    with service.connection(account):pass
                    self.assertEqual(constructor.call_args.args[:2],('imap.mail.me.com',143))
                    imap.starttls.assert_called_once();imap.login.assert_called_once_with('tf@example.com','mock-new-password')
            payload['servers']['smtp_host']='https://bad.example/path';self.assertEqual(self.client.put(path+'/config',json=payload).status_code,422)
            payload=self.payload_config('microsoft');payload['servers']['smtp_host']='evil.example';self.assertEqual(self.client.put(path+'/config',json=payload).status_code,422)

    def test_microsoft_device_flow_permissions_binding_refresh_and_xoauth(self):
        path=f'/api/v1/admin/email/{self.tf}'
        env={'MAILBOX_ENCRYPTION_KEY':Fernet.generate_key().decode(),'MAILBOX_MICROSOFT_CLIENT_ID':'00000000-0000-0000-0000-000000000001'}
        with patch.dict('os.environ',env):
            payload=self.payload_config('microsoft');payload.pop('password')
            self.assertEqual(self.client.put(path+'/config',json=payload).status_code,200)
            _,reader=self.active_staff({'email':1},'provider-reader')
            _,writer=self.active_staff({'email':2},'provider-writer')
            self.assertEqual(reader.post(path+'/microsoft/start').status_code,403)
            self.assertEqual(writer.post(path+'/microsoft/start').status_code,403)
            pending=dict(device_code='secret-device-code',user_code='MOCK-CODE',expires_in=900,interval=5)
            with patch.object(oauth,'request_token',return_value=pending):
                result=self.client.post(path+'/microsoft/start');self.assertEqual(result.status_code,200,result.text)
                self.assertNotIn('secret-device-code',result.text)
            with Session(self.engine) as db:
                row=db.get(MailboxAuthorization,(self.tf,1));self.assertNotIn('secret-device-code',row.device_encrypted)
                row.next_poll_at=now_utc()-timedelta(seconds=1);db.commit()
            with patch.object(oauth,'request_token',return_value={'error':'authorization_pending'}):
                self.assertTrue(self.client.post(path+'/microsoft/finish').json()['pending'])
            with Session(self.engine) as db:
                row=db.get(MailboxAuthorization,(self.tf,1));row.next_poll_at=now_utc()-timedelta(seconds=1);db.commit()
            with patch.object(oauth,'request_token',return_value=dict(access_token='mock-access',refresh_token='mock-refresh',expires_in=3600)):
                result=self.client.post(path+'/microsoft/finish');self.assertEqual(result.status_code,200,result.text);self.assertTrue(result.json()['connected'])
            self.assertNotIn('mock-access',self.client.get(path+'/config').text)
            self.assertEqual(self.client.post(path+'/microsoft/finish').status_code,409)
            with Session(self.engine) as db:
                row=db.get(MailboxSettings,self.tf);self.assertNotIn('mock-refresh',row.tokens_encrypted)
                token=oauth.unseal(row.tokens_encrypted);token['expires_at']=time.time()-1;row.tokens_encrypted=oauth.seal(token);db.commit()
                account=db.get(MailboxAccount,self.tf);account._settings=row;account._db=db
                with patch.object(oauth,'request_token',return_value=dict(access_token='mock-access-new',refresh_token='mock-refresh-new',expires_in=3600)):
                    self.assertEqual(oauth.access_token(account),'mock-access-new')
                    self.assertEqual(oauth.unseal(row.tokens_encrypted)['refresh_token'],'mock-refresh-new')
                imap=MagicMock()
                with patch.object(service.imaplib,'IMAP4_SSL',return_value=imap):
                    with service.connection(account):pass
                    imap.login.assert_not_called();self.assertEqual(imap.authenticate.call_args.args[0],'XOAUTH2')
                    self.assertIn(b'auth=Bearer mock-access-new',imap.authenticate.call_args.args[1](b''))
                smtp=MagicMock();smtp.__enter__.return_value=smtp;smtp.send_message.return_value={};imap.__enter__.return_value=imap;imap.append.return_value=('OK',[])
                with patch.object(service.smtplib,'SMTP',return_value=smtp) as factory,patch.object(service,'connection',return_value=imap):
                    result=service.send(account,MessageInput(to=['recipient@example.com'],subject='Mock OAuth send',body='Mock'))
                    self.assertTrue(result['sent']);self.assertEqual(factory.call_args.args[:2],('smtp-mail.outlook.com',587))
                    smtp.starttls.assert_called_once();smtp.login.assert_not_called();self.assertEqual(smtp.auth.call_args.args[0],'XOAUTH2')
                    self.assertIn('mock-access-new',smtp.auth.call_args.args[1]())
            payload['username']='changed@example.com';self.client.put(path+'/config',json=payload)
            self.assertFalse(self.client.get(path+'/config').json()['oauth_connected'])


if __name__=='__main__':unittest.main()
