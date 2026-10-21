import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


class DemoTfRoutineTest(unittest.TestCase):
    def test_help_and_bash_syntax(self):
        subprocess.run(['bash','-n',str(ROOT/'setup-demo-tf.sh')],check=True)
        result=subprocess.run(['bash',str(ROOT/'setup-demo-tf.sh'),'--help'],capture_output=True,text=True,check=True)
        self.assertIn('Vorhandene Konten',result.stdout)

    @unittest.skipUnless(os.geteuid()==0,'Wrapper integration requires Linux root (all server commands mocked).')
    def test_backup_before_import_and_restart_on_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'backend/testenv').mkdir(parents=True);(root/'bin').mkdir()
            (root/'setup-demo-tf.sh').write_bytes((ROOT/'setup-demo-tf.sh').read_bytes())
            (root/'backend/.env.host').touch()
            (root/'setup-demo.sh').write_text('#!/usr/bin/env bash\nprintf "update\\n" >> "$IMPORT_TEST_LOG"\n')
            (root/'backend/testenv/control-host.sh').write_text('#!/usr/bin/env bash\nprintf "control %s\\n" "$1" >> "$IMPORT_TEST_LOG"\n')
            docker=root/'bin/docker'
            docker.write_text('#!/usr/bin/env bash\nprintf "docker %s\\n" "$*" >> "$IMPORT_TEST_LOG"\nif [[ "$*" == *" run "* && "${IMPORT_TEST_FAIL:-0}" == 1 ]];then exit 17;fi\n')
            docker.chmod(0o755)
            for fail in ('0','1'):
                log=root/'calls';log.write_text('')
                env=dict(os.environ,PATH=str(root/'bin')+':'+os.environ['PATH'],IMPORT_TEST_LOG=str(log),IMPORT_TEST_FAIL=fail)
                result=subprocess.run(['bash',str(root/'setup-demo-tf.sh')],env=env,capture_output=True,text=True)
                self.assertEqual(result.returncode,0 if fail=='0' else 17,result.stderr)
                calls=log.read_text();self.assertLess(calls.index('control backup'),calls.index(' run '))
                self.assertIn('lokzeitleiste.accounts.import_demo_tf --seed 23',calls)
                if fail=='0':self.assertIn('control start',calls)
                else:self.assertIn(' start api mailer',calls)
                self.assertNotIn('--replace-all-tf',calls)
