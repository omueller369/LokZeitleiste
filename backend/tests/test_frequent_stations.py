import json,unittest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import test_work_reports
from lokzeitleiste.main import app
from lokzeitleiste.models import DutyReport,RailwayStation

PATH='/api/v1/tf/work-reports/stations/frequent'
class FrequentStationsTest(unittest.TestCase):
    setUp=test_work_reports.WorkReportsTest.setUp
    tearDown=test_work_reports.WorkReportsTest.tearDown
    payload=test_work_reports.WorkReportsTest.payload
    create=test_work_reports.WorkReportsTest.create

    def test_empty_and_private_history(self):
        self.assertEqual(self.driver.get(PATH).json(),[])
        self.create();self.create_tf('787200','FREQUENT-OTHER')
        other=TestClient(app,base_url='https://testserver');self.staff_clients.append(other)
        other.post('/api/v1/account/login',json={'username':'787200','password':'tf-secret-12345'})
        self.assertEqual(other.get(PATH).json(),[])
        self.assertEqual(self.client.get(PATH).status_code,403)
        self.driver.cookies.clear();self.assertEqual(self.driver.get(PATH).status_code,401)

    def test_ranking_six_limit_names_and_legacy_unknown_codes(self):
        report=self.create()
        with Session(self.engine) as db:
            db.add_all([RailwayStation(code='X'+str(i),name='Ort '+str(i)) for i in range(8)])
            row=db.get(DutyReport,report['id']);payload=json.loads(row.payload_json)
            payload['trips']=[dict(start_station='X'+str(i),end_station='X'+str(i)) for i in range(8) for repeat in range(i+1)]
            payload['train_journeys']=[dict(start_station='X0',end_station='GONE',events=[dict(station='X0')]*20+[dict(station='')])]
            row.payload_json=json.dumps(payload);db.commit()
        response=self.driver.get(PATH);self.assertEqual(response.status_code,200,response.text)
        rows=response.json();self.assertEqual([r['code'] for r in rows],['X0','X7','X6','X5','X4','X3'])
        self.assertEqual(rows[0],dict(code='X0',name='Ort 0',count=23))
        self.assertIn('no-store',response.headers['cache-control'])

    def test_retries_do_not_inflate_and_ties_sort_by_ds100(self):
        data=self.payload();self.create(data);self.create(data)
        rows=self.driver.get(PATH).json();self.assertEqual([(r['code'],r['count']) for r in rows],[('BHF',1),('LL',1)])
        with Session(self.engine) as db:db.get(RailwayStation,'BHF').name='Neuer Bahnhofsname';db.commit()
        self.assertEqual(self.driver.get(PATH).json()[0]['name'],'Neuer Bahnhofsname')
