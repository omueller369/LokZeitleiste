import os
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

import test_accounts
from lokzeitleiste.models import User
from lokzeitleiste.user_directories import directory_transaction, sync_user_directories, user_path


class UserDirectoryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        env = patch.dict(os.environ, {'LOKZEITLEISTE_FILES_ROOT': self.temp.name})
        env.start(); self.addCleanup(env.stop)

    def test_private_role_directories_and_existing_content(self):
        for role, category, login in [('tf','TF','787123'),('staff','VW','office.one'),('admin','VW','admin')]:
            user = SimpleNamespace(role=role, username=login)
            with directory_transaction(user) as path:
                self.assertEqual(path, self.root/category/login)
                (path/'beleg.pdf').write_bytes(b'example')
            with directory_transaction(user) as path:
                self.assertEqual((path/'beleg.pdf').read_bytes(), b'example')
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
                self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)

    def test_rename_preserves_documents_and_rolls_back_on_commit_error(self):
        user = SimpleNamespace(role='tf', username='787123')
        with directory_transaction(user) as old:
            (old/'beleg.pdf').write_bytes(b'example')
        user.username = '787124'
        with self.assertRaisesRegex(RuntimeError,'DB commit failed'):
            with directory_transaction(user,'787123') as new:
                self.assertEqual((new/'beleg.pdf').read_bytes(),b'example')
                raise RuntimeError('DB commit failed')
        self.assertTrue(old.exists());self.assertFalse((old.parent/'787124').exists())
        with directory_transaction(user,'787123') as new:
            self.assertEqual((new/'beleg.pdf').read_bytes(),b'example')
        self.assertFalse(old.exists())
        with self.assertRaises(RuntimeError):
            with directory_transaction(SimpleNamespace(role='tf',username='787125')):
                raise RuntimeError('DB failed')
        self.assertFalse((new.parent/'787125').exists())

    def test_no_path_escape_symlinks_or_merging(self):
        for login in ('..','../outside','a/b','/tmp/escape','Auser'):
            with self.assertRaises(HTTPException):
                with directory_transaction(SimpleNamespace(role='tf',username=login)):pass
        outside=self.root/'outside';outside.mkdir()
        (self.root/'TF'/'787123').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(HTTPException):
            with directory_transaction(SimpleNamespace(role='tf',username='787123')):pass
        self.assertEqual(list(outside.iterdir()),[])
        for login in ('787124','787125'):
            with directory_transaction(SimpleNamespace(role='tf',username=login)):pass
        with self.assertRaises(HTTPException):
            with directory_transaction(SimpleNamespace(role='tf',username='787125'),'787124'):pass
        self.assertTrue((self.root/'TF'/'787124').exists())


class UserDirectoryApiTest(unittest.TestCase):
    setUp = test_accounts.AccountsTest.setUp
    tearDown = test_accounts.AccountsTest.tearDown
    payload = test_accounts.AccountsTest.payload
    create_staff = test_accounts.AccountsTest.create_staff

    def test_create_existing_backfill_and_tf_number_change(self):
        root=Path(self.documents.name)
        self.assertTrue((root/'TF'/'787100').is_dir())
        self.create_staff(username='office-one')
        self.assertTrue((root/'VW'/'office-one').is_dir())
        with Session(self.engine) as db:
            count=sync_user_directories(db)
            self.assertEqual(count,len(db.scalars(select(User)).all()))
        self.assertTrue((root/'VW'/'admin').is_dir())
        old=root/'TF'/'787100';(old/'beleg.txt').write_text('keep')
        profile=self.client.get('/api/v1/admin/tf').json()[0]
        profile['username']='787101'
        result=self.client.put(f'/api/v1/admin/tf/{self.tf}',json=profile)
        self.assertEqual(result.status_code,200,result.text)
        self.assertFalse(old.exists())
        self.assertEqual((root/'TF'/'787101'/'beleg.txt').read_text(),'keep')

    def test_directory_error_does_not_create_staff_account(self):
        root=Path(self.documents.name);(root/'VW').mkdir()
        (root/'VW'/'office-one').write_text('occupied')
        response=self.client.post('/api/v1/admin/staff',json=self.payload())
        self.assertEqual(response.status_code,503,response.text)
        with Session(self.engine) as db:
            self.assertIsNone(db.scalar(select(User).where(User.username=='office-one')))
