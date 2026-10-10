import email
import unittest
from unittest.mock import patch, MagicMock
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session
import test_accounts
from lokzeitleiste.models import MailboxAccount
from lokzeitleiste.mailbox import service
from lokzeitleiste.mailbox.api import MessageInput


class MailboxTest(unittest.TestCase):
    setUp=test_accounts.AccountsTest.setUp
    tearDown=test_accounts.AccountsTest.tearDown
    payload=test_accounts.AccountsTest.payload
    create_staff=test_accounts.AccountsTest.create_staff
    staff_login=test_accounts.AccountsTest.staff_login
    change=test_accounts.AccountsTest.change
    active_staff=test_accounts.AccountsTest.active_staff

    def configure(self):
        path=f'/api/v1/admin/email/{self.tf}'
        response=self.client.put(path+'/config',json={'address':'tf@example.com','username':'tf-mail','password':'mock-mail-password'})
        self.assertEqual(response.status_code,200,response.text);return path

    def fake(self):
        client=MagicMock()
        client.__enter__.return_value=client
        client.select.return_value=('OK',[b'1'])
        client.response.return_value=('UIDVALIDITY',[b'123'])
        return client

    def test_config_encryption_missing_key_and_access(self):
        path=f'/api/v1/admin/email/{self.tf}'
        with patch.dict('os.environ',{'MAILBOX_ENCRYPTION_KEY':''}):
            self.assertEqual(self.client.put(path+'/config',json={'address':'tf@example.com','username':'tf','password':'mock'}).status_code,409)
        with patch.dict('os.environ',{'MAILBOX_ENCRYPTION_KEY':Fernet.generate_key().decode()}):
            self.configure()
            with Session(self.engine) as db:
                value=db.get(MailboxAccount,self.tf)
                self.assertNotIn('mock-mail-password',value.password_encrypted)
                self.assertEqual(service.password(value),'mock-mail-password')
            self.assertNotIn('password',self.client.get(path+'/config').text)
            _,reader=self.active_staff({'email':1},'mail-reader')
            self.assertEqual(reader.get(path+'/config').status_code,200)
            self.assertEqual(reader.post(path+'/send',json={}).status_code,403)
            self.assertEqual(reader.put(path+'/config',json={}).status_code,403)
            _,writer=self.active_staff({'email':2},'mail-writer')
            self.assertEqual(writer.put(path+'/config',json={}).status_code,403)
            self.assertEqual(writer.put(path+'/draft',json={'to':'a@example.com','subject':'Draft','body':'Private draft'}).status_code,200)
            self.assertEqual(writer.get(path+'/draft').json()['body'],'Private draft')
            self.assertEqual(self.client.get(path+'/draft').json()['body'],'')

    def test_uid_validity_read_does_not_mark_seen_and_html_safe(self):
        with patch.dict('os.environ',{'MAILBOX_ENCRYPTION_KEY':Fernet.generate_key().decode()}):
            path=self.configure();client=self.fake()
            raw=b'From: Sender <s@example.com>\r\nTo: tf@example.com\r\nSubject: Test\r\nContent-Type: text/html; charset=utf-8\r\n\r\n<p>Hello</p><script>danger()</script><img src="remote">'
            client.uid.side_effect=[('OK',[b'1 (RFC822.SIZE 200)']),('OK',[(b'1 (BODY[]',raw),b')'])]
            with patch.object(service,'connection',return_value=client):
                self.assertEqual(self.client.get(path+'/messages/1?folder=INBOX&uidvalidity=999').status_code,409)
                response=self.client.get(path+'/messages/1?folder=INBOX&uidvalidity=123')
                self.assertEqual(response.status_code,200,response.text)
                self.assertIn('Hello',response.json()['body']);self.assertNotIn('danger()',response.json()['body']);self.assertNotIn('remote',response.json()['body'])
                self.assertTrue(any('BODY.PEEK[]' in str(call) for call in client.uid.call_args_list))
                self.assertFalse(any('store' in str(call) for call in client.uid.call_args_list))

    def test_send_and_sent_copy_mocked_no_real_delivery(self):
        with patch.dict('os.environ',{'MAILBOX_ENCRYPTION_KEY':Fernet.generate_key().decode(),'MAILBOX_SMTP_HOST':'mock.example','MAILBOX_SMTP_SECURITY':'ssl'}):
            path=self.configure();smtp=MagicMock();smtp.__enter__.return_value=smtp;smtp.send_message.return_value={}
            imap=self.fake();imap.append.return_value=('OK',[])
            with patch.object(service.smtplib,'SMTP_SSL',return_value=smtp),patch.object(service,'connection',return_value=imap):
                response=self.client.post(path+'/send',json={'to':['recipient@example.com'],'subject':'Reply','body':'Mock body','in_reply_to':'<old@example.com>','attachments':[{'name':'test.txt','content_base64':'aGVsbG8='}]})
                self.assertEqual(response.status_code,200,response.text)
                self.assertTrue(response.json()['sent'])
                msg=smtp.send_message.call_args.args[0]
                self.assertEqual(str(msg['From']),'tf@example.com');self.assertEqual(str(msg['In-Reply-To']),'<old@example.com>')
                self.assertEqual(list(msg.iter_attachments())[0].get_payload(decode=True),b'hello')
                self.assertTrue(imap.append.called)
                self.assertEqual(self.client.post(path+'/send',json={'to':['recipient@example.com'],'subject':'Bad\nBcc: leak@example.com','body':'x'}).status_code,422)
