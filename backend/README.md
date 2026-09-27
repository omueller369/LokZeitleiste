# LokZeitleiste Backend (Python / MySQL)

FastAPI stellt die Admin-Oberfläche unter `/admin` und die API für die Android-App bereit. MySQL speichert Admins, Tf-Stammdaten, Sitzungen und Monatsdaten.

## Zunächst lokal: Apache und MySQL

Die folgende Konfiguration ist für Debian mit nativem Apache 2.4 gedacht. Python-API und **MySQL 8.4** laufen lokal in Containern. So bleibt es tatsächlich MySQL: Debians Paket `default-mysql-server` kann stattdessen MariaDB installieren. Für lokale HTTP-Tests keine echten Tf-Daten verwenden.

1. Apache installieren: `sudo apt update && sudo apt install apache2`. Docker Engine samt Compose-Plugin nach der [offiziellen Debian-Anleitung](https://docs.docker.com/engine/install/debian/) installieren. Vorhandene Docker-Pakete und die Debian-Version dort abgleichen.
2. Im Ordner `backend` die Datei `.env.example` als `.env` kopieren. `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD` und `DATABASE_URL` auf eigene Werte setzen. Das Passwort innerhalb der Datenbank-URL muss bei Sonderzeichen URL-kodiert werden. Die Datei ist vom Git-Commit ausgeschlossen.
3. MySQL und die Python-API starten:

   ```bash
   docker compose -f compose.yaml -f compose.local.yaml up -d --build
   docker compose -f compose.yaml -f compose.local.yaml ps
   docker compose -f compose.yaml -f compose.local.yaml exec api python -m lokzeitleiste.init_db --create-admin
   ```

4. Apache als lokalen Reverse-Proxy aktivieren:

   ```bash
   sudo a2enmod proxy proxy_http
   sudo cp apache/lokzeitleiste-local.conf /etc/apache2/sites-available/
   sudo a2ensite lokzeitleiste-local.conf
   sudo apache2ctl configtest
   sudo systemctl reload apache2
   curl http://localhost:8080/health
   ```

   Die `Listen 127.0.0.1:8080`-Zeile darf nicht doppelt existieren. Anschließend `http://localhost:8080/admin` öffnen. Das lokale Compose-Override setzt `COOKIE_SECURE=false` ausschließlich für HTTP auf dem Entwicklungsrechner.
5. In Android Studio einen **Debug-Build im Emulator** mit `-PlokzeitleisteApiBaseUrl=http://10.0.2.2:8080` konfigurieren. `10.0.2.2` verweist im Emulator auf den Entwicklungsrechner. Nur diese Debug-Adresse darf in der App HTTP verwenden. Tf werden im Admin-Bereich angelegt; danach kann die App Monatsdaten senden.

Dieser Server ist über die Loopback-Adresse nur vom Entwicklungsrechner beziehungsweise dessen Android-Emulator erreichbar. Ein physisches Tablet erreicht `localhost` des Rechners nicht. Dafür folgt später ein erreichbarer Server mit HTTPS. **Lokales HTTP ist ausschließlich für Entwicklungsdaten gedacht.**

## Spätere Serverumgebung

Die Datei `compose.yaml` enthält alternativ einen MySQL-Container und den Python-API-Container. Für einen erreichbaren Server wird ein HTTPS-Reverse-Proxy benötigt. Dann `COOKIE_SECURE=true`, `PUBLIC_ORIGIN` auf den exakten HTTPS-Ursprung und im Android-Build eine HTTPS-API-Adresse setzen. Die App lässt HTTP nur im Debug-Emulator an `10.0.2.2:8080` zu.

## Funktionen und Grenzen

Admins melden sich über ein HttpOnly-Cookie an, legen Tf mit Name, Vorname, Personalnummer, monatlichen Sollstunden, Urlaubstagen, Geburtsdatum und BahnCard 50 oder 100 an und können deren Monate einsehen. Die App meldet Tf über die API an und sendet den ausgewählten Monat. Einträge werden mit ihrer `client_id` bei erneutem Senden aktualisiert und sind dem angemeldeten Tf zugeordnet. Passwortprüfwerte verwenden PBKDF2-HMAC-SHA256 und zufälligen Salt. App-Tokens sind mit Android Keystore geschützt und verfallen serverseitig nach 365 Tagen.

Lokal gelöschte Einträge bleiben derzeit auf dem Server; Serverdaten werden noch nicht in die App geladen. Ein gleichzeitiger Betrieb auf mehreren Geräten ist nicht vorgesehen. Es gibt noch keine Passwortzurücksetzung, Dienstplanungsschnittstelle, Ausbleibe-Berechnung oder Kopplung der LokZeit-Standzeiten mit dem Monatsdatensatz. Vor späteren Schemaänderungen wird ein Migrationstool benötigt.

API-Tests: `pip install -r requirements-dev.txt` und `python -m unittest discover -s tests` im Backend-Ordner. Die Tests verwenden SQLite als isolierte Testdatenbank. Der reguläre Betrieb verlangt MySQL.
