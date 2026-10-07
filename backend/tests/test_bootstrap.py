import io
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from lokzeitleiste import bootstrap_admin
from lokzeitleiste.db import Base
from lokzeitleiste.models import User
from lokzeitleiste.security import hash_password, verify_password


class BootstrapAdminTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite://")
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()

    def run_bootstrap(self, password="example-secret-12345", username="test-admin"):
        with patch.object(bootstrap_admin, "engine", return_value=self.engine), \
             patch("sys.argv", ["bootstrap_admin", username]), \
             patch("sys.stdin", io.StringIO(password)), \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            bootstrap_admin.main()
            self.assertNotIn(password, output.getvalue())

    def test_admin_password_is_hashed_and_repeat_keeps_credentials(self):
        self.run_bootstrap()
        with Session(self.engine) as db:
            original = db.scalar(select(User)).password_hash
            self.assertTrue(verify_password("example-secret-12345", original))
        self.run_bootstrap(password="other-secret-12345")
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(User)).password_hash, original)
            self.assertEqual(len(db.scalars(select(User)).all()), 1)

    def test_tf_username_is_not_promoted(self):
        with Session(self.engine) as db:
            db.add(User(username="test-admin", password_hash=hash_password("tf-secret-12345"), role="tf"))
            db.commit()
        with self.assertRaises(SystemExit):
            self.run_bootstrap()
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(User)).role, "tf")

    def test_invalid_credentials_do_not_create_users(self):
        for username, password in [("a", "valid-secret-12345"), ("admin", "short"),
                                   ("admin", "valid-secret-12345\nsecond-line")]:
            with self.subTest(username=username, password_length=len(password)):
                with self.assertRaises(SystemExit):
                    self.run_bootstrap(password=password, username=username)
        with Session(self.engine) as db:
            self.assertEqual(db.scalars(select(User)).all(), [])
