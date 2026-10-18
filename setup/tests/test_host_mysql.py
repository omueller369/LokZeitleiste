import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit,unquote
import yaml

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('host_mysql',ROOT/'setup/host-mysql.py')
host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)


class HostMySQLTest(unittest.TestCase):
    def test_credentials_are_encoded_and_never_in_process_arguments(self):
        password='synthetic:$@"\\secret'
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'.env.host'
            with patch('builtins.input',side_effect=['','']),patch.object(host.getpass,'getpass',return_value=password),patch.object(host.subprocess,'run') as run:
                host.prepare(path)
                for call in run.call_args_list:
                    self.assertNotIn(password,' '.join(call.args[0]))
                self.assertIn('CREATE DATABASE IF NOT EXISTS `ctl_software`',run.call_args_list[0].args[0][-1])
            self.assertEqual(host.settings(path),('ctl-software',password,'ctl_software'))
            self.assertEqual(path.stat().st_mode&0o777,0o600)
            original=path.read_bytes()
            with patch.object(host.subprocess,'run'),patch('builtins.input',side_effect=AssertionError):host.prepare(path)
            self.assertEqual(original,path.read_bytes())

    def test_failed_connection_does_not_store_new_credentials(self):
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'.env.host'
            with patch('builtins.input',side_effect=['','']),patch.object(host.getpass,'getpass',return_value='synthetic'),patch.object(host.subprocess,'run',side_effect=host.subprocess.CalledProcessError(1,['mysql'])),self.assertRaises(host.subprocess.CalledProcessError):
                host.prepare(path)
            self.assertFalse(path.exists())

    def test_backup_uses_private_option_file_and_writes_compressed_dump(self):
        import gzip
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'.env.host';target=Path(name)/'database.sql.gz'
            path.write_text('DATABASE_URL=mysql+pymysql://ctl-software:synthetic@127.0.0.1:3306/ctl_software?charset=utf8mb4\n')
            configs=[]
            def dump(args,**kwargs):
                private=Path(args[1].split('=',1)[1]);configs.append(private)
                self.assertEqual(private.stat().st_mode&0o777,0o600)
                self.assertNotIn('synthetic',' '.join(args))
                kwargs['stdout'].write(b'CREATE TABLE example (id INT);')
            with patch.object(host,'dump_options',return_value=['--single-transaction']),patch.object(host.subprocess,'run',side_effect=dump):host.backup(path,target)
            self.assertIn(b'CREATE TABLE',gzip.decompress(target.read_bytes()))
            self.assertFalse(configs[0].exists())

    def test_dump_options_match_installed_client(self):
        from types import SimpleNamespace
        for help_text,gtid in [('--single-transaction --no-tablespaces --set-gtid-purged=name',True),
                               ('--single-transaction --no-tablespaces',False),('--single-transaction',False)]:
            with patch.object(host.subprocess,'run',return_value=SimpleNamespace(stdout=help_text)) as run:
                options=host.dump_options()
                self.assertEqual('--set-gtid-purged=OFF' in options,gtid)
                self.assertEqual('--no-tablespaces' in options,'--no-tablespaces' in help_text)
                self.assertIn('--single-transaction',options)
                self.assertEqual(run.call_args.args[0],['mysqldump','--no-defaults','--help'])

    def test_host_stack_has_no_database_service_and_binds_only_loopback(self):
        stack=yaml.safe_load((ROOT/'backend/compose.host.yaml').read_text())
        self.assertNotIn('db',stack['services'])
        self.assertNotIn('mysql_data',stack.get('volumes',{}))
        for name in ('api','mailer','mailpit'):
            self.assertEqual(stack['services'][name]['network_mode'],'host')
            self.assertNotIn('ports',stack['services'][name])
        self.assertIn('--host 127.0.0.1',stack['services']['api']['command'][-1])
        self.assertEqual(stack['services']['mailpit']['environment']['MP_UI_BIND_ADDR'],'127.0.0.1:8025')
        self.assertEqual(stack['services']['mailpit']['environment']['MP_SMTP_BIND_ADDR'],'127.0.0.1:1025')


if __name__=='__main__':unittest.main()
