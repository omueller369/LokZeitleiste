import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from types import SimpleNamespace
from cryptography.fernet import Fernet

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('mailbox_provisioner',ROOT/'setup/mailbox_provisioner.py')
worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)


class MailboxProvisionerTest(unittest.TestCase):
    def test_provision_preserves_existing_accounts_and_never_uses_password_in_argv(self):
        domain='ctl-software.io-goerlitz.eu';key=Fernet.generate_key();secret='initial-secret-123'
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            def path(value):
                p=Path(value)
                return root/str(p).lstrip('/') if str(p).startswith(('/etc/','/var/')) else p
            config=path('/etc/ctlsoftware-test/environment.json');config.parent.mkdir(parents=True)
            config.write_text(json.dumps(dict(DATABASE_URL='mysql+pymysql://dbo_ctl:password@127.0.0.1/db_ctl',MAILBOX_ENCRYPTION_KEY=key.decode(),CTL_MAIL_DOMAIN=domain)))
            for filename,value in [('/etc/dovecot/ctl-users','info@'+domain+':preserved-hash\n'),('/etc/postfix/ctl-mailboxes','info@'+domain+' 1\n')]:
                target=path(filename);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(value)
            path('/etc/opendkim').mkdir(parents=True);path('/var/vmail').mkdir(parents=True)
            cursor=Mock();cursor.__enter__=Mock(return_value=cursor);cursor.__exit__=Mock(return_value=False)
            cursor.fetchall.side_effect=[[(4,'mira.muster@'+domain,Fernet(key).encrypt(secret.encode()).decode())],[(domain,)]]
            conn=Mock();conn.__enter__=Mock(return_value=conn);conn.__exit__=Mock(return_value=False);conn.cursor.return_value=cursor
            import builtins
            original_open=builtins.open
            def file_open(name,*args,**kwargs):return original_open(root/'lock' if str(name)=='/run/lock/ctl-mailboxes.lock' else name,*args,**kwargs)
            with patch.object(worker,'Path',side_effect=path),patch.object(worker.os,'geteuid',return_value=0),patch.object(worker.os,'chown'),patch.object(worker.pwd,'getpwnam',return_value=SimpleNamespace(pw_uid=123,pw_gid=123)),patch.object(worker.grp,'getgrnam',return_value=SimpleNamespace(gr_gid=124)),patch.object(worker.pymysql,'connect',return_value=conn),patch.object(worker.subprocess,'run',return_value=SimpleNamespace(stdout='$6$hash\n')) as run,patch('builtins.open',side_effect=file_open):
                worker.main()
            text=path('/etc/dovecot/ctl-users').read_text()
            self.assertIn('info@'+domain+':preserved-hash',text)
            self.assertIn('mira.muster@'+domain+':{SHA512-CRYPT}$6$hash',text)
            self.assertTrue(path('/var/vmail/'+domain+'/mira.muster/Maildir/new').is_dir())
            self.assertTrue(any('status=\'ready\'' in call.args[0] for call in cursor.execute.call_args_list))
            self.assertTrue(all(secret not in str(call.args) for call in run.call_args_list))
            conn.commit.assert_called_once()
