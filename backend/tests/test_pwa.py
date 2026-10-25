import io,unittest
from fastapi.testclient import TestClient
from PIL import Image
from lokzeitleiste.main import app

class PwaTest(unittest.TestCase):
    def setUp(self):self.client=TestClient(app,base_url='https://testserver')
    def tearDown(self):self.client.close()
    def test_separate_manifests_and_icons(self):
        ids=[];icons=[]
        for area,start in [('tf','/tf'),('backend','/admin/start')]:
            response=self.client.get(f'/pwa/{area}/manifest.webmanifest')
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.headers['content-type'],'application/manifest+json')
            data=response.json();ids.append(data['id']);self.assertEqual(data['start_url'],start)
            self.assertEqual(data['display'],'standalone');self.assertTrue(start.startswith(data['scope']))
            for item in data['icons']:
                image_response=self.client.get(item['src']);self.assertEqual(image_response.status_code,200)
                image=Image.open(io.BytesIO(image_response.content));size=int(item['sizes'].split('x')[0]);self.assertEqual(image.size,(size,size));self.assertEqual(image.format,'PNG')
                if size==192:icons.append(image_response.content)
            self.assertEqual(self.client.get(f'/pwa/{area}/icon-180.png').status_code,200)
        self.assertNotEqual(*ids);self.assertNotEqual(*icons)
        self.assertEqual(self.client.get('/pwa/tf/icon-999.png').status_code,404)
    def test_public_installation_pages_and_worker(self):
        for path in ['/tf/install','/admin/install']:
            page=self.client.get(path);self.assertEqual(page.status_code,200);self.assertIn('/auth-session.js',page.text);self.assertIn('rel="manifest"',page.text);self.assertIn('apple-touch-icon',page.text)
        for path in ['/pwa/install.js','/pwa/install.css','/pwa-sw.js']:
            response=self.client.get(path);self.assertEqual(response.status_code,200);self.assertEqual(response.headers['cache-control'],'no-cache')
        worker=self.client.get('/pwa-sw.js');self.assertEqual(worker.headers['service-worker-allowed'],'/')
        self.assertNotIn('caches.open',worker.text);self.assertNotIn('skipWaiting',worker.text)
        self.assertIn("event.request.mode!=='navigate'",worker.text)
