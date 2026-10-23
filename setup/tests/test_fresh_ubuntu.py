import ast
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('fresh_ubuntu',ROOT/'setup/fresh_ubuntu.py')
fresh=importlib.util.module_from_spec(spec);spec.loader.exec_module(fresh)

class FreshUbuntuTest(unittest.TestCase):
    def test_roundcube_php85_patch_is_guarded_idempotent_and_preserves_other_code(self):
        old="<?php\nfunction array_first($array)\n{\n    if (is_array($array)) {\n        return reset($array);\n    }\n    return null;\n}\n// next function\n"
        fixed=fresh.roundcube_php85_patch(old)
        self.assertIn("if (!function_exists('array_first')) {",fixed)
        self.assertTrue(fixed.endswith('// next function\n'))
        self.assertEqual(fresh.roundcube_php85_patch(fixed),fixed)
        self.assertEqual(fresh.roundcube_php85_patch('<?php // no polyfill'), '<?php // no polyfill')
        with self.assertRaises(ValueError):fresh.roundcube_php85_patch('<?php function array_first($x) {}')

    def test_fixed_identity_and_secure_service_configs(self):
        self.assertEqual(fresh.DOMAIN,'ctl-software.io-goerlitz.eu');self.assertEqual(fresh.IP,'212.227.86.251')
        self.assertEqual(fresh.DB_USER,'dbo_ctl');self.assertEqual(fresh.DB_NAME,'db_ctl')
        self.assertEqual(fresh.MAIL_USERS,('info','diso','vkplanung','railpool'))
        dovecot=fresh.dovecot_config();self.assertTrue(dovecot.startswith('dovecot_config_version = 2.4.0'))
        self.assertIn('passwd_file_path = /etc/dovecot/ctl-users',dovecot);self.assertIn('auth_allow_cleartext = no',dovecot)
        self.assertIn('ssl = required',dovecot);self.assertIn('port = 993',dovecot)
        self.assertNotIn('ssl_cert =',dovecot);self.assertNotIn('plugin {',dovecot)
        self.assertEqual(dovecot.count('{'),dovecot.count('}'))
        postfix=fresh.postfix_config();self.assertIn('reject_unauth_destination',postfix)
        self.assertIn('virtual_mailbox_domains = '+fresh.DOMAIN,postfix)
        self.assertIn('recipient_canonical_classes = envelope_recipient\n',postfix)
        self.assertIn('smtpd_sasl_auth_enable = no',postfix)
        submission=fresh.postfix_submission();self.assertIn('smtpd_tls_security_level=encrypt',submission)
        self.assertIn('permit_sasl_authenticated,reject',submission)
        self.assertIn('keep;',fresh.forward_script());self.assertIn('redirect "omueller369@gmail.com";',fresh.forward_script())
    def test_dns_and_apache_ipv4_tls_configuration(self):
        zone=fresh.bind_zone('ctl._domainkey IN TXT "key"',123)
        for value in ('IN NS ns1.'+fresh.DOMAIN,'IN MX 10 '+fresh.DOMAIN,'ip4:'+fresh.IP,'_dmarc IN TXT','ctl._domainkey'):
            self.assertIn(value,zone)
        self.assertNotIn('AAAA',zone)
        tls=fresh.apache_config(True);self.assertIn('SSLEngine On',tls);self.assertIn('127.0.0.1:18080',tls)
        self.assertIn('ProxyPass /.well-known/acme-challenge/ !',tls)
        self.assertNotIn('ProxyPass / http',fresh.apache_config())
    def test_php_apps_are_routed_before_backend_and_use_mail_credentials(self):
        apache=fresh.apache_config(True,'8.5')
        for path in ('/phpmyadmin','/webmailer'):
            self.assertLess(apache.index('ProxyPass '+path+' !'),apache.index('ProxyPass / http'))
        self.assertIn('php8.5-fpm.sock',apache)
        self.assertIn('Require all denied',apache)
        pma=fresh.phpmyadmin_config('a'*32)
        self.assertIn("['auth_type'] = 'cookie'",pma)
        self.assertIn("['AllowRoot'] = false",pma)
        self.assertNotIn('tomcom123456',pma)
        mail=fresh.roundcube_config('a'*24)
        self.assertIn('ssl://'+fresh.DOMAIN+':993',mail)
        self.assertIn('ssl://'+fresh.DOMAIN+':465',mail)
        self.assertIn("['smtp_pass'] = '%p'",mail)
        self.assertIn("['enable_installer'] = false",mail)
        self.assertIn("'verify_peer' => true",mail)
        self.assertIn('php-sqlite3',fresh.PACKAGES)

    def test_database_password_parameterized_and_nonempty_schema_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            state=Path(folder);(state/'database-password').write_text("secret'\\with$chars")
            cursor=Mock();cursor.__enter__=Mock(return_value=cursor);cursor.__exit__=Mock(return_value=False);cursor.fetchone.return_value=(0,)
            connection=Mock();connection.__enter__=Mock(return_value=connection);connection.__exit__=Mock(return_value=False);connection.cursor.return_value=cursor
            client=SimpleNamespace(connect=Mock(return_value=connection))
            with patch.object(fresh,'STATE',state),patch.object(fresh,'run') as run,patch.object(fresh,'write'),patch.dict(sys.modules,{'pymysql':client}):
                fresh.prepare_database()
                commands=[call.args for call in cursor.execute.call_args_list]
                create_users=[call for call in commands if call[0].startswith('CREATE USER')]
                self.assertEqual(len(create_users),2)
                self.assertTrue(all(call[1][0]=='dbo_ctl' and call[1][2]=="secret'\\with$chars" for call in create_users))
                self.assertFalse(any('DROP ' in call[0] for call in commands))
                self.assertFalse(any("secret'" in str(call.args[0]) for call in run.call_args_list))
                cursor.reset_mock();cursor.fetchone.return_value=(2,)
                with self.assertRaisesRegex(ValueError,'bereits Tabellen'):fresh.prepare_database()
                self.assertEqual(cursor.execute.call_count,1)
    def test_public_dns_accepts_strato_without_delegation(self):
        def dns(command):
            if '-x' in command:return fresh.DOMAIN+'.'
            kind=command[-1];name=command[-2]
            if kind=='A':return fresh.IP
            if kind=='AAAA':return ''
            if kind=='NS':raise AssertionError('No NS lookup allowed')
            if kind=='MX':return '10 '+fresh.DOMAIN+'.'
            if name.startswith('_dmarc.'):return '"v=DMARC1; p=none"'
            if name==fresh.DOMAIN:return '"v=spf1 ip4:'+fresh.IP+' -all"'
            return '"v=DKIM1; p=key"'
        with tempfile.TemporaryDirectory() as folder:
            state=Path(folder);(state/'provider-dns.txt').write_text('Provider-Einträge prüfen')
            with patch.object(fresh,'STATE',state),patch.object(fresh,'output',side_effect=dns),patch.object(fresh,'local_dkim',return_value='v=DKIM1; p=key'):fresh.public_dns_check()
            def a_only(command):return fresh.IP if command[-1]=='A' else ''
            with patch.object(fresh,'STATE',state),patch.object(fresh,'output',side_effect=a_only),patch.object(fresh,'local_dkim',return_value='v=DKIM1; p=key'):
                with self.assertRaisesRegex(ValueError,'MX muss'):fresh.public_dns_check()
    def test_resume_does_not_repeat_completed_database_stage(self):
        names=['prepare_packages','prepare_hostname','prepare_firewall','prepare_database','prepare_php_apps','prepare_dns','public_dns_check','prepare_certificate','prepare_mail','prepare_application','finish_web','repair_roundcube_php85','verify']
        with tempfile.TemporaryDirectory() as folder:
            state=Path(folder);(state/'database-password').write_text('existing-password')
            mocks={name:Mock() for name in names};mocks['public_dns_check'].side_effect=ValueError('DNS records missing')
            with patch.object(fresh,'STATE',state),patch.object(fresh.os,'geteuid',return_value=0),patch.object(fresh,'output',return_value=json.dumps([{'addr_info':[{'local':fresh.IP}]}])),patch.multiple(fresh,**mocks),patch.object(sys,'argv',['fresh','--engine','/test/engine.py']):
                with self.assertRaisesRegex(ValueError,'DNS records missing'):fresh.main()
                self.assertEqual(mocks['prepare_database'].call_count,1);mocks['prepare_application'].assert_not_called()
                mocks['public_dns_check'].side_effect=None
                with patch.object(sys,'argv',['fresh','--resume','--engine','/test/engine.py']):fresh.main()
                self.assertEqual(mocks['prepare_database'].call_count,1);self.assertEqual(mocks['prepare_application'].call_count,1)
                self.assertTrue(json.loads((state/'state.json').read_text())['complete'])
                self.assertEqual((state/'database-password').read_text(),'existing-password')
    def test_single_file_embeds_current_helpers_and_help_is_read_only(self):
        script=(ROOT/'install-ctlsoftware-test.sh').read_text()
        for delimiter,path in [('CTL_FRESH_APP_HELPER','setup/ispconfig_app.py'),('CTL_FRESH_ENGINE','setup/ispconfig_install.py'),('CTL_FRESH_SERVER','setup/fresh_ubuntu.py')]:
            embedded=script.split("<<'"+delimiter+"'\n",1)[1].split('\n'+delimiter+'\n',1)[0]+'\n'
            self.assertEqual(embedded,(ROOT/path).read_text());ast.parse(embedded)
        subprocess.run(['bash','-n',str(ROOT/'install-ctlsoftware-test.sh')],check=True)
        result=subprocess.run(['bash',str(ROOT/'install-ctlsoftware-test.sh'),'--help'],capture_output=True,text=True,check=True)
        self.assertIn('ctl-software.io-goerlitz.eu',result.stdout)
        self.assertIn('db_ctl',result.stdout)

if __name__=='__main__':unittest.main()
