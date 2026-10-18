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
from lokzeitleiste.models import DocumentFile,User,ReportDispatch,DocumentRenderState
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
        self.assertTrue(any(f['path'].endswith('/2026/10/Monatsbericht.pdf') for f in files))
        self.assertTrue(any(f['path'].endswith('/2026/10/Monatszusammenfassung.pdf') for f in files))
        file=next(f for f in files if f['path'].endswith(f'2026-10-12-1-{report["id"]}-Arbeitsbericht.pdf'))
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

    def test_legacy_archives_migrate_by_duty_date_without_changing_bytes(self):
        self.create()
        root=Path(self.documents.name)/'TF'/'787100'
        originals={}
        with Session(self.engine) as db:
            for row in db.scalars(select(DocumentFile)):
                new=root/row.relative_path
                folder='Dokumente/Arbeitsberichte/2026-10-18' if row.source_key.startswith('work-report:') else 'Dokumente/Monatsabrechnung/2026-10'
                old=root/folder/row.display_name;old.parent.mkdir(parents=True,exist_ok=True)
                new.rename(old);row.relative_path=old.relative_to(root).as_posix()
                originals[row.source_key]=(old,old.read_bytes())
            db.commit()
            # First run rolls back: old originals must survive.
            backfill_documents(db);db.rollback()
            for old,content in originals.values():self.assertEqual(old.read_bytes(),content)
            backfill_documents(db);db.commit()
            paths=[]
            for row in db.scalars(select(DocumentFile)):
                old,content=originals[row.source_key];new=root/row.relative_path
                self.assertFalse(old.exists());self.assertEqual(new.read_bytes(),content)
                if row.source_key.startswith('work-report:'):self.assertIn('/2026/10/12/',row.relative_path)
                else:self.assertIn('/2026/10/',row.relative_path)
                paths.append(row.relative_path)
            backfill_documents(db);db.commit()
            self.assertEqual(sorted(paths),sorted(row.relative_path for row in db.scalars(select(DocumentFile))))

    def test_migration_preserves_target_collision_and_relocates_after_duty_edit(self):
        report=self.create();root=Path(self.documents.name)/'TF'/'787100'
        with Session(self.engine) as db:
            row=db.scalar(select(DocumentFile).where(DocumentFile.source_key==f'work-report:{report["id"]}'))
            original=root/row.relative_path;content=original.read_bytes()
            legacy=root/'Dokumente/Arbeitsberichte/2026-10-18'/original.name
            legacy.parent.mkdir(parents=True,exist_ok=True);original.rename(legacy)
            row.relative_path=legacy.relative_to(root).as_posix();db.commit()
            original.write_bytes(b'manually uploaded document')
            backfill_documents(db);db.commit()
            self.assertEqual(original.read_bytes(),b'manually uploaded document')
            self.assertEqual((root/row.relative_path).read_bytes(),content)
            self.assertIn('-system-',row.relative_path)
            before=row.relative_path;backfill_documents(db);db.commit();self.assertEqual(row.relative_path,before)
        from lokzeitleiste.documents.storage import generated
        with Session(self.engine) as db:
            user=db.scalar(select(User).where(User.username=='787100'))
            row=generated(db,user,f'Dokumente/Arbeitsberichte/2026/09/30/Arbeitsbericht-{report["id"]}.pdf',b'updated report',f'work-report:{report["id"]}')
            db.commit()
            self.assertIn('/2026/09/30/',row.relative_path)
            self.assertTrue((root/row.relative_path).is_file())
            self.assertFalse((root/before).exists())


    def test_overnight_duty_uses_start_day_and_both_billing_months(self):
        payload=self.payload('2026-10-31T21:00','2026-11-01T09:00');payload['actual_pause']=120
        report=self.create(payload)
        paths=[file['path'] for file in self.listing()['files']]
        self.assertIn(f'Dokumente/Arbeitsberichte/2026/10/31/2026-10-31-1-{report["id"]}-Arbeitsbericht.pdf',paths)
        for month in ('10','11'):
            for name in ('Monatsbericht','Monatszusammenfassung'):
                self.assertIn(f'Dokumente/Monatsabrechnung/2026/{month}/{name}.pdf',paths)

    def test_old_month_receipt_uses_billing_month_not_dispatch_creation(self):
        from lokzeitleiste.documents.archive import archive_dispatch
        self.create();root=Path(self.documents.name)/'TF'/'787100'
        with Session(self.engine) as db:
            original=db.scalar(select(ReportDispatch))
            dispatch=ReportDispatch(tf_user_id=original.tf_user_id,work_month_id=original.work_month_id,
                recipient_email=original.recipient_email,filename='Monat.pdf',pdf_data=b'monthly receipt',status='sent')
            db.add(dispatch);db.flush()
            old=root/f'Dokumente/Arbeitsberichte/2026-12-24/Eingang-{dispatch.id}.pdf'
            old.parent.mkdir(parents=True,exist_ok=True);old.write_bytes(dispatch.pdf_data)
            row=DocumentFile(owner_id=dispatch.tf_user_id,source_key=f'dispatch:{dispatch.id}',relative_path=old.relative_to(root).as_posix(),display_name=old.name,byte_size=len(dispatch.pdf_data),sha256='')
            db.add(row);db.commit();backfill_documents(db);db.commit()
            self.assertFalse(old.exists());self.assertEqual(row.relative_path,f'Dokumente/Monatsabrechnung/2026/10/Eingang-{dispatch.id}.pdf')
            self.assertEqual((root/row.relative_path).read_bytes(),b'monthly receipt')


    def test_upgrade_regenerates_archives_once_without_sending_old_reports(self):
        report=self.create();root=Path(self.documents.name)/'TF'/'787100'
        with Session(self.engine) as db:
            rows=db.scalars(select(DocumentFile)).all()
            for row in rows:
                state=db.get(DocumentRenderState,row.id)
                if row.source_key.startswith('month-report:'):db.delete(state)
                else:state.format_version=2
                if row.source_key.startswith('work-report:'):
                    old=root/row.relative_path;new=old.with_name(f'Arbeitsbericht-{report["id"]}.pdf');old.rename(new)
                    row.relative_path=new.relative_to(root).as_posix();row.display_name=new.name
                (root/row.relative_path).write_bytes(b'legacy PDF layout')
            dispatch=db.scalar(select(ReportDispatch));dispatch.filename=f'Arbeitsbericht-{report["id"]}.pdf'
            dispatch_bytes=dispatch.pdf_data;count=len(db.scalars(select(ReportDispatch)).all());db.commit()
            backfill_documents(db);db.rollback()
            self.assertTrue((root/rows[0].relative_path).exists())
            backfill_documents(db);db.commit()
            hashes={}
            for row in db.scalars(select(DocumentFile)):
                self.assertTrue((root/row.relative_path).read_bytes().startswith(b'%PDF'))
                self.assertEqual(db.get(DocumentRenderState,row.id).format_version,3)
                hashes[row.id]=row.sha256
            daily=db.scalar(select(DocumentFile).where(DocumentFile.source_key==f'work-report:{report["id"]}'))
            self.assertEqual(daily.display_name,f'2026-10-12-1-{report["id"]}-Arbeitsbericht.pdf')
            daily_bytes=(root/daily.relative_path).read_bytes()
            self.assertEqual(len(db.scalars(select(ReportDispatch)).all()),count)
            self.assertEqual(dispatch.pdf_data,dispatch_bytes)
            backfill_documents(db);db.commit()
            self.assertEqual(hashes,{row.id:row.sha256 for row in db.scalars(select(DocumentFile))})
            dispatch_id=dispatch.id;daily_path=daily.relative_path
        process_dispatch(dispatch_id)
        self.assertEqual((root/daily_path).read_bytes(),daily_bytes)

    def test_filename_version_increases_after_train_edit(self):
        report=self.create();train=dict(id=str(uuid4()),train_number='TEST12',start_station='BHF',end_station='LL',start_at='2026-10-12T09:00',end_at='2026-10-12T10:00',events=[])
        result=self.driver.put(f'/api/v1/tf/work-reports/{report["id"]}/train-journeys',json={'expected_revision':0,'train_journeys':[train]})
        self.assertEqual(result.status_code,200,result.text)
        files=self.listing()['files'];daily=next(f for f in files if f['path'].endswith('-Arbeitsbericht.pdf'))
        self.assertEqual(daily['name'],f'2026-10-12-2-{report["id"]}-Arbeitsbericht.pdf')
        self.assertEqual(sum(f['path'].endswith('-Arbeitsbericht.pdf') for f in files),1)


    def test_pdf_times_only_label_date_changes_in_overnight_duties(self):
        from lokzeitleiste.documents.archive import report_time
        start='2026-10-12T21:00';end='2026-10-13T09:00'
        self.assertEqual(report_time(start,start,end),'21:00')
        self.assertEqual(report_time(end,start,end,start),'13.10.2026 09:00')
        self.assertEqual(report_time('2026-10-13T00:05',start,end,'2026-10-12T23:55'),'13.10.2026 00:05')
        self.assertEqual(report_time('2026-10-13T00:10',start,end,'2026-10-13T00:05'),'00:10')
        self.assertEqual(report_time('2026-10-12T09:00','2026-10-12T09:00','2026-10-12T17:00'),'09:00')



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
