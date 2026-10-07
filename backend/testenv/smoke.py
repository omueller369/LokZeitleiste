"""Realer API/MySQL/SMTP-Test über Apache; legt je Lauf einen fiktiven Tf an."""
import getpass
import http.cookiejar
import json
import secrets
import time
import urllib.request
import uuid

BASE = "http://localhost:8080"
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def request(path, data=None, token=None):
    headers = {"Origin": BASE}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + path, headers=headers,
                                 data=json.dumps(data).encode() if data is not None else None)
    with opener.open(req, timeout=30) as response:
        return json.load(response)


def main():
    request("/health")
    request("/api/v1/admin/login", {"username": input("Admin-Benutzername: "),
                                   "password": getpass.getpass("Admin-Passwort: ")})
    name = "test-" + secrets.token_hex(5)
    password = secrets.token_urlsafe(24)
    recipient = name + "@example.com"
    tf = request("/api/v1/admin/tf", {
        "username": name, "password": password, "first_name": "Test", "last_name": "Beispiel",
        "personnel_number": name, "target_hours_minutes": 9600, "vacation_days": 30,
        "birth_date": "1990-05-12", "bahncard": 50, "email": recipient, "federal_state": "BE"})
    token = request("/api/v1/tf/login", {"username": name, "password": password})["access_token"]
    def entry(kind, date, start="08:00", end="12:00", guest=0):
        return {"client_id": str(uuid.uuid4()), "kind": kind, "date": date,
                "start": start, "end": end, "pause": 0, "guest": guest}
    batch = {"entries": [entry("Zugfahrt", "2026-09-21", guest=120),
                         entry("Zugfahrt", "2026-09-22", end="18:00", guest=60),
                         entry("Urlaub", "2026-09-23"), entry("Krank", "2026-09-24")]}
    path = "/api/v1/me/months/2026/9/entries"
    first = request(path, batch, token)
    request(path, batch, token)
    if len(request(path, token=token)) != 4:
        raise RuntimeError("Erneute Übermittlung hat Einträge dupliziert")
    totals = request("/api/v1/me/months/2026/9/summary", token=token)["totals"]
    for key, expected in {"credited": 2040, "guest": 180, "topup": 240,
                          "vacation": 480, "sick": 480}.items():
        if totals[key] != expected:
            raise RuntimeError(f"{key}: {totals[key]} statt {expected}")
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        reports = request(f"/api/v1/admin/tf/{tf['id']}/reports")
        if len(reports) == 2 and all(r["status"] == "sent" for r in reports):
            break
        time.sleep(2)
    else:
        raise RuntimeError("SMTP-Versand nicht erfolgreich: " + json.dumps(reports))
    with urllib.request.urlopen("http://localhost:8025/api/v1/messages", timeout=10) as response:
        messages = json.load(response)
    if recipient not in json.dumps(messages):
        raise RuntimeError("Test-E-Mail nicht in Mailpit gefunden")
    print("OK: Apache, Admin/Tf-Login, MySQL-Daten, erneuter Upload, 34:00 h und SMTP geprüft.")
    print(f"PDF-Anhänge in Mailpit für {recipient} öffnen und prüfen.")
    print(f"Fiktiver Tf: {name}; zwei Versandaufträge; erster Auftrag #{first['report_dispatch_id']}.")
    print("Das zufällige Tf-Passwort wird nicht gespeichert; eigenen App-Test-Tf im Admin anlegen.")


if __name__ == "__main__":
    main()
