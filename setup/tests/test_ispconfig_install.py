import argparse
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit,unquote

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('ispconfig_install',ROOT/'setup/ispconfig_install.py')
setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)

class IspconfigInstallTest(unittest.TestCase):
    def test_credentials_are_url_encoded_and_invalid_inputs_rejected(self):
        password='s@fe:$`"/ä?#%';url=setup.database_url('127.0.0.1',3306,'c1_ctl','c1_user',password)
        parsed=urlsplit(url);self.assertEqual(unquote(parsed.password),password);self.assertEqual(parsed.hostname,'127.0.0.1')
        self.assertEqual(unquote(parsed.username),'c1_user')
        for name in ('bad-name','schema;drop','x'*65):
            with self.assertRaises(ValueError):setup.database_url('127.0.0.1',3306,name,'user',password)
        with self.assertRaises(ValueError):setup.database_url('127.0.0.1',3306,'db','user','line\nbreak')
        for domain in ('https://example.com','example.com/','a\nProxyPass / x','-bad.example','a..b'):
            with self.assertRaises(ValueError):setup.origin(domain)
    def test_units_and_proxy_are_application_only(self):
        unit=setup.unit(18080);self.assertIn('--host 127.0.0.1 --port 18080',unit)
        self.assertIn('User=lokzeitleiste-ispconfig',unit);self.assertIn('ProtectSystem=strict',unit)
        self.assertNotIn('password',unit.lower());self.assertIn('reports.worker',setup.unit(18080,True))
        apache=setup.proxy_config(18080,'apache',True);self.assertIn('ProxyPass /.well-known/acme-challenge/ !',apache)
        self.assertIn('X-Forwarded-Proto "http"',apache);self.assertIn('33554432',apache)
        nginx=setup.proxy_config(18080,'nginx');self.assertIn('proxy_pass http://127.0.0.1:18080;',nginx);self.assertIn('client_max_body_size 32m',nginx)
        env=setup.env_file({'TEST':'quotes" dollar$ backtick` slash\\'})
        self.assertIn('TEST="',env);self.assertNotIn('\nTEST=',env)
        with self.assertRaises(ValueError):setup.env_file({'TEST':'newline\n'})
    def test_check_does_not_prompt_write_or_install(self):
        with patch.object(sys,'argv',['setup-ispconfig','--check']),patch.object(setup,'preflight') as check,patch.object(setup.getpass,'getpass') as prompt,patch.object(setup.subprocess,'run') as run:
            setup.main();check.assert_called_once();prompt.assert_not_called();run.assert_not_called()
    def test_complete_install_generates_private_config_and_only_app_services(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);install=root/'app';config=root/'config';data=root/'data';units=root/'units';units.mkdir()
            helper=root/'private-helper.py';helper.write_text((ROOT/'setup/ispconfig_app.py').read_text());helper.chmod(0o600)
            account=SimpleNamespace(pw_uid=99,pw_gid=99,pw_shell='/usr/sbin/nologin')
            reply=SimpleNamespace(stdout=json.dumps({'created':20,'people':[]}))
            response=SimpleNamespace(status=200,__enter__=lambda self:self,__exit__=lambda *a:None)
            class Healthy:
                def __enter__(self):return response
                def __exit__(self,*args):pass
            args=['setup-ispconfig','--domain','ctl-software.example.com','--http','--db-name','c1_ctl','--db-user','c1_ctl']
            with patch.multiple(setup,INSTALL=install,CONFIG=config,DATA=data,UNIT_DIR=units,APP_HELPER=helper),patch.object(sys,'argv',args),patch.object(setup,'preflight'),patch.object(setup.os,'geteuid',return_value=0),patch.object(setup.os,'chown'),patch.object(setup.pwd,'getpwnam',return_value=account),patch.object(setup.getpass,'getpass',return_value='secret@Password'),patch.object(setup.subprocess,'run') as run,patch.object(setup,'run_application',return_value=reply) as application,patch.object(setup,'urlopen',return_value=Healthy()):
                setup.main()
                self.assertTrue(json.loads((config/'installation.json').read_text())['complete'])
                env=json.loads((config/'environment.json').read_text())
                from cryptography.fernet import Fernet
                Fernet(env['MAILBOX_ENCRYPTION_KEY'].encode())
                self.assertEqual(env['PUBLIC_ORIGIN'],'http://ctl-software.example.com');self.assertEqual(env['COOKIE_SECURE'],'false')
                self.assertEqual(env['SMTP_HOST'],'');self.assertEqual(env['PYTHONPATH'],str(install/'backend'))
                self.assertEqual((config/'app.env').stat().st_mode&0o777,0o600)
                self.assertEqual((config/'admin-initial-password').stat().st_mode&0o777,0o600)
                calls=[str(c.args[0]) for c in run.call_args_list]
                self.assertTrue(any('systemctl' in c and 'enable' in c for c in calls))
                self.assertFalse(any(any(x in c for x in ('apt-get','docker','a2ensite','certbot','mysqladmin')) for c in calls))
                self.assertFalse(any('secret@Password' in c for c in calls))
                modes=[call.args[0] for call in application.call_args_list]
                self.assertEqual(modes[0][-1],'empty')
                self.assertIn(['-m','lokzeitleiste.accounts.import_demo_tf','--seed','23'],modes)
                self.assertTrue((units/'lokzeitleiste-ispconfig.service').is_file())
                self.assertEqual((install/'ispconfig_app.py').stat().st_mode&0o777,0o644)
                self.assertEqual((install/'backend/lokzeitleiste/main.py').stat().st_mode&0o777,0o644)
                with patch.object(sys,'argv',['setup-ispconfig','--resume']):
                    with self.assertRaisesRegex(ValueError,'bereits vollständig'):setup.main()
                state=json.loads((config/'installation.json').read_text());state['complete']=False
                (config/'installation.json').write_text(json.dumps(state));password_before=(config/'admin-initial-password').read_text()
                application.reset_mock()
                with patch.object(sys,'argv',['setup-ispconfig','--resume']):setup.main()
                self.assertTrue(json.loads((config/'installation.json').read_text())['complete'])
                self.assertEqual((config/'admin-initial-password').read_text(),password_before)
                self.assertEqual(json.loads((config/'environment.json').read_text()),env)
                self.assertFalse(any(call.args[0][-1]=='empty' for call in application.call_args_list))
    def test_existing_target_refused_before_password_or_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'existing';target.mkdir()
            with patch.multiple(setup,INSTALL=target,CONFIG=Path(folder)/'config',DATA=Path(folder)/'data'),patch.object(sys,'argv',['setup-ispconfig','--domain','example.com','--db-name','db','--db-user','user']),patch.object(setup,'preflight'),patch.object(setup.os,'geteuid',return_value=0),patch.object(setup.getpass,'getpass') as prompt:
                with self.assertRaisesRegex(ValueError,'bereits vorhanden'):setup.main()
                prompt.assert_not_called()



class IspconfigDatabaseGuardTest(unittest.TestCase):
    def test_nonempty_database_is_rejected_without_changing_it(self):
        from sqlalchemy import create_engine,text,inspect
        helper_spec=importlib.util.spec_from_file_location('ispconfig_app',ROOT/'setup/ispconfig_app.py')
        helper=importlib.util.module_from_spec(helper_spec);helper_spec.loader.exec_module(helper)
        db=create_engine('sqlite+pysqlite://')
        with db.begin() as connection:connection.execute(text('CREATE TABLE preserved (id INTEGER)'))
        with patch.object(helper,'engine',return_value=db),patch.object(sys,'argv',['helper','empty']):
            with self.assertRaisesRegex(SystemExit,'nicht leer'):helper.main()
        self.assertEqual(inspect(db).get_table_names(),['preserved'])
        db.dispose()

if __name__=='__main__':unittest.main()
