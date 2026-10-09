# LokZeitleiste Backend (Python / MySQL)

FastAPI stellt die Admin-Oberfläche unter `/admin` und die API für die Android-App bereit. MySQL speichert Admins, Tf-Stammdaten, Sitzungen und Monatsdaten.

## Vollständige Testumgebung auf Ubuntu Server 26.04.1 LTS

Die [automatische Setup-Routine](../setup/README.md) übernimmt Abhängigkeitsprüfung, Paketinstallation, Containerstart und Apache-Konfiguration: im Repository-Hauptordner `sudo bash setup/install-ubuntu.sh`.

Für Tests einschließlich PDF-E-Mail steht ein separater Stack mit MySQL und Mailpit bereit. Die [Einrichtungsanleitung](testenv/README.md) beschreibt Vorbereitung, Apache, SSH-Tunnel, App-Verbindung, durchgängigen Test und Sicherung. Start: `bash testenv/prepare.sh` und `sudo bash testenv/control.sh start`.

## Bestehende manuelle Debian-Einrichtung (optional)

Die folgende Konfiguration ist für Debian mit nativem Apache 2.4 gedacht. Python-API und **MySQL 8.4** laufen lokal in Containern. So bleibt es tatsächlich MySQL: Debians Paket `default-mysql-server` kann stattdessen MariaDB installieren. Für lokale HTTP-Tests keine echten Tf-Daten verwenden.

1. Apache installieren: `sudo apt update && sudo apt install apache2`. Docker Engine samt Compose-Plugin nach der [offiziellen Debian-Anleitung](https://docs.docker.com/engine/install/debian/) installieren. Vorhandene Docker-Pakete und die Debian-Version dort abgleichen.
2. Im Ordner `backend` die Datei `.env.example` als `.env` kopieren. `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD` und `DATABASE_URL` auf eigene Werte setzen. Das Passwort innerhalb der Datenbank-URL muss bei Sonderzeichen URL-kodiert werden. Die Datei ist vom Git-Commit ausgeschlossen.
3. Bei einer bereits vorhandenen MySQL-Datenbank vor dem Neustart eine Sicherung erstellen und `migrations/0001_daily_receipt.sql` einmalig in der Datenbank ausführen. Beispiel bei laufendem Datenbankcontainer: `docker compose -f compose.yaml -f compose.local.yaml exec -T db sh -c 'exec mysql -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' < migrations/0001_daily_receipt.sql`. Bei frischer Installation ist das nicht erforderlich. In `.env` außerdem `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY` (`ssl` oder `starttls`), `SMTP_FROM` und gegebenenfalls `SMTP_USERNAME` und `SMTP_PASSWORD` für ein TLS-geschütztes SMTP-Postfach setzen. Ohne diese Konfiguration nimmt die API keine neuen nichtleeren Übermittlungen an (HTTP 503). Danach MySQL, Python-API und Versanddienst starten:

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

## Arbeitszeitplanung

Admins können pro Tf einen bearbeitbaren Arbeits-, Urlaubs- und Ruhetagsplan anlegen, XLSX-Dateien mit Importvorschau übernehmen und farbige Monats-/Jahres-PDFs erstellen. Arbeitstage und Urlaub zählen im Plan mit jeweils acht Stunden, Ruhetage mit null; nur ausdrücklich geplante Tage werden berechnet. Regeln, Installation und Excel-Format stehen in der [Modulanleitung](lokzeitleiste/planning/README.md).

## Funktionen und Grenzen

Admins melden sich über ein HttpOnly-Cookie an, legen Tf mit Name, Vorname, Personalnummer, monatlichen Sollstunden, Urlaubstagen, Geburtsdatum, BahnCard 50 oder 100, E-Mail und Bundesland an und können deren Monate einsehen. Für bereits angelegte Tf sind E-Mail und Bundesland in der Admin-Tabelle nachzutragen. Die App meldet Tf über die API an und sendet den ausgewählten Monat. Einträge werden mit ihrer `client_id` bei erneutem Senden aktualisiert und sind dem angemeldeten Tf zugeordnet. Passwortprüfwerte verwenden PBKDF2-HMAC-SHA256 und zufälligen Salt. App-Tokens sind mit Android Keystore geschützt und verfallen serverseitig nach 365 Tagen.

### Tagesbeleg und E-Mail

Jede nichtleere Übermittlung speichert zugleich einen Versandauftrag mit einer tabellarischen PDF-Eingangsbestätigung. Ein Anhang enthält alle in **dieser Übermittlung** empfangenen Tage, mit Zeilen und Tagessummen für Arbeit, Gastfahrt, Sonntag, Feiertag im Bundesland des Tf und Nacht von 22 bis 06 Uhr. Der Server versucht den Versand unmittelbar nach dem Speichern; `mailer` wiederholt fehlgeschlagene Versuche alle 30 Sekunden, höchstens fünfmal. Der API-Rückgabewert `email_status=queued` bestätigt den Versandauftrag, nicht die tatsächliche Zustellung. Admins sehen den Status unter „PDF-Versand“. Bei Wiederholung einer Übermittlung wird ein neuer Beleg erstellt. Nach Erfolg werden die zwischengespeicherten PDF-Bytes gelöscht. Eine SMTP-Übernahme ist keine garantierte Zustellung; bei Prozessabbruch direkt nach Übernahme kann ein erneut versandter Auftrag zu einem Duplikat führen.

Die Berechnung verwendet lokale Zeit ohne Sommerzeitkorrektur. Solange die App für Pause und Gastfahrt keine genaue Zeitlage sendet, wird die Pause dem Ende und die Gastfahrt dem Beginn des Eintrags zugeordnet. Die Verteilung auf Nacht, Sonntag und Feiertag ist daher vorläufig. Das PDF ist eine Eingangsbestätigung und keine Entgeltabrechnung.

### Monatsabrechnung

`GET /api/v1/me/months/{year}/{month}/summary` liefert die eigene Übersicht; Admins nutzen `GET /api/v1/admin/tf/{tf_id}/months/{year}/{month}/summary` oder die Tabelle in `/admin`. Die Abrechnung wird jeweils aus den gespeicherten Einträgen neu berechnet; laufende und künftige Monate sind als „vorläufig“ markiert. Ein Monatsabschluss mit Sperre oder automatischem E-Mail-Versand gehört noch nicht zu dieser Version.

Pro Kalendertag zählt geleistete Zeit aus Zugfahrt, Bereitschaft und Sonstiger Erfassung abzüglich Pause. Gastfahrt ist darin enthalten und wird separat ausgewiesen. Nur Tage mit erfasster Arbeit unter acht Stunden erhalten eine Auffüllung auf acht Stunden: zuerst wird die Gastfahrt innerhalb der tatsächlichen Arbeitszeit für das Achtstunden-Ziel genutzt, dann die restliche Lücke ergänzt. Gastfahrt wird nie doppelt addiert. Urlaub und Krankheit zählen mit je acht Stunden pro Tag (pro Datum einmal); freie Tage ohne Eintrag erhalten keine Auffüllung. Sonn-, Feiertags- und Nachtzeit werden informativ zusätzlich ausgewiesen, nicht nochmals in die Stundensumme addiert. Mehrere Einträge gleicher Art am Tag werden summiert; widersprüchliche Kombinationen von Arbeit und Urlaub/Krank oder Urlaub und Krank am selben Tag blockieren die Abrechnung mit HTTP 409 bis zur Korrektur.

Lokal gelöschte Einträge bleiben derzeit auf dem Server; Serverdaten werden noch nicht in die App geladen. Ein gleichzeitiger Betrieb auf mehreren Geräten ist nicht vorgesehen. Es gibt noch keine Passwortzurücksetzung, Dienstplanungsschnittstelle, Ausbleibe-Berechnung oder Kopplung der LokZeit-Standzeiten mit dem Monatsdatensatz. Für spätere Schemaänderungen wird ein Migrationstool benötigt.

API-Tests: `pip install -r requirements-dev.txt` und `python -m unittest discover -s tests` im Backend-Ordner. Die Tests verwenden SQLite als isolierte Testdatenbank. Der reguläre Betrieb verlangt MySQL.

## Arbeitszeitkorrekturen

Administratoren können Arbeitsbeginn und Arbeitsende je Mitarbeiter unter `/admin/worktime` bearbeiten. Tages-, Wochen- und Monatswerte werden neu berechnet; jede tatsächliche Änderung erzeugt eine E-Mail mit Vorher-/Nachher-Werten und einen nachvollziehbaren Änderungsverlauf. [Bedienung, Versand und Update](lokzeitleiste/worktime/README.md). In der Testumgebung landen Benachrichtigungen in Mailpit.
