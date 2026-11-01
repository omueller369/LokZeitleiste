import unittest
import json
from pathlib import Path
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
        self.assertEqual([r['kind'] for r in analyse(points(235))['rows']],['Start','Ende'])
        result=analyse(points());self.assertEqual([r['kind'] for r in result['rows']],['Start','Halt','Ende'])
        self.assertEqual(result['rows'][1]['end']-result['rows'][1]['start'],305000)
        self.assertEqual(len(analyse(points(speed=3/3.6))['rows']),2)
        self.assertEqual(len(analyse(points(speed=2.99/3.6))['rows']),3)

        self.assertEqual(len(analyse(points(240))['rows']),3)

    def test_rail_stop_fixtures_match_browser(self):
        cases=json.loads((Path(__file__).parent/'fixtures/gps-rail-stops.json').read_text())
        for case in cases:
            with self.subTest(case=case['name']):
                rows=analyse(case['points'],case['edits'])['rows']
                self.assertEqual([dict(start=row['start'],end=row['end']) for row in rows if row['kind']=='Halt'],case['expected'])

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
        nearby=[dict(code='E',name='Ahead',lat=52,lon=13.01),dict(code='W',name='Behind',lat=52,lon=12.995),dict(code='F',name='Far',lat=52,lon=14)]
        self.assertEqual([r['code'] for r in candidates(row,nearby)],['W'])
        self.assertEqual(len(candidates({**row,'direction':None},nearby)),1)

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
        elements=[dict(lat=52,lon=13,tags={'place':'town','name':'Berlin'}),dict(lat=52,lon=13,tags={'railway:ref':'NOTKNOWN','name':'Ignored railway site'})]
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

    def test_live_stop_edits_end_station_and_import_flag_survive_checkpoint(self):
        key='live-'+str(BASE)
        path,response=self.save(ended=False,end_station='BBB',stop_edits={key:{'station_input':'BBB · Berlin Beispiel','station':{'code':'BBB','name':'ignored'},'reason':'sonstiges','detail':'Warten auf Ablösung','end':BASE+305000,'manual_end':True,'imported':True}})
        self.assertEqual(response.status_code,200,response.text)
        value=response.json();self.assertEqual(value['points'],points())
        self.assertFalse(value['ended']);self.assertEqual(value['end_station'],'BBB')
        self.assertEqual(value['stations']['end']['name'],'Berlin Beispiel')
        self.assertEqual(value['stop_edits'][key]['station']['name'],'Berlin Beispiel')
        self.assertTrue(self.driver.get(path).json()['stop_edits'][key]['imported'])
        changed=self.save(path,expected_revision=1,points=points(310))[1]
        self.assertEqual(changed.status_code,200,changed.text)
        self.assertTrue(changed.json()['stop_edits'][key]['imported'])
        for edits in [{'bad-key':{}},{key:{'end':BASE}},{key:{'station':{'code':'unknown','name':'x'}}}]:
            self.assertEqual(self.save(path,expected_revision=2,points=points(310),stop_edits=edits)[1].status_code,422)
        self.assertEqual(self.save(path,expected_revision=2,end_station='UNKNOWN')[1].status_code,422)

    def test_four_minute_jitter_stop_and_existing_edits_roundtrip(self):
        data=points(240)
        # Movement/jitter inside the stop area must not split the interval.
        for i in range(5,len(data),5):data[i]={**data[i],'lat':52.0005,'speed':2}
        key='live-'+str(BASE)
        path,response=self.save(points=data,stop_edits={key:{'station_input':'BBB','reason':'V1'}})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['analysis']['rows'][1]['end'],BASE+240000)
        # Two previously edited halts remain separately addressable even inside 100m.
        edits={key:{'reason':'V1','imported':True},'live-'+str(BASE+300000):{'reason':'V2','station_input':'CCC'}}
        saved=self.save(path,expected_revision=1,points=points(600),stop_edits=edits)[1]
        self.assertEqual(saved.status_code,200,saved.text)
        self.assertEqual(len([r for r in saved.json()['analysis']['rows'] if r['kind']=='Halt']),2)
        self.assertTrue(saved.json()['stop_edits'][key]['imported'])
        changed=self.save(path,expected_revision=2,points=points(610))[1]
        self.assertEqual(changed.status_code,200,changed.text)
        self.assertEqual(changed.json()['stop_edits']['live-'+str(BASE+300000)]['station_input'],'CCC')

    def test_legacy_station_assignment_does_not_shift_to_new_shorter_stop(self):
        data=points(240)+[dict(points()[0],t=BASE+245000,lat=52.002,speed=2)]
        data += [dict(points()[0],t=BASE+s*1000,lat=52.004) for s in range(250,556,5)]
        path,response=self.save(points=data)
        self.assertEqual(response.status_code,200,response.text)
        with Session(self.engine) as db:
            row=db.query(TrainGpsRecording).filter_by(journey_id=path.rsplit('/',1)[1]).one()
            payload=json.loads(row.payload_json);payload.pop('detection_version',None);payload.pop('stop_edits',None)
            payload.update(stations={'s0':dict(code='CCC',name='Legacy location')},reasons={'s0':dict(reason='V1',detail='')},selection=['s0'])
            row.payload_json=json.dumps(payload);db.commit()
        result=self.driver.get(path).json()
        stops=[r for r in result['analysis']['rows'] if r['kind']=='Halt']
        self.assertEqual(len(stops),2)
        self.assertIsNone(stops[0]['station'])
        self.assertEqual(stops[1]['station']['code'],'CCC')
        self.assertEqual(result['selection'],['s1'])
        self.assertEqual(result['stop_edits']['live-'+str(BASE+250000)]['station']['code'],'CCC')
        saved=self.save(path,expected_revision=1,points=data)[1]
        self.assertEqual(saved.status_code,200,saved.text)
        self.assertEqual(saved.json()['stations']['s1']['code'],'CCC')

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
            revision+=1;expected={'label':reason,'reason':reason,'detail':'Warten auf Ersatzlok' if reason=='sonstiges' else ''}
            self.assertEqual(result.json()['analysis']['rows'][1]['reason'],expected)
            self.assertEqual(self.driver.get(path).json()['reasons']['s0'],expected)
        for reasons in [{'no-row':{'reason':'V1'}},{'s0':{'reason':'invented'}},{'s0':{'reason':'sonstiges'}},{'s0':{'reason':'sonstiges','detail':'x'*257}}]:
            self.assertEqual(self.driver.put(path+'/stations',json={'expected_revision':revision,'stations':{},'reasons':reasons}).status_code,422)
        self.assertEqual(self.driver.put(path+'/stations',json={'expected_revision':1,'stations':{},'reasons':{}}).status_code,409)
        legacy=self.driver.put(path+'/stations',json={'expected_revision':revision,'stations':{}})
        self.assertEqual(legacy.json()['reasons']['s0']['reason'],'sonstiges');revision+=1
        same=self.save(path,expected_revision=revision)[1];self.assertEqual(same.json()['reasons']['s0']['reason'],'sonstiges');revision+=1
        changed=self.save(path,expected_revision=revision,points=points(310))[1];self.assertEqual(changed.json()['reasons'],{})

    def test_nearby_covers_5km_and_start_selection_survives_save(self):
        elements=[dict(lat=52,lon=13.065,tags={'place':'town','name':'Berlin'})]
        with patch('lokzeitleiste.gps.osm_query',return_value=elements) as query:
            response=self.driver.get('/api/v1/tf/gps/nearby?lat=52&lon=13');self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['radius_m'],5000);self.assertEqual(response.json()['stations'][0]['code'],'BBB')
            self.assertGreater(response.json()['stations'][0]['distance_m'],4000);self.assertEqual(query.call_args.args[2],6500)
        path,response=self.save(start_station='BBB');self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['analysis']['rows'][0]['station']['code'],'BBB')
        self.assertEqual(self.save(path,expected_revision=1,start_station='BBB',points=points(310))[1].json()['analysis']['rows'][0]['station']['code'],'BBB')
        self.assertEqual(self.save(start_station='INVALID')[1].status_code,422)
        self.assertEqual(self.client.get('/api/v1/tf/gps/nearby?lat=52&lon=13').status_code,403)

    def test_stop_proposes_ds100_by_nearest_place_name_within_5km(self):
        path,response=self.save();elements=[dict(lat=52,lon=13.065,tags={'place':'town','name':'Berlin'})]
        with patch('lokzeitleiste.gps.osm_query',return_value=elements) as query:
            result=self.driver.post(path+'/stations');self.assertEqual(result.status_code,200,result.text)
            station=result.json()['analysis']['rows'][0]['candidates'][0]
            self.assertEqual(station['code'],'BBB');self.assertGreater(station['distance_m'],4000)
            self.assertEqual(query.call_args.args[2],6500)

    def test_unmatched_place_has_times_without_station_and_legacy_data_survives(self):
        path,response=self.save(start_station='BBB');self.assertEqual(response.status_code,200)
        data={'expected_revision':1,'stations':{'start':'BBB','s0':'CCC'},'reasons':{'s0':{'reason':'V1'}},'selection':['s0']}
        saved=self.driver.put(path+'/stations',json=data);self.assertEqual(saved.status_code,200,saved.text)
        elements=[dict(lat=52,lon=13,tags={'place':'village','name':'Unknown Village','railway:ref':'AAA'}),dict(lat=52,lon=13.01,tags={'place':'city','name':'Berlin'})]
        with patch('lokzeitleiste.gps.osm_query',return_value=elements):
            result=self.driver.post(path+'/stations');self.assertEqual(result.status_code,200,result.text)
            rows=result.json()['analysis']['rows'];self.assertTrue(all(r['candidates']==[] for r in rows))
            self.assertEqual(rows[1]['station']['code'],'CCC');self.assertEqual(rows[1]['end']-rows[1]['start'],305000)
        self.assertEqual(self.driver.get(path).json()['selection'],['s0'])
        unchanged=self.save(path,expected_revision=2,start_station='BBB')[1].json()
        self.assertEqual(unchanged['stations']['s0']['code'],'CCC');self.assertEqual(unchanged['reasons']['s0']['reason'],'V1');self.assertEqual(unchanged['selection'],['s0'])
        self.assertEqual(self.driver.put(path+'/stations',json={**data,'expected_revision':3,'selection':['not-a-row']}).status_code,422)

    def test_place_outside_radius_and_railway_reference_are_not_suggestions(self):
        path,_=self.save()
        elements=[dict(lat=52,lon=13.1,tags={'place':'town','name':'Berlin'}),dict(lat=52,lon=13,tags={'railway':'station','railway:ref':'BBB','name':'Berlin'})]
        with patch('lokzeitleiste.gps.osm_query',return_value=elements):
            response=self.driver.post(path+'/stations');self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['analysis']['rows'][1]['candidates'],[])

    def test_place_query_uses_names_and_not_railway_sites(self):
        import json,urllib.parse
        from lokzeitleiste import gps
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,*args):return json.dumps({'elements':[]}).encode()
        with patch.object(gps,'_last_query',0),patch('urllib.request.urlopen',return_value=Response()) as fetch:
            gps.osm_query(52,13,6500)
        query=urllib.parse.parse_qs(fetch.call_args.args[0].data.decode())['data'][0]
        self.assertIn('["place"',query);self.assertIn('["name"]',query);self.assertNotIn('["railway"',query)
