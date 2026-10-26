import io,json,unittest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session
from sqlalchemy import select
import test_accounts
from lokzeitleiste.main import app
from lokzeitleiste.models import AccountLoginStamp,User

class TfMessagesTest(unittest.TestCase):
    tearDown=test_accounts.AccountsTest.tearDown
    def setUp(self):
        test_accounts.AccountsTest.setUp(self)
        self.other_id=self.create_tf('787222','MSG-OTHER').json()['id']
        self.sender=self.login('787100');self.other=self.login('787222')
    def login(self,username):
        client=TestClient(app,base_url='https://testserver');self.staff_clients.append(client)
        result=client.post('/api/v1/account/login',json={'username':username,'password':'tf-secret-12345'});self.assertEqual(result.status_code,200,result.text);return client
    def send(self,**changes):
        body=dict(recipients=[self.other_id],subject='Testnachricht',body='Zeile 1\nZeile 2');body.update(changes)
        result=self.sender.post('/api/v1/tf/messages',data={'payload':json.dumps(body)})
        self.assertEqual(result.status_code,201,result.text);return result.json()['id']
    def test_private_recipient_names_and_inbox_read_delete(self):
        choices=self.sender.get('/api/v1/tf/messages/recipients').json()
        self.assertTrue(all(set(r)=={'id','name'} for r in choices));self.assertNotIn('787222',json.dumps(choices));self.assertNotIn('787100',json.dumps(choices))
        mid=self.send();base='/api/v1/tf/messages/'+str(mid)
        self.assertEqual(self.sender.get(base).status_code,404)
        self.assertEqual(self.other.get('/api/v1/tf/messages/unread').json()['count'],1)
        self.assertFalse(self.other.get('/api/v1/tf/messages').json()['messages'][0]['read'])
        detail=self.other.get(base);self.assertEqual(detail.status_code,200);self.assertEqual(detail.json()['body'],'Zeile 1\nZeile 2');self.assertNotIn('username',detail.json());self.assertNotIn('sender_id',detail.json())
        self.assertEqual(self.other.get('/api/v1/tf/messages/unread').json()['count'],0)
        self.assertEqual(self.other.put(base+'/read',json={'read':False}).status_code,200)
        self.assertEqual(self.other.get('/api/v1/tf/messages/unread').json()['count'],1)
        self.assertEqual(self.sender.delete(base).status_code,404)
        self.assertEqual(self.other.delete(base).status_code,200)
        self.assertEqual(self.other.get(base).status_code,404)
        self.assertEqual(self.other.get('/api/v1/tf/messages').json()['total'],0)
    def test_broadcast_forward_and_independent_deletion(self):
        mid=self.send(all_tf=True);self.assertEqual(self.sender.get('/api/v1/tf/messages').json()['total'],1)
        self.assertEqual(self.sender.get('/api/v1/tf/messages/unread').json()['count'],0)
        forwarded=self.other.post(f'/api/v1/tf/messages/{mid}/forward',json={'recipients':[self.tf]});self.assertEqual(forwarded.status_code,201,forwarded.text)
        new=forwarded.json()['id'];self.other.delete(f'/api/v1/tf/messages/{mid}')
        result=self.sender.get(f'/api/v1/tf/messages/{new}');self.assertEqual(result.status_code,200);self.assertEqual(result.json()['subject'],'WG: Testnachricht')
        self.assertEqual(self.sender.get(f'/api/v1/tf/messages/{mid}').status_code,200)
    def test_attachment_preview_download_and_forward_authorization(self):
        image=io.BytesIO();Image.new('RGB',(5,5),'green').save(image,format='PNG');content=image.getvalue()
        payload=dict(recipients=[self.other_id],subject='Bild',body='Anhang')
        result=self.sender.post('/api/v1/tf/messages',data={'payload':json.dumps(payload)},files={'file':('Bild.png',content,'image/png')});self.assertEqual(result.status_code,201,result.text)
        mid=result.json()['id'];path=f'/api/v1/tf/messages/{mid}'
        detail=self.other.get(path).json();self.assertEqual(detail['attachment']['mime_type'],'image/png')
        self.assertEqual(self.sender.get(path+'/attachment').status_code,404)
        self.assertEqual(self.other.get(path+'/attachment').content,content)
        new=self.other.post(path+'/forward',json={'recipients':[self.tf]}).json()['id'];self.other.delete(path)
        self.assertEqual(self.sender.get(f'/api/v1/tf/messages/{new}/attachment').content,content)
        too_large=self.sender.post('/api/v1/tf/messages',data={'payload':json.dumps(payload)},files={'file':('big.dat',b'x'*(10*1024*1024+1),'application/octet-stream')});self.assertEqual(too_large.status_code,413)
    def test_validation_and_roles(self):
        for body in [dict(recipients=[],subject='Test',body='Text'),dict(recipients=[self.other_id],subject=' ',body='Text'),dict(recipients=[self.other_id],subject='Test',body='x'*1001),dict(recipients=[999999],subject='Test',body='Text')]:
            self.assertEqual(self.sender.post('/api/v1/tf/messages',data={'payload':json.dumps(body)}).status_code,422)
        anonymous=TestClient(app,base_url='https://testserver');self.staff_clients.append(anonymous)
        self.assertEqual(anonymous.get('/api/v1/tf/messages').status_code,401)
        self.assertEqual(self.client.get('/api/v1/tf/messages').status_code,403)
        with Session(self.engine) as db:db.get(User,self.other_id).active=False;db.commit()
        self.assertEqual(self.sender.post('/api/v1/tf/messages',data={'payload':json.dumps(dict(recipients=[self.other_id],subject='Test',body='Text'))}).status_code,422)
    def test_own_profile_shell_login_and_page_assets(self):
        meta=self.sender.get('/api/v1/tf/shell').json();self.assertEqual(meta['tf_number'],'787100');self.assertTrue(meta['last_login_at'].endswith('Z'));self.assertIn('version',meta)
        with Session(self.engine) as db:stamp=db.get(AccountLoginStamp,self.tf);first=stamp.last_login_at
        self.login('787100')
        with Session(self.engine) as db:self.assertEqual(db.get(AccountLoginStamp,self.tf).previous_login_at,first)
        with Session(self.engine) as db:db.delete(db.get(AccountLoginStamp,self.tf));db.commit()
        self.assertTrue(self.sender.get('/api/v1/tf/shell').json()['last_login_at'])
        own=self.sender.get('/api/v1/tf/me',params={'user_id':self.other_id}).json();self.assertEqual(own['data']['tf_number'],787100);self.assertIn('addresses',own['data']);self.assertNotIn('password',json.dumps(own));self.assertNotIn('token',json.dumps(own))
        for path in ['/tf/me','/tf/nachrichten','/tf/messages.js','/tf/shell.js','/tf/shell.css','/tf/profile.js','/tf/ctl-logistics-logo.jpg']:
            self.assertEqual(self.sender.get(path).status_code,200,path)
        landing=self.sender.get('/tf').text;self.assertIn('href="/tf/nachrichten"',landing);header=landing.split('<header>')[1].split('</header>')[0];self.assertNotIn('Meine Dokumente',header);self.assertNotIn('/account',header)

    def test_sent_listing_detail_recipients_and_unread_isolation(self):
        first=self.send(subject='Erste Nachricht');second=self.send(subject='Zweite Nachricht',all_tf=True)
        sent=self.sender.get('/api/v1/tf/messages/sent');self.assertEqual(sent.status_code,200,sent.text)
        data=sent.json();self.assertEqual(data['total'],2);self.assertEqual([m['id'] for m in data['messages']],[second,first])
        self.assertTrue(data['messages'][0]['recipient_names']);self.assertNotIn('787222',json.dumps(data));self.assertNotIn('recipient_id',json.dumps(data))
        self.assertEqual(self.other.get('/api/v1/tf/messages/sent').json()['total'],0)
        path=f'/api/v1/tf/messages/sent/{first}'
        self.assertEqual(self.other.get(path).status_code,404)
        before=self.other.get('/api/v1/tf/messages/unread').json()['count']
        detail=self.sender.get(path);self.assertEqual(detail.status_code,200);self.assertEqual(detail.json()['body'],'Zeile 1\nZeile 2')
        self.assertEqual(self.other.get('/api/v1/tf/messages/unread').json()['count'],before)
        self.other.delete(f'/api/v1/tf/messages/{first}')
        self.assertEqual(self.sender.get(path).status_code,200)
        page=self.sender.get('/api/v1/tf/messages/sent',params={'offset':1,'limit':1}).json();self.assertEqual([m['id'] for m in page['messages']],[first])

    def test_sent_attachment_is_only_accessible_to_sender(self):
        payload=dict(recipients=[self.other_id],subject='Gesendeter Anhang',body='Text')
        response=self.sender.post('/api/v1/tf/messages',data={'payload':json.dumps(payload)},files={'file':('Text.txt',b'Originalinhalt','text/plain')})
        self.assertEqual(response.status_code,201,response.text);mid=response.json()['id'];path=f'/api/v1/tf/messages/sent/{mid}'
        detail=self.sender.get(path).json();self.assertEqual(detail['attachment']['url'],path+'/attachment')
        self.assertEqual(self.sender.get(path+'/attachment').content,b'Originalinhalt')
        self.assertEqual(self.other.get(path+'/attachment').status_code,404)
        self.other.delete(f'/api/v1/tf/messages/{mid}')
        self.assertEqual(self.sender.get(path+'/attachment').content,b'Originalinhalt')
