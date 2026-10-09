import unittest
from datetime import date
from uuid import uuid4
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from lokzeitleiste.db import Base, database_session
from lokzeitleiste.main import app
from lokzeitleiste.models import AccountPolicy, ReportDispatch, User
from lokzeitleiste.security import hash_password


class ApiFlowTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False},
                                    poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        def test_session():
            with Session(self.engine, expire_on_commit=False) as db:
                yield db
        app.dependency_overrides[database_session] = test_session
        self.engine_patch = patch("lokzeitleiste.reports.service.engine", return_value=self.engine)
        self.smtp_patch = patch.dict("os.environ", {"SMTP_HOST": "smtp.example.test", "SMTP_FROM": "test@example.test"})
        self.send_patch = patch("lokzeitleiste.reports.service.send_receipt")
        self.engine_patch.start()
        self.smtp_patch.start()
        self.send_mock = self.send_patch.start()
        with Session(self.engine) as db:
            db.add(User(username="admin", password_hash=hash_password("admin-secret-12345"), role="admin"))
            db.commit()
        self.client = TestClient(app, base_url="https://testserver")

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.send_patch.stop()
        self.smtp_patch.stop()
        self.engine_patch.stop()
        self.engine.dispose()

    def create_tf(self, username, personnel):
        result = self.client.post("/api/v1/admin/tf", json={
            "username": username, "password": "tf-secret-12345", "first_name": "Mira",
            "last_name": "Beispiel", "personnel_number": personnel,
            "target_hours_minutes": 9600, "vacation_days": 30,
            "birth_date": "1990-05-12", "bahncard": 50,
            "email": username + "@example.com", "federal_state": "BE",
        })
        # Fachliche Tests verwenden ein Konto nach abgeschlossenem Initialpasswortwechsel.
        if result.status_code == 201:
            with Session(self.engine) as db:
                db.get(AccountPolicy,result.json()['id']).must_change_password=False
                db.commit()
        return result

    def test_admin_creation_upload_idempotence_and_owner_isolation(self):
        self.assertEqual(self.client.post("/api/v1/admin/login",
            json={"username": "admin", "password": "admin-secret-12345"}).status_code, 200)
        first = self.create_tf("tf-one", "P-001")
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(self.create_tf("tf-two", "P-002").status_code, 201)
        self.assertEqual(self.create_tf("tf-three", "P-001").status_code, 409)
        self.assertEqual(len(self.client.get("/api/v1/admin/tf").json()), 2)
        token_one = self.client.post("/api/v1/tf/login",
            json={"username": "tf-one", "password": "tf-secret-12345"}).json()["access_token"]
        token_two = self.client.post("/api/v1/tf/login",
            json={"username": "tf-two", "password": "tf-secret-12345"}).json()["access_token"]
        headers_one = {"Authorization": "Bearer " + token_one}
        headers_two = {"Authorization": "Bearer " + token_two}
        item = {"client_id": str(uuid4()), "kind": "Bereitschaft", "date": "2026-09-22",
                "start": "22:00", "end": "06:00", "pause": 0, "guest": 0, "note": "",
                "away": True, "accommodation": "Hotel", "hotel_name": "Bahnhof"}
        path = "/api/v1/me/months/2026/9/entries"
        self.assertEqual(self.client.post(path, json={"entries": [item]}, headers=headers_one).status_code, 200)
        item["hotel_name"] = "Neues Hotel"
        self.assertEqual(self.client.post(path, json={"entries": [item]}, headers=headers_one).status_code, 200)
        own = self.client.get(path, headers=headers_one).json()
        self.assertEqual(len(own), 1)
        self.assertEqual(own[0]["hotel_name"], "Neues Hotel")
        self.assertEqual(self.client.get(path, headers=headers_two).json(), [])
        self.assertEqual(self.client.get(f"/api/v1/admin/tf/{first.json()['id']}/months").json()[0]["entry_count"], 1)
        invalid = dict(item, kind="Rufbereitschaft", start="07:00", end="10:00")
        self.assertEqual(self.client.post(path, json={"entries": [invalid]}, headers=headers_one).status_code, 422)
        self.assertEqual(len(self.client.get(path, headers=headers_one).json()), 1)
        self.assertEqual(self.send_mock.call_count, 2)
        self.assertTrue(self.send_mock.call_args.kwargs["pdf_data"].startswith(b"%PDF"))
        with Session(self.engine) as db:
            self.assertEqual([r.status for r in db.query(ReportDispatch).all()], ["sent", "sent"])
        summary = self.client.get("/api/v1/me/months/2026/9/summary", headers=headers_one)
        self.assertEqual(summary.status_code, 200, summary.text)
        self.assertEqual(summary.json()["totals"]["credited"], 960)
        self.assertEqual(summary.json()["totals"]["night"], 480)
        self.assertEqual(self.client.get("/api/v1/me/months/2026/9/summary", headers=headers_two).json()["days"], [])

    def test_unauthed_requests_are_rejected(self):
        self.assertEqual(self.client.get("/api/v1/admin/tf").status_code, 401)
        self.assertEqual(self.client.post("/api/v1/me/months/2026/9/entries",
            json={"entries": []}).status_code, 401)

    def test_month_topup_uses_guest_once_and_absence_once_per_day(self):
        self.client.post("/api/v1/admin/login", json={"username": "admin", "password": "admin-secret-12345"})
        tf_id = self.create_tf("tf-example", "P-003").json()["id"]
        token = self.client.post("/api/v1/tf/login", json={"username": "tf-example", "password": "tf-secret-12345"}).json()["access_token"]
        headers = {"Authorization": "Bearer " + token}
        def entry(kind, day, start="08:00", end="12:00", guest=0):
            return {"client_id": str(uuid4()), "kind": kind, "date": day,
                    "start": start, "end": end, "pause": 0, "guest": guest}
        items = [entry("Zugfahrt", "2026-09-21", guest=120),
                 entry("Zugfahrt", "2026-09-22", end="18:00", guest=60),
                 entry("Urlaub", "2026-09-23"), entry("Krank", "2026-09-24")]
        response = self.client.post("/api/v1/me/months/2026/9/entries", json={"entries": items}, headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        report = self.client.get(f"/api/v1/admin/tf/{tf_id}/months/2026/9/summary").json()
        self.assertEqual(report["totals"]["work_without_guest"], 660)
        self.assertEqual(report["totals"]["guest"], 180)
        self.assertEqual(report["totals"]["guest_used_for_target"], 120)
        self.assertEqual(report["totals"]["topup"], 240)
        self.assertEqual(report["totals"]["credited"], 2040)
        self.assertEqual((report["vacation_days"], report["sick_days"]), (1, 1))
        self.assertEqual(len(report["days"]), 4)

    def test_upload_needs_mail_settings_and_failure_remains_retryable(self):
        self.client.post("/api/v1/admin/login", json={"username": "admin", "password": "admin-secret-12345"})
        tf_id = self.create_tf("tf-missing", "P-004").json()["id"]
        token = self.client.post("/api/v1/tf/login", json={"username": "tf-missing", "password": "tf-secret-12345"}).json()["access_token"]
        headers = {"Authorization": "Bearer " + token}
        item = {"client_id": str(uuid4()), "kind": "Zugfahrt", "date": "2026-09-10",
                "start": "08:00", "end": "11:00", "pause": 0, "guest": 0}
        with patch.dict("os.environ", {"SMTP_HOST": ""}):
            self.assertEqual(self.client.post("/api/v1/me/months/2026/9/entries", json={"entries": [item]}, headers=headers).status_code, 503)
        self.assertEqual(self.client.get("/api/v1/me/months/2026/9/entries", headers=headers).json(), [])
        self.send_mock.side_effect = OSError("SMTP vorübergehend nicht erreichbar")
        self.assertEqual(self.client.post("/api/v1/me/months/2026/9/entries", json={"entries": [item]}, headers=headers).status_code, 200)
        status = self.client.get(f"/api/v1/admin/tf/{tf_id}/reports").json()
        self.assertEqual(status[0]["status"], "failed")
        self.assertEqual(status[0]["attempts"], 1)


if __name__ == "__main__":
    unittest.main()
