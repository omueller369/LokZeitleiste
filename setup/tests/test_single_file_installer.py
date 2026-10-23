import ast
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('installer',ROOT/'setup/ispconfig_install.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)

class SingleFileInstallerTest(unittest.TestCase):
    def test_embedded_files_are_complete_current_and_compile(self):
        script=(ROOT/'install-ctl-software.sh').read_text()
        helper=script.split("<<'CTL_APP_HELPER'\n",1)[1].split('\nCTL_APP_HELPER\n',1)[0]+'\n'
        engine=script.split("<<'CTL_INSTALL_ENGINE'\n",1)[1].split('\nCTL_INSTALL_ENGINE\n',1)[0]+'\n'
        self.assertEqual(helper,(ROOT/'setup/ispconfig_app.py').read_text())
        self.assertEqual(engine,(ROOT/'setup/ispconfig_install.py').read_text())
        ast.parse(helper);ast.parse(engine)
        subprocess.run(['bash','-n',str(ROOT/'install-ctl-software.sh')],check=True)
        self.assertIn('git clone --branch setup/debian-testumgebung',script)
        self.assertIn('CTL_INSTALL_SOURCE="$source_dir"',script)
        self.assertIn('CTL_INSTALL_HELPER="$work_dir/ispconfig_app.py"',script)
    def test_help_and_invalid_options_never_escalate_or_install(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);log=folder/'invoked'
            for command in ('sudo','apt-get','git','systemctl'):
                path=folder/command;path.write_text('#!/bin/sh\necho called >> "'+str(log)+'"\nexit 99\n');path.chmod(0o755)
            env={**os.environ,'PATH':str(folder)+os.pathsep+os.environ['PATH']}
            help_result=subprocess.run(['bash',str(ROOT/'install-ctl-software.sh'),'--help'],env=env,capture_output=True,text=True)
            self.assertEqual(help_result.returncode,0,help_result.stderr);self.assertIn('MariaDB',help_result.stdout)
            invalid=subprocess.run(['bash',str(ROOT/'install-ctl-software.sh'),'--wrong'],env=env,capture_output=True,text=True)
            self.assertEqual(invalid.returncode,2);self.assertFalse(log.exists())
    def test_existing_site_matches_exact_host_and_alias(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'website.vhost'
            path.write_text('<VirtualHost *:80>\n ServerName website.example.com\n ServerAlias ctl.example.com other.example.com\n</VirtualHost>')
            self.assertTrue(installer.existing_site('ctl.example.com','apache',folder))
            self.assertFalse(installer.existing_site('example.com','apache',folder))
            self.assertFalse(installer.existing_site('ctl.example.com.evil','apache',folder))
            path.write_text('server {\n server_name ctl.example.com other.example.com;\n}')
            self.assertTrue(installer.existing_site('ctl.example.com','nginx',folder))
            self.assertFalse(installer.existing_site('example.com','nginx',folder))

if __name__=='__main__':unittest.main()
