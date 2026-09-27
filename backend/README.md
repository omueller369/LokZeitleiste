# LokZeitleiste Backend (Python / MySQL)

## Aufbau

- FastAPI stellt Admin- und Tf-Schnittstellen bereit.
- SQLAlchemy verwaltet MySQL-Tabellen: Benutzer, Tf-Stammdaten, Sitzungen, Monate und Arbeitszeiteinträge.
- Admin-Oberfläche: `/admin`. Nur ein Admin kann Tf-Konten anlegen und ihre Monatsdaten einsehen.
- Tf-App: Anmeldung mit dem zugewiesenen Benutzernamen/Passwort, danach `POST /api/v1/me/months/{year}/{month}/entries`.
- Jeder Eintrag gehört zu genau einem Monat und einem Tf. Die `client_id` verhindert doppelte Einträge bei wiederholtem Senden.

## Start auf einem Webserver

1. `.env.example` als `.env` ablegen und sämtliche Beispielwerte ersetzen. Die Datenbank-URL muss das MySQL-Passwort gegebenenfalls URL-kodiert enthalten.
2. `docker compose up -d --build` im Backend-Ordner starten.
3. Einmalig mit `docker compose exec api python -m lokzeitleiste.init_db --create-admin` den ersten Admin interaktiv anlegen.
4. Einen HTTPS-Reverse-Proxy auf `127.0.0.1:8000` konfigurieren. `PUBLIC_ORIGIN` muss dessen exaktem HTTPS-Ursprung entsprechen. Admin-Cookies sind nur über HTTPS nutzbar.
5. `https://<server>/admin` öffnen und Tf-Konten anlegen. Das eingegebene Passwort dem jeweiligen Tf über einen geeigneten separaten Weg bereitstellen.
6. Android-Projekt mit `-PlokzeitleisteApiBaseUrl=https://<server>` bauen. Ohne konfigurierte HTTPS-Adresse verweigert die App den Versand und die Anmeldung.

Der Container veröffentlicht die API nur an localhost des Webservers. Datenbank und Passwörter gehören nicht ins Repository. `.env` wird ignoriert. Datenbankzugriff und HTTPS-Zertifikat müssen vor dem produktiven Betrieb eingerichtet werden.

Die API-Tests lassen sich mit `pip install -r requirements-dev.txt` und `python -m unittest discover -s tests` im Backend-Ordner ausführen. Sie verwenden eine isolierte SQLite-Datenbank; der Betrieb verwendet ausschließlich MySQL.

## Datenfluss und Grenzen

Die Android-App hält Einträge weiterhin lokal und sendet auf Knopfdruck den ausgewählten Monat. Einträge mit gleicher `client_id` werden serverseitig aktualisiert. Lokal gelöschte Einträge bleiben vorerst auf dem Server, da noch kein Abgleich von Löschungen implementiert ist. Serverdaten werden noch nicht automatisch in die App geladen; gleichzeitige Bearbeitung auf mehreren Geräten ist nicht vorgesehen. Ein Tf kann ausschließlich seine eigenen Monate lesen oder senden. Admins können Tf-Stammdaten und Monatsdaten lesen.

Sitzungstokens werden in der Datenbank nur als SHA-256-Prüfwert gespeichert und laufen nach 365 Tagen ab; nach Ablauf ist eine erneute Anmeldung nötig. Die Android-App verschlüsselt das Token mit einem Schlüssel aus Android Keystore. Passwörter werden mit PBKDF2-HMAC-SHA256 und zufälligem Salt gespeichert. Die Admin-Oberfläche nutzt ein HttpOnly/Secure/SameSite-Cookie.

Die Datenbanktabellen werden beim Start erstellt. Schemaänderungen und Datenbankmigrationen benötigen vor einem produktiven Ausbau ein Migrationstool. Es gibt noch keine Passwortzurücksetzung, keine zentrale Dienstplanung, keine Ausbleibe-Berechnung und keine Kopplung der LokZeit-Standzeiten mit dem Monatsdatensatz.
