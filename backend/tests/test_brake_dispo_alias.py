import ast,tempfile,unittest
from pathlib import Path

class DispoAliasTest(unittest.TestCase):
    def test_additive_alias_respects_existing_mailboxes_and_aliases(self):
        script=(Path(__file__).parents[2]/'install-ctlsoftware-test.sh').read_text()
        code=script.split("<<'CTL_FRESH_SERVER'\n",1)[1].split('\nCTL_FRESH_SERVER',1)[0]
        tree=ast.parse(code)
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='ensure_dispo_alias')
        for box,alias,expected in [('diso@example.com 1\n','info@example.com other@example.com\n',True),('diso@example.com 1\ndispo@example.com 1\n','',False),('diso@example.com 1\n','dispo@example.com other@example.com\n',False)]:
            with tempfile.TemporaryDirectory() as temp:
                root=Path(temp);folder=root/'etc/postfix';folder.mkdir(parents=True)
                (folder/'ctl-mailboxes').write_text(box);(folder/'ctl-aliases').write_text(alias);calls=[]
                namespace=dict(Path=lambda value:root/value.lstrip('/'),DOMAIN='example.com',write=lambda path,text:path.write_text(text),run=lambda args:calls.append(args))
                exec(compile(ast.Module(body=[fn],type_ignores=[]),'alias','exec'),namespace)
                namespace['ensure_dispo_alias']();first=(folder/'ctl-aliases').read_text()
                if expected:self.assertEqual(first,alias+'dispo@example.com diso@example.com\n');self.assertEqual(len(calls),2)
                else:self.assertEqual(first,alias);self.assertEqual(calls,[])
                namespace['ensure_dispo_alias']();self.assertEqual((folder/'ctl-aliases').read_text(),first)
