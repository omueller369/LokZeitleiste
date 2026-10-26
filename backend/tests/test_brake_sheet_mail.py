import io,unittest
from uuid import uuid4
from unittest.mock import patch
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from pypdf import PdfReader
import test_brake_sheets
from lokzeitleiste.models import User,MailboxAccount,EmployeeEmail,DocumentFile,BrakeSheetDispatch
from lokzeitleiste.user_directories import user_path

class BrakeSheetMailTest(unittest.TestCase):
    setUp=test_brake_sheets.BrakeSheetTest.setUp
    tearDown=test_brake_sheets.BrakeSheetTest.tearDown
    data=test_brake_sheets.BrakeSheetTest.data
    create=test_brake_sheets.BrakeSheetTest.create
    sheet=test_brake_sheets.BrakeSheetTest.sheet
    base='/api/v1/tf/brake-sheets'
    def prepare(self,mailbox=True):
        if mailbox:
            with Session(self.engine) as db:
                user=db.scalar(select(User).where(User.username=='admin'))
                db.add(MailboxAccount(tf_user_id=user.id,address='test.admin@ctl-software.io-goerlitz.eu',username='test.admin@ctl-software.io-goerlitz.eu',password_encrypted='encrypted'))
                address=db.get(EmployeeEmail,user.id)
                if address:address.address='test.admin@ctl-software.io-goerlitz.eu'
                else:db.add(EmployeeEmail(user_id=user.id,address='test.admin@ctl-software.io-goerlitz.eu',managed=True))
                db.commit()
        sheet=self.sheet(departure_date='2026-10-26',first_vehicle='918061850012',last_vehicle='918061850053',countries=[dict(country='DE',category='G'),dict(country='PL',category='P'),{},{}],wagon=dict(count=20,length=200,brake=700,weight=1000))
        id=str(uuid4());saved=self.driver.put(self.base+'/'+id,json={'expected_revision':0,'sheet':sheet});self.assertEqual(saved.status_code,200,saved.text)
        result=self.driver.post(self.base+'/'+id+'/mail',json={'expected_revision':1});self.assertEqual(result.status_code,200,result.text)
        return result.json()
    def payload(self,prepared):return {k:prepared[k] for k in ['to','cc','bcc','subject','body']}
    def test_prepare_archives_pdf_but_does_not_send_and_explicit_send_is_idempotent(self):
        with patch('lokzeitleiste.brake_sheet_mail.service.send_prepared',return_value={'sent':True,'warning':''}) as smtp:
            r=self.prepare();self.assertFalse(smtp.called);self.assertTrue(r['mail_ready'])
            self.assertEqual(r['to'],['dispo@ctl-software.io-goerlitz.eu']);self.assertEqual(r['cc'],['oliver.mueller@ctl.eu'])
            self.assertEqual(r['sender'],'test.admin@ctl-software.io-goerlitz.eu');self.assertEqual(r['bcc'],['omueller369@gmail.com']);self.assertEqual(r['filename'],'Bremszettel-00123-2026-10-26.PDF')
            self.assertEqual(r['document_path'],'Dokumente/Zugfahrten/2026/10/26/00123/'+r['filename'])
            with Session(self.engine) as db:
                user=db.scalar(select(User).where(User.username=='787100'));document=db.scalar(select(DocumentFile).where(DocumentFile.owner_id==user.id,DocumentFile.relative_path==r['document_path']))
                self.assertIsNotNone(document);self.assertIsNone(document.uploader_id);self.assertTrue((user_path(user.username,user.role)/r['document_path']).is_file());archived=(user_path(user.username,user.role)/r['document_path']).read_bytes()
            pdf=self.driver.get(r['pdf_url']);self.assertEqual(pdf.status_code,200);self.assertEqual(len(PdfReader(io.BytesIO(pdf.content)).pages),1);self.assertEqual(archived,pdf.content)
            self.assertTrue(self.driver.get(r['image_url']).content.startswith(b'\x89PNG'))
            endpoint='/api/v1/tf/brake-sheet-mail/'+r['id']+'/send';body=self.payload(r);body['body']='<script>Test</script>';body['sender']='spoof@example.com'
            sent=self.driver.post(endpoint,json=body);self.assertEqual(sent.status_code,200,sent.text);self.assertEqual(smtp.call_count,1)
            self.assertIn('omueller369@gmail.com',[str(a) for a in smtp.call_args.args[2].bcc]);msg=smtp.call_args.args[1];self.assertIsNone(msg['Bcc']);self.assertEqual(msg['From'],r['sender']);self.assertEqual(str(msg['Cc']),'oliver.mueller@ctl.eu')
            self.assertIn('cid:brake-sheet-preview',msg.get_body(preferencelist=('html',)).get_content());self.assertIn('&lt;script&gt;',msg.get_body(preferencelist=('html',)).get_content())
            attached=[p for p in msg.walk() if p.get_content_type()=='application/pdf'];self.assertEqual(len(attached),1);self.assertEqual(attached[0].get_filename(),r['filename']);self.assertEqual(attached[0].get_payload(decode=True),pdf.content)
            inline=[p for p in msg.walk() if p.get_content_type()=='image/png'];self.assertIn(inline[0]['Content-ID'][1:-1],msg.get_body(preferencelist=('html',)).get_content())
            self.assertEqual(self.driver.post(endpoint,json=body).status_code,200);self.assertEqual(smtp.call_count,1)
    def test_mail_failure_keeps_archive_and_blocks_ambiguous_retry(self):
        r=self.prepare();endpoint='/api/v1/tf/brake-sheet-mail/'+r['id']+'/send'
        with patch('lokzeitleiste.brake_sheet_mail.service.send_prepared',side_effect=HTTPException(502,'SMTP fehlgeschlagen')) as smtp:
            self.assertEqual(self.driver.post(endpoint,json=self.payload(r)).status_code,502)
            self.assertEqual(self.driver.post(endpoint,json=self.payload(r)).status_code,409);self.assertEqual(smtp.call_count,1)
        self.assertEqual(self.driver.get(r['pdf_url']).status_code,200)
        with Session(self.engine) as db:self.assertEqual(db.get(BrakeSheetDispatch,r['id']).status,'unknown')
    def test_private_attachments_unconfigured_mailbox_and_no_spoofing(self):
        with patch.dict('os.environ',{'SMTP_HOST':''}):
            r=self.prepare(mailbox=False);self.assertFalse(r['mail_ready']);self.assertEqual(self.client.get(r['pdf_url']).status_code,403)
            with patch('lokzeitleiste.brake_sheet_mail.service.send_prepared') as smtp:
                self.assertEqual(self.driver.post('/api/v1/tf/brake-sheet-mail/'+r['id']+'/send',json=self.payload(r)).status_code,409);self.assertFalse(smtp.called)
        with Session(self.engine) as db:db.get(BrakeSheetDispatch,r['id']).owner_id=999;db.commit()
        self.assertEqual(self.driver.get(r['pdf_url']).status_code,404);self.assertEqual(self.driver.get(r['image_url']).status_code,404)

    def test_configured_server_admin_mailbox_and_hidden_envelope_bcc(self):
        with patch.dict('os.environ',{'SMTP_HOST':'smtp.example.com','SMTP_FROM':'info@example.com','SMTP_SECURITY':'ssl'}):
            r=self.prepare(mailbox=False);self.assertTrue(r['mail_ready']);self.assertEqual(r['sender'],'info@example.com')
            payload=self.payload(r);payload['bcc']=[]
            with patch('lokzeitleiste.reports.mailer._send_message') as smtp:
                response=self.driver.post('/api/v1/tf/brake-sheet-mail/'+r['id']+'/send',json=payload)
                self.assertEqual(response.status_code,200,response.text);self.assertEqual(smtp.call_count,1)
                msg=smtp.call_args.args[0];self.assertEqual(msg['From'],'info@example.com');self.assertIsNone(msg['Bcc'])
                self.assertIn('omueller369@gmail.com',smtp.call_args.kwargs['recipients'])

    def test_system_transport_sets_one_from_header_and_blind_recipients(self):
        from email.message import EmailMessage
        from lokzeitleiste.reports.mailer import _send_message
        msg=EmailMessage();msg['From']='info@example.com';msg['To']='dispo@example.com';msg.set_content('Test')
        with patch.dict('os.environ',{'SMTP_HOST':'smtp.example.com','SMTP_FROM':'info@example.com','SMTP_SECURITY':'ssl'}),patch('lokzeitleiste.reports.mailer.smtplib.SMTP_SSL') as connection:
            smtp=connection.return_value.__enter__.return_value
            _send_message(msg,recipients=['dispo@example.com','omueller369@gmail.com'])
            self.assertEqual(len(msg.get_all('From')),1);self.assertIsNone(msg['Bcc'])
            self.assertEqual(smtp.send_message.call_args.kwargs['to_addrs'],['dispo@example.com','omueller369@gmail.com'])
    def test_archive_only_creates_no_dispatch_and_needs_no_mailbox(self):
        sheet=self.sheet(departure_date='2026-10-26',first_vehicle='918061850012',last_vehicle='918061850053',countries=[dict(country='DE',category='G'),dict(country='PL',category='P'),{},{}],wagon=dict(count=20,length=200,brake=700,weight=1000))
        path=self.base+'/'+str(uuid4());self.assertEqual(self.driver.put(path,json={'expected_revision':0,'sheet':sheet}).status_code,200)
        with patch.dict('os.environ',{'SMTP_HOST':''}),patch('lokzeitleiste.brake_sheet_mail.service.send_prepared') as smtp:
            r=self.driver.post(path+'/archive',json={'expected_revision':1});self.assertEqual(r.status_code,200,r.text);smtp.assert_not_called()
            self.assertEqual(self.driver.post(path+'/archive',json={'expected_revision':1}).json()['document_path'],r.json()['document_path'])
            pdf=self.driver.get(r.json()['download_url']);self.assertEqual(pdf.status_code,200);self.assertEqual(len(PdfReader(io.BytesIO(pdf.content)).pages),1)
        with Session(self.engine) as db:self.assertEqual(list(db.scalars(select(BrakeSheetDispatch))),[])
        self.assertEqual(self.driver.post(path+'/archive',json={'expected_revision':2}).status_code,409)
        self.assertEqual(self.client.post(path+'/archive',json={'expected_revision':1}).status_code,403)
