from datetime import timedelta
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from sqlalchemy.orm import Session
import test_stations
from lokzeitleiste.main import app
from lokzeitleiste.models import TfStationShare,TfStationDelivery,now_utc

class StationSharingTest(test_stations.StationDirectoryTest):
    def setUp(self):
        super().setUp()
        self.create_tf('787200','SHARE-RECIPIENT')
        self.other=TestClient(app,base_url='https://testserver');self.staff_clients.append(self.other)
        self.other.post('/api/v1/account/login',json={'username':'787200','password':'tf-secret-12345'})
        self.recipient=self.driver.get('/api/v1/tf/station-recipients').json()[0]['id']

    def share(self,rows,plans=False):
        r=self.driver.post('/api/v1/tf/station-shares',json={'station_ids':[row['id'] for row in rows],'recipient_id':self.recipient,'include_plans':plans})
        self.assertEqual(r.status_code,201,r.text);return r.json()

    def preview(self,share):
        r=self.other.get('/api/v1/tf/station-inbox/'+str(share['id']));self.assertEqual(r.status_code,200,r.text);return r.json()

    def take(self,share,items=None,mode='merge'):
        items=items if items is not None else self.preview(share)['items']
        return self.other.post('/api/v1/tf/station-inbox/'+str(share['id'])+'/import',json={'items':[{'id':i['id'],'expected_revision':i['expected_revision']} for i in items],'mode':mode})

    def test_snapshot_selection_repeat_and_source_isolation(self):
        row=self.create(contacts=[dict(category='bada',label='Fdl',number='00123')]);second=self.create('AAA')
        share=self.share([row,second]);items=self.preview(share)['items'];self.assertEqual([i['code'] for i in items],['AAA','BBB'])
        self.driver.delete('/api/v1/tf/stations/'+str(row['id']),params={'expected_revision':1})
        self.assertEqual(self.take(share,[items[1]]).json()['created'],1)
        target=self.other.get('/api/v1/tf/stations').json()[0]
        self.assertEqual(self.other.get('/api/v1/tf/stations/'+str(target['id'])).json()['contacts'][0]['number'],'00123')
        self.assertEqual(self.take(share).json()['created'],1)
        self.assertEqual(self.take(share).json()['unchanged'],2)
        self.assertEqual(len(self.driver.get('/api/v1/tf/stations').json()),1)

    def test_merge_preserves_plan_and_deduplicates(self):
        row=self.create(contacts=[dict(category='bada',label='Fdl',number='00123'),dict(category='mobile',label='Neu',number='00456')])
        own=self.other.post('/api/v1/tf/stations',json={'code':'BBB','contacts':[dict(category='bada',label='fdl',number='00 123')]}).json()
        for client,r,name in [(self.driver,row,'source.png'),(self.other,own,'own.png')]:
            self.assertEqual(client.put('/api/v1/tf/stations/'+str(r['id'])+'/plan',data={'expected_revision':1},files={'file':(name,self.png(),'image/png')}).status_code,200)
        share=self.share([row],True)
        self.assertEqual(self.take(share,mode='new_only').json()['skipped'],1)
        result=self.take(share);self.assertEqual(result.status_code,200,result.text);self.assertEqual(result.json()['extended'],1)
        target=self.other.get('/api/v1/tf/stations/'+str(own['id'])).json()
        self.assertEqual(len(target['contacts']),2);self.assertEqual(target['plan']['filename'],'own.png')
        self.assertEqual(self.take(share).json()['unchanged'],1)

    def test_conflict_and_atomic_rollback(self):
        rows=[self.create('AAA'),self.create('BBB',contacts=[dict(category='mobile',label='New',number='999')])]
        own=self.other.post('/api/v1/tf/stations',json={'code':'BBB','contacts':[dict(category='bada',label=str(i),number=str(i)) for i in range(100)]}).json()
        share=self.share(rows);items=self.preview(share)['items']
        self.assertEqual(self.take(share,items).status_code,409)
        self.assertEqual([r['code'] for r in self.other.get('/api/v1/tf/stations').json()],['BBB'])
        self.other.put('/api/v1/tf/stations/'+str(own['id']),json={'expected_revision':1,'contacts':[]})
        self.assertEqual(self.take(share,items).status_code,409)
        self.assertEqual(self.take(share).json()['created'],1)

    def test_plan_access_manual_removal_and_roles(self):
        row=self.create();self.driver.put('/api/v1/tf/stations/'+str(row['id'])+'/plan',data={'expected_revision':1},files={'file':('plan.png',self.png(),'image/png')})
        share=self.share([row],True);item=self.preview(share)['items'][0]
        url='/api/v1/tf/station-inbox/'+str(share['id']);plan=url+'/items/'+str(item['id'])+'/plan'
        self.assertEqual(self.other.get(plan).content,self.png())
        self.assertEqual(self.client.get(url).status_code,403)
        self.assertEqual(self.other.get(url+'/items/999999/plan').status_code,404)
        self.assertEqual(self.driver.delete('/api/v1/tf/station-inbox/'+str(share['id'])).status_code,404)
        self.assertEqual(self.take(share).json()['plans_added'],1)
        self.assertEqual(self.other.delete('/api/v1/tf/station-inbox/'+str(share['id'])).status_code,200)
        for response in (self.other.get(url),self.other.get(plan),self.take(share,[item])):self.assertEqual(response.status_code,404)
        self.assertEqual(len(self.other.get('/api/v1/tf/stations').json()),1)
        another=self.share([row])
        with Session(self.engine) as db:
            delivery=db.get(TfStationDelivery,another['id']);db.get(TfStationShare,delivery.share_id).expires_at=now_utc()-timedelta(days=1);db.commit()
        self.assertEqual(self.other.get('/api/v1/tf/station-inbox/'+str(another['id'])).status_code,200)

    def test_ownership_validation_and_size_rollback(self):
        row=self.create();self.assertEqual(self.other.post('/api/v1/tf/station-shares',json={'station_ids':[row['id']],'recipient_id':self.tf}).status_code,404)
        self.assertEqual(self.driver.post('/api/v1/tf/station-shares',json={'station_ids':[row['id'],row['id']],'recipient_id':self.recipient}).status_code,422)
        self.driver.put('/api/v1/tf/stations/'+str(row['id'])+'/plan',data={'expected_revision':1},files={'file':('plan.png',self.png(),'image/png')})
        with patch('lokzeitleiste.station_sharing.MAX_PLANS',1):
            self.assertEqual(self.driver.post('/api/v1/tf/station-shares',json={'station_ids':[row['id']],'recipient_id':self.recipient,'include_plans':True}).status_code,413)
        with Session(self.engine) as db:self.assertEqual(db.scalar(select(func.count()).select_from(TfStationShare)),0)

    def test_reset_cascades_shares(self):
        from lokzeitleiste.accounts.seed_demo_tf import delete_tf_records
        self.share([self.create()])
        with Session(self.engine) as db:
            delete_tf_records(db);db.commit();self.assertEqual(db.scalar(select(func.count()).select_from(TfStationShare)),0)

    def test_destination_choice_and_inbox_survives_import(self):
        source=self.create('AAA',contacts=[dict(category='bada',label='Fdl',number='00123')])
        target=self.other.post('/api/v1/tf/stations',json={'code':'CCC','contacts':[]}).json()
        delivery=self.share([source]);item=self.preview(delivery)['items'][0]
        result=self.other.post('/api/v1/tf/station-inbox/'+str(delivery['id'])+'/import',json={'items':[dict(id=item['id'],expected_revision=1,target_station_id=target['id'])]})
        self.assertEqual(result.status_code,200,result.text);self.assertEqual(result.json()['extended'],1)
        own=self.other.get('/api/v1/tf/stations/'+str(target['id'])).json()
        self.assertEqual(own['code'],'CCC');self.assertEqual(own['contacts'][0]['number'],'00123')
        self.assertEqual(len(self.other.get('/api/v1/tf/station-inbox').json()),1)
        self.assertEqual(self.driver.get('/api/v1/tf/station-inbox').json(),[])
        self.assertEqual(self.driver.get('/api/v1/tf/station-inbox/'+str(delivery['id'])).status_code,404)
        self.assertEqual(self.driver.get('/api/v1/tf/station-shares/'+'a'*43).status_code,404)
        foreign=self.create('BBB');result=self.other.post('/api/v1/tf/station-inbox/'+str(delivery['id'])+'/import',json={'items':[dict(id=item['id'],expected_revision=1,target_station_id=foreign['id'])]})
        self.assertEqual(result.status_code,404)

    def test_recipient_validation_and_unrelated_tf_isolation(self):
        self.create_tf('787300','THIRD-TF')
        third=TestClient(app,base_url='https://testserver');self.staff_clients.append(third)
        third.post('/api/v1/account/login',json={'username':'787300','password':'tf-secret-12345'})
        row=self.create();delivery=self.share([row]);item=self.preview(delivery)['items'][0]
        url='/api/v1/tf/station-inbox/'+str(delivery['id'])
        self.assertEqual(third.get('/api/v1/tf/station-inbox').json(),[])
        for r in [third.get(url),third.delete(url),third.get(url+'/items/'+str(item['id'])+'/plan'),third.post(url+'/import',json={'items':[dict(id=item['id'],expected_revision=0)]})]:self.assertEqual(r.status_code,404)
        recipients=self.driver.get('/api/v1/tf/station-recipients').json();self.assertEqual(len(recipients),2)
        self.assertNotIn(self.tf,[r['id'] for r in recipients])
        for recipient in [self.tf,999999]:self.assertEqual(self.driver.post('/api/v1/tf/station-shares',json={'station_ids':[row['id']],'recipient_id':recipient}).status_code,422)

    def test_notes_snapshot_and_fill_empty_without_overwriting(self):
        source=self.driver.post('/api/v1/tf/stations',json={'code':'BBB','locomotive_parking':'Gleis 1','train_securing':'Hemmschuhe','special_features':'Achtung\nBesonderheit'}).json()
        delivery=self.share([source]);item=self.preview(delivery)['items'][0]
        self.assertEqual(item['special_features'],'Achtung\nBesonderheit')
        self.driver.put('/api/v1/tf/stations/'+str(source['id']),json={'expected_revision':1,'special_features':'Später geändert'})
        target=self.other.post('/api/v1/tf/stations',json={'code':'BBB','locomotive_parking':'Eigene Abstellung'}).json()
        result=self.take(delivery);self.assertEqual(result.status_code,200,result.text)
        own=self.other.get('/api/v1/tf/stations/'+str(target['id'])).json()
        self.assertEqual(own['locomotive_parking'],'Eigene Abstellung')
        self.assertEqual(own['train_securing'],'Hemmschuhe');self.assertEqual(own['special_features'],'Achtung\nBesonderheit')
        self.assertEqual(self.take(delivery).json()['unchanged'],1)


    def test_tf_numbers_private_in_recipient_and_delivery_responses(self):
        recipients=self.driver.get('/api/v1/tf/station-recipients')
        self.assertEqual(recipients.status_code,200)
        for item in recipients.json():
            self.assertEqual(set(item),{'id','label'})
            self.assertNotIn('787200',item['label'])
        delivery=self.share([self.create()])
        for response in [recipients,self.other.get('/api/v1/tf/station-inbox'),self.other.get('/api/v1/tf/station-inbox/'+str(delivery['id']))]:
            for private in ['787100','787200','tf_number','username']:self.assertNotIn(private,response.text)
        # The driver's own identity remains available; staff-only lists stay protected.
        self.assertEqual(self.driver.get('/api/v1/tf/portal').json()['username'],'787100')
        for url in ['/api/v1/admin/tf','/api/v1/admin/directory']:
            self.assertIn(self.other.get(url).status_code,(401,403))
        response=self.client.get('/api/v1/admin/tf')
        self.assertEqual(response.status_code,200)
        self.assertIn('787100',response.text)
