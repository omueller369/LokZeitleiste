# LokZeitleiste Backend (Python / MySQL)

FastAPI stellt die Admin-Oberfläche unter `/admin` und die API für die Android-App bereit. MySQL speichert Admins, Tf-Stammdaten, Sitzungen und Monatsdaten.

## Zunächst lokal: Apache und MySQL

Die folgende Konfiguration ist für einen Entwicklungsrechner mit Apache 2.4, MySQL 8 und Python 3.12 gedacht. Es werden keine echten Tf-Daten für HTTP-Tests verwendet.

1. MySQL lokal installieren und eine Datenbank mit eigenem Passwort anlegen. In einer administrativen MySQL-Sitzung:

   ```sql
   CREATE DATABASE lokzeitleiste CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'lokzeitleiste'@'127.0.0.1' IDENTIFIED BY 'EIGENES_LANGES_PASSWORT';
   GRANT ALL PRIVILEGES ON lokzeitleiste.* TO 'lokzeitleiste'@'127.0.0.1';
   ```

2. Im Ordner `backend` eine Python-Umgebung anlegen, `pip install -r requirements.txt` ausführen und `.env.local.example` als `.env.local` mit eigener `DATABASE_URL` kopieren. Sonderzeichen im Passwort innerhalb der URL kodieren. Diese Datei niemals committen.
3. Die Variablen aus `.env.local` in der lokalen Shell setzen, beispielsweise mit `set -a; . ./.env.local; set +a` unter Bash. Danach `python -m lokzeitleiste.init_db --create-admin` ausführen; Benutzername und Passwort werden interaktiv abgefragt. Den Python-Server mit `uvicorn lokzeitleiste.main:app --host 127.0.0.1 --port 8000` starten.
4. Apache-Module `proxy` und `proxy_http` aktivieren und [apache/lokzeitleiste-local.conf](apache/lokzeitleiste-local.conf) als lokale VirtualHost-Konfiguration einbinden. Die `Listen`-Zeile darf nicht doppelt existieren. Konfiguration mit `apachectl configtest` prüfen und Apache neu laden. Danach `http://localhost:8080/health` und `http://localhost:8080/admin` aufrufen.
5. In Android Studio einen **Debug-Build im Emulator** mit `-PlokzeitleisteApiBaseUrl=http://10.0.2.2:8080` konfigurieren. `10.0.2.2` verweist im Emulator auf den Entwicklungsrechner. Nur diese Debug-Adresse darf in der App HTTP verwenden. Tf werden im Admin-Bereich angelegt; danach kann die App Monatsdaten senden.

Die konkreten Installations- und Dienstbefehle für Apache und MySQL hängen vom Betriebssystem ab. Dieser Server ist über die Loopback-Adresse nur vom Entwicklungsrechner beziehungsweise dessen Android-Emulator erreichbar. Ein physisches Tablet erreicht `localhost` des Rechners nicht. Dafür folgt später ein erreichbarer Server mit HTTPS. **Lokales HTTP ist ausschließlich für Entwicklungsdaten gedacht.**

## Spätere Serverumgebung

Die Datei `compose.yaml` enthält alternativ einen MySQL-Container und den Python-API-Container. Für einen erreichbaren Server wird ein HTTPS-Reverse-Proxy benötigt. Dann `COOKIE_SECURE=true`, `PUBLIC_ORIGIN` auf den exakten HTTPS-Ursprung und im Android-Build eine HTTPS-API-Adresse setzen. Die App lässt HTTP nur im Debug-Emulator an `10.0.2.2:8080` zu.

## Funktionen und Grenzen

Admins melden sich über ein HttpOnly-Cookie an, legen Tf mit Name, Vorname, Personalnummer, monatlichen Sollstunden, Urlaubstagen, Geburtsdatum und BahnCard 50 oder 100 an und können deren Monate einsehen. Die App meldet Tf über die API an und sendet den ausgewählten Monat. Einträge werden mit ihrer `client_id` bei erneutem Senden aktualisiert und sind dem angemeldeten Tf zugeordnet. Passwortprüfwerte verwenden PBKDF2-HMAC-SHA256 und zufälligen Salt. App-Tokens sind mit Android Keystore geschützt und verfallen serverseitig nach 365 Tagen.

Lokal gelöschte Einträge bleiben derzeit auf dem Server; Serverdaten werden noch nicht in die App geladen. Ein gleichzeitiger Betrieb auf mehreren Geräten ist nicht vorgesehen. Es gibt noch keine Passwortzurücksetzung, Dienstplanungsschnittstelle, Ausbleibe-Berechnung oder Kopplung der LokZeit-Standzeiten mit dem Monatsdatensatz. Vor späteren Schemaänderungen wird ein Migrationstool benötigt.

API-Tests: `pip install -r requirements-dev.txt` und `python -m unittest discover -s tests` im Backend-Ordner. Die Tests verwenden SQLite als isolierte Testdatenbank. Der reguläre Betrieb verlangt MySQL.
