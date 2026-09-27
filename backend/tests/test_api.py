import unittest
from datetime import date
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from lokzeitleiste.db import Base, database_session
from lokzeitleiste.main import app
from lokzeitleiste.models import User
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
        with Session(self.engine) as db:
            db.add(User(username="admin", password_hash=hash_password("admin-secret-12345"), role="admin"))
            db.commit()
        self.client = TestClient(app, base_url="https://testserver")

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.engine.dispose()

    def create_tf(self, username, personnel):
        return self.client.post("/api/v1/admin/tf", json={
            "username": username, "password": "tf-secret-12345", "first_name": "Mira",
            "last_name": "Beispiel", "personnel_number": personnel,
            "target_hours_minutes": 9600, "vacation_days": 30,
            "birth_date": "1990-05-12", "bahncard": 50,
        })

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

    def test_unauthed_requests_are_rejected(self):
        self.assertEqual(self.client.get("/api/v1/admin/tf").status_code, 401)
        self.assertEqual(self.client.post("/api/v1/me/months/2026/9/entries",
            json={"entries": []}).status_code, 401)


if __name__ == "__main__":
    unittest.main()
