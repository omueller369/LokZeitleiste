import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
import test_accounts
import test_work_reports
from lokzeitleiste.main import app
from lokzeitleiste.models import DocumentFile,User,ReportDispatch
from lokzeitleiste.documents.storage import MAX_FILE
from lokzeitleiste.documents.archive import backfill_documents
from lokzeitleiste.reports.service import process_dispatch


class DocumentsTest(unittest.TestCase):
    setUp=test_work_reports.WorkReportsTest.setUp
    tearDown=test_work_reports.WorkReportsTest.tearDown
    payload=test_work_reports.WorkReportsTest.payload
    create=test_work_reports.WorkReportsTest.create
    create_staff=test_accounts.AccountsTest.create_staff
    staff_login=test_accounts.AccountsTest.staff_login
    change=test_accounts.AccountsTest.change
    active_staff=test_accounts.AccountsTest.active_staff

    def listing(self,client=None,**params):
        result=(client or self.driver).get('/api/v1/documents/tree',params=params)
        self.assertEqual(result.status_code,200,result.text);return result.json()

    def test_tree_upload_download_search_and_own_delete(self):
        data=self.listing();folders=data['folders']
        for path in ['Dokumente/Fahrpläne/Trassen','Dokumente/Fahrpläne/FPLO','Dokumente/Fahrpläne/Sonstiges']:
            self.assertIn(path,folders)
        response=self.driver.post('/api/v1/documents/upload',data={'folder':'Dokumente/Fahrpläne/FPLO'},files={'file':('Test ä.txt',b'example')})
        self.assertEqual(response.status_code,201,response.text);path=response.json()['path']
        rows=self.listing(q='ä.txt')['files'];self.assertEqual(len(rows),1);self.assertTrue(rows[0]['can_delete'])
        download=self.driver.get('/api/v1/documents/download',params={'path':path});self.assertEqual(download.content,b'example');self.assertEqual(download.headers['x-content-type-options'],'nosniff');self.assertIn('attachment',download.headers['content-disposition'])
        self.assertEqual(self.driver.delete('/api/v1/documents/file',params={'path':path}).status_code,200)
        self.assertEqual(self.listing()['files'],[])

    def test_size_traversal_symlinks_and_account_isolation(self):
        for size,status in [(MAX_FILE,201),(MAX_FILE+1,413),(0,413)]:
            response=self.driver.post('/api/v1/documents/upload',data={'folder':'Dokumente'},files={'file':('limit.txt',b'x'*size)})
            self.assertEqual(response.status_code,status,response.text[:300])
        oversized=self.driver.post('/api/v1/documents/upload',content=b'x'*(MAX_FILE+65537),headers={'Content-Type':'application/octet-stream'})
        self.assertEqual(oversized.status_code,413)
        for path in ('../VW/admin','Dokumente/../../outside','/etc/passwd','Dokumente\\bad','Dokumente//bad'):
            self.assertIn(self.driver.get('/api/v1/documents/download',params={'path':path}).status_code,(404,409,422))
        root=Path(self.documents.name)/'TF'/'787100'/'Dokumente';(root/'link.txt').symlink_to(Path(self.documents.name)/'outside')
        self.assertEqual(self.driver.post('/api/v1/documents/upload',data={'folder':'Dokumente/link.txt'},files={'file':('x',b'x')}).status_code,409)
        self.assertEqual(self.driver.get('/api/v1/documents/download',params={'path':'Dokumente/link.txt'}).status_code,409)
        self.assertNotIn('Dokumente/link.txt',[f['path'] for f in self.listing()['files']])
        self.create_tf('787200','P-SECOND')
        other=TestClient(app,base_url='https://testserver');self.staff_clients.append(other)
        other.post('/api/v1/account/login',json={'username':'787200','password':'tf-secret-12345'})
        self.assertEqual(self.listing(other)['files'],[])
        self.assertEqual(other.get('/api/v1/documents/download',params={'path':'Dokumente/limit.txt'}).status_code,404)
        self.assertEqual(other.delete('/api/v1/documents/file',params={'path':'Dokumente/limit.txt'}).status_code,403)

    def test_staff_without_module_grants_and_initial_password_gate(self):
        # This class uses report payload(); use the staff fixture payload explicitly.
        result=self.client.post('/api/v1/admin/staff',json=test_accounts.AccountsTest.payload(self,'docs-office'))
        self.assertEqual(result.status_code,201,result.text)
        staff,_=self.staff_login('docs-office')
        self.assertEqual(staff.get('/api/v1/documents/tree').status_code,403)
        self.change(staff);staff.post('/api/v1/account/login',json={'username':'docs-office','password':'personal-secret-67890'})
        self.assertEqual(self.listing(staff)['folders'],['Dokumente','Dokumente/Protokolle','Dokumente/Sonstiges'])

    def test_old_login_directory_is_not_reassigned_to_a_new_person(self):
        folder=Path(self.documents.name)/'TF'/'787333';folder.mkdir()
        (folder/'old.txt').write_text('old documents')
        response=self.create_tf('787333','P-OLD-DIRECTORY')
        self.assertEqual(response.status_code,409,response.text)
        self.assertEqual((folder/'old.txt').read_text(),'old documents')
        with Session(self.engine) as db:
            self.assertIsNone(db.scalar(select(User).where(User.username=='787333')))

    def test_archive_mail_bytes_month_pdfs_and_delete_protection(self):
        report=self.create();data=self.listing();files=data['files']
        self.assertTrue(any('/Arbeitsberichte/' in f['path'] for f in files))
        self.assertTrue(any(f['path'].endswith('/2026-10/Monatsbericht.pdf') for f in files))
        self.assertTrue(any(f['path'].endswith('/2026-10/Monatszusammenfassung.pdf') for f in files))
        file=next(f for f in files if f['path'].endswith(f'Arbeitsbericht-{report["id"]}.pdf'))
        self.assertFalse(file['can_delete']);self.assertTrue(file['generated'])
        self.assertEqual(self.driver.delete('/api/v1/documents/file',params={'path':file['path']}).status_code,403)
        with Session(self.engine) as db:
            dispatch=db.scalar(select(ReportDispatch));dispatch_id=dispatch.id;pdf=dispatch.pdf_data
        process_dispatch(dispatch_id)
        self.assertEqual(self.driver.get('/api/v1/documents/download',params={'path':file['path']}).content,pdf)
        with Session(self.engine) as db:
            self.assertEqual(db.get(ReportDispatch,dispatch_id).status,'sent')
            before=len(db.scalars(select(DocumentFile)).all());backfill_documents(db);db.commit()
            self.assertEqual(len(db.scalars(select(DocumentFile)).all()),before)


class LinuxProvisioningTest(unittest.TestCase):
    def test_commands_are_locked_accounts_and_acl_scoped(self):
        spec=importlib.util.spec_from_file_location('provision',Path(__file__).resolve().parents[2]/'setup'/'provision-users.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        import tempfile
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);userdir=root/'TF'/'787123';userdir.mkdir(parents=True);(userdir/'file.pdf').write_bytes(b'data')
            with patch.object(module.pwd,'getpwnam',side_effect=KeyError),patch.object(module.pwd,'getpwuid',side_effect=KeyError),patch.object(module,'run') as run,patch.object(module.os,'chown'):
                module.provision(root,dict(id=42,username='787123',category='TF'))
                commands=[call.args[0] for call in run.call_args_list]
                account=next(c for c in commands if c[0]=='useradd')
                self.assertIn('/usr/sbin/nologin',account);self.assertIn('--no-create-home',account);self.assertIn('!',account)
                self.assertTrue(any(c[0]=='setfacl' and 'u:10001:rwx' in c[2] for c in commands))
                with self.assertRaises(ValueError):module.provision(root,dict(id=42,username='../escape',category='TF'))
            bad=SimpleNamespace(pw_uid=200042,pw_gecos='Other account',pw_dir=str(userdir),pw_shell='/bin/bash')
            with patch.object(module.pwd,'getpwnam',return_value=bad),patch.object(module,'run') as run:
                with self.assertRaises(RuntimeError):module.provision(root,dict(id=42,username='787123',category='TF'))
                run.assert_not_called()
            foreign=SimpleNamespace(pw_name='foreign',pw_uid=10001,pw_gecos='not managed')
            with patch.object(module.pwd,'getpwuid',return_value=foreign),patch.object(module,'run') as run:
                with self.assertRaises(RuntimeError):module.ensure_api_account()
                run.assert_not_called()
