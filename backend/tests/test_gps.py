import unittest
from uuid import uuid4
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from lokzeitleiste.main import app
from lokzeitleiste.gps_analysis import analyse,candidates
from lokzeitleiste.models import TrainGpsRecording,AccountPolicy
from test_stations import StationDirectoryTest

BASE=1792627200000

def points(seconds=305,speed=0):
    return [dict(t=BASE+i*1000,lat=52,lon=13,accuracy=5,speed=speed) for i in range(0,seconds+1,5)]

class AnalysisTest(unittest.TestCase):
    def test_strict_thresholds_and_endpoints(self):
        self.assertEqual([r['kind'] for r in analyse(points(300))['rows']],['Start','Ende'])
        result=analyse(points());self.assertEqual([r['kind'] for r in result['rows']],['Start','Halt','Ende'])
        self.assertEqual(result['rows'][1]['end']-result['rows'][1]['start'],305000)
        self.assertEqual(len(analyse(points(speed=3/3.6))['rows']),2)
        self.assertEqual(len(analyse(points(speed=2.99/3.6))['rows']),3)

    def test_gaps_and_accuracy_never_count_as_stops(self):
        data=points();data[31:]=[{**p,'t':p['t']+60000} for p in data[31:]]
        result=analyse(data);self.assertEqual(len(result['rows']),2);self.assertEqual(len(result['gaps']),1)
        data=points();data[30]['accuracy']=51
        self.assertEqual(len(analyse(data)['rows']),2)
        self.assertEqual(analyse([{**p,'accuracy':100} for p in data])['rows'],[])
        self.assertEqual(len(analyse([{**p,'accuracy':50} for p in points()])['rows']),3)

    def test_missing_speed_and_direction(self):
        self.assertEqual(len(analyse(points(310,speed=None))['rows']),3)
        moving=[{**p,'lon':13+i*.001,'speed':None} for i,p in enumerate(points())]
        result=analyse(moving);self.assertEqual(len(result['rows']),2)
        self.assertAlmostEqual(result['rows'][0]['direction'],90,delta=1)
        row=dict(lat=52,lon=13,direction=90)
        nearby=[dict(code='E',name='Ahead',lat=52,lon=13.01),dict(code='W',name='Behind',lat=52,lon=12.99),dict(code='F',name='Far',lat=52,lon=14)]
        self.assertEqual([r['code'] for r in candidates(row,nearby)],['E'])
        self.assertEqual(len(candidates({**row,'direction':None},nearby)),2)

class RecordingTest(unittest.TestCase):
    setUp=StationDirectoryTest.setUp
    tearDown=StationDirectoryTest.tearDown
    def path(self):return '/api/v1/tf/gps/'+str(uuid4())
    def save(self,path=None,**changes):
        path=path or self.path();data=dict(train_number='ABC123',points=points(),ended=True,expected_revision=0);data.update(changes)
        result=self.driver.put(path,json=data);return path,result

    def test_private_roundtrip_revision_and_delete(self):
        path,response=self.save();self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['revision'],1);self.assertEqual(len(response.json()['analysis']['rows']),3)
        self.assertIn('no-store',response.headers['cache-control'])
        self.assertEqual(self.driver.get(path).json()['points'],points())
        self.assertEqual(self.save(path)[1].status_code,409)
        self.assertEqual(self.save(path,expected_revision=1)[1].json()['revision'],2)
        self.assertEqual(self.client.get(path).status_code,403)
        self.create_tf('787200','GPS-OTHER')
        other=TestClient(app,base_url='https://testserver');self.staff_clients.append(other)
        other.post('/api/v1/account/login',json={'username':'787200','password':'tf-secret-12345'})
        for response in [other.get(path),other.delete(path),other.post(path+'/stations')]:self.assertEqual(response.status_code,404)
        self.assertEqual(self.driver.delete(path).status_code,200);self.assertEqual(self.driver.get(path).status_code,404)

    def test_validation_and_login_gates(self):
        for changes in [dict(train_number='a'*13),dict(points=[]),dict(points=list(reversed(points()))),dict(points=[{**points()[0],'lat':91}]),dict(points=[{**points()[0],'speed':-1}]),dict(points=[points()[0],{**points()[0],'t':BASE+49*3600000}])]:
            self.assertEqual(self.save(**changes)[1].status_code,422)
        path=self.path()
        with Session(self.engine) as db:db.get(AccountPolicy,self.tf).must_change_password=True;db.commit()
        self.assertEqual(self.driver.get(path).status_code,403)
        self.driver.cookies.clear();self.assertEqual(self.driver.get(path).status_code,401)

    def test_osm_cache_canonical_ds100_and_confirmed_selection(self):
        path,response=self.save();self.assertEqual(response.status_code,200,response.text)
        elements=[dict(lat=52,lon=13,tags={'railway:ref':'BBB','name':'Untrusted external name'}),dict(lat=52,lon=13,tags={'railway:ref':'NOTKNOWN'})]
        with patch('lokzeitleiste.gps.osm_query',return_value=elements) as query:
            result=self.driver.post(path+'/stations');self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(result.json()['analysis']['rows'][0]['candidates'][0]['name'],'Berlin Beispiel')
            self.driver.post(path+'/stations');self.assertEqual(query.call_count,1)
        selected=self.driver.put(path+'/stations',json={'expected_revision':1,'stations':{'start':'BBB'}})
        self.assertEqual(selected.status_code,200,selected.text);self.assertEqual(selected.json()['revision'],2)
        self.assertEqual(selected.json()['analysis']['rows'][0]['station']['code'],'BBB')
        self.assertEqual(self.driver.put(path+'/stations',json={'expected_revision':2,'stations':{'bad':'BBB'}}).status_code,422)
        self.assertEqual(self.driver.put(path+'/stations',json={'expected_revision':2,'stations':{'start':'UNKNOWN'}}).status_code,422)
        _,changed=self.save(path,expected_revision=2,points=points(310));self.assertIsNone(changed.json()['analysis']['rows'][0]['station'])

    def test_reset_deletes_private_recordings(self):
        from lokzeitleiste.accounts.seed_demo_tf import delete_tf_records
        self.save()
        with Session(self.engine) as db:
            self.assertEqual(db.query(TrainGpsRecording).count(),1)
            delete_tf_records(db);db.commit();self.assertEqual(db.query(TrainGpsRecording).count(),0)

    def test_stop_reasons_validation_roundtrip_and_legacy_update(self):
        from lokzeitleiste.work_reports.schemas import REASONS
        path,response=self.save();self.assertEqual(response.status_code,200)
        revision=1
        for reason in REASONS:
            data={'expected_revision':revision,'stations':{},'reasons':{'s0':{'reason':reason,'detail':'Warten auf Ersatzlok' if reason=='sonstiges' else 'ignored'}}}
            result=self.driver.put(path+'/stations',json=data);self.assertEqual(result.status_code,200,result.text)
            revision+=1;expected={'reason':reason,'detail':'Warten auf Ersatzlok' if reason=='sonstiges' else ''}
            self.assertEqual(result.json()['analysis']['rows'][1]['reason'],expected)
            self.assertEqual(self.driver.get(path).json()['reasons']['s0'],expected)
        for reasons in [{'no-row':{'reason':'V1'}},{'s0':{'reason':'invented'}},{'s0':{'reason':'sonstiges'}},{'s0':{'reason':'sonstiges','detail':'x'*257}}]:
            self.assertEqual(self.driver.put(path+'/stations',json={'expected_revision':revision,'stations':{},'reasons':reasons}).status_code,422)
        self.assertEqual(self.driver.put(path+'/stations',json={'expected_revision':1,'stations':{},'reasons':{}}).status_code,409)
        legacy=self.driver.put(path+'/stations',json={'expected_revision':revision,'stations':{}})
        self.assertEqual(legacy.json()['reasons']['s0']['reason'],'sonstiges');revision+=1
        same=self.save(path,expected_revision=revision)[1];self.assertEqual(same.json()['reasons']['s0']['reason'],'sonstiges');revision+=1
        changed=self.save(path,expected_revision=revision,points=points(310))[1];self.assertEqual(changed.json()['reasons'],{})
