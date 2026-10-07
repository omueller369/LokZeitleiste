# Komplette Debian-Testumgebung in einer VM

Dieser eigenständige Stack verwendet Apache 2.4 auf der VM und Container für Python-API, MySQL 8.4 und den PDF-Versanddienst. Mailpit nimmt Test-E-Mails mit PDF-Anhang per STARTTLS entgegen. Es versendet sie nicht an echte Postfächer. Die Testdatenbank und das Testpostfach haben eigene persistente Docker-Volumes. Bestehende Datenbanken werden nicht übernommen oder migriert.

## 1. Voraussetzungen auf der VM

Debian 12 (Bookworm) oder 13 (Trixie), empfohlen 2 CPU, 4 GB RAM und 20 GB freier Speicher. Internet für Paketinstallation, Container und Python-Abhängigkeiten. Vorhandene Dienste auf 8000, 8025 und 8080 prüfen: `sudo ss -ltnp`. Diese Ports müssen frei sein. Bestehenden LokZeitleiste-Lokalstack gegebenenfalls stoppen, ohne Volumes zu löschen.

```bash
cat /etc/os-release
sudo apt update
sudo apt install apache2 openssh-server git python3 openssl ca-certificates curl
sudo systemctl enable --now apache2 ssh
```

Docker Engine und Compose-Plugin nach https://docs.docker.com/engine/install/debian/ installieren. Falls Docker bereits vorhanden ist, zuerst `sudo docker compose version` prüfen. Docker nicht parallel zu einer anderen Containerinstallation neu installieren. Auf einer frischen VM:

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF_DOCKER
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: $VERSION_CODENAME
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF_DOCKER
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker compose version
```

## 2. Projekt bereitstellen und starten

Das Repository ist privat. Auf der VM mit einem berechtigten GitHub-Konto klonen (SSH-Schlüssel oder Git Credential Manager; keine Tokens in Befehle oder Konfigurationsdateien schreiben). Alternativ das komplette Repository vom Entwicklungsrechner auf die VM kopieren. Bei bestehendem Checkout vor `git pull --ff-only` lokale Änderungen prüfen.

```bash
git clone git@github.com:omueller369/LokZeitleiste.git
cd LokZeitleiste/backend
bash testenv/prepare.sh
sudo bash testenv/control.sh start
sudo bash testenv/control.sh admin
```

Beim letzten Befehl eigenen Admin-Benutzernamen und ein Passwort mit mindestens zwölf Zeichen vergeben. `prepare.sh` erzeugt `.env.test` mit zufälligen MySQL-Passwörtern und ein ein Jahr gültiges Testzertifikat mit Hostname `mailpit`. API und Worker vertrauen diesem Zertifikat über `SSL_CERT_FILE`; die TLS-Prüfung bleibt aktiv. Die geheimen Dateien werden weder ins Repository noch ins Docker-Build kopiert. Wiederholtes Vorbereiten behält Passwörter und Zertifikat bei. Nach Ablauf das Zertifikat bei gestopptem Stack erneuern und API, Worker und Mailpit neu starten.

Der Worker startet erst nach Datenbankinitialisierung und erfolgreicher API-Gesundheitsprüfung. Bei einer neuen Installation legt das Backend alle Tabellen an. Vorhandene Produktionsdaten niemals in diesen Stack einspielen.

## 3. Apache einschalten

Im Backend-Ordner:

```bash
sudo a2enmod proxy proxy_http
sudo cp apache/lokzeitleiste-local.conf /etc/apache2/sites-available/
sudo a2ensite lokzeitleiste-local.conf
sudo apache2ctl configtest
sudo systemctl reload apache2
curl --fail http://localhost:8080/health
```

Die mitgelieferte Konfiguration enthält `Listen 127.0.0.1:8080`. Diese Zeile darf nur einmal konfiguriert sein. Bei einem Fehler des Konfigurationstests erst die Ursache beheben, dann neu laden. Apache leitet an `127.0.0.1:8000` weiter. MySQL und der SMTP-Port werden nicht an den Host veröffentlicht.

## 4. Zugriff vom Entwicklungsrechner auf die VM

Die VM benötigt eine vom Entwicklungsrechner erreichbare SSH-Adresse: bei Bridged-/Host-only-Netzwerk ihre VM-IP; bei NAT eine konfigurierte SSH-Portweiterleitung. Auf dem Entwicklungsrechner, nicht in der VM:

```bash
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:8080:127.0.0.1:8080 -L 127.0.0.1:8025:127.0.0.1:8025 BENUTZER@VM_IP
```

Bei NAT mit weitergeleitetem SSH-Port entsprechend `-p PORT` und die Hostadresse verwenden. Tunnel während des Tests offen lassen. Danach:

| Ansicht | Adresse auf dem Entwicklungsrechner |
|---|---|
| Admin-Anmeldung und Tf-Stammdaten | http://localhost:8080/admin |
| API-Dokumentation | http://localhost:8080/docs |
| Monatsdaten, Monatsabrechnung, PDF-Versand | Im Admin-Bereich beim jeweiligen Tf |
| Testpostfach und PDF-Anhänge | http://localhost:8025 |

`localhost` exakt verwenden, nicht `127.0.0.1`: Die Admin-Prüfung vergleicht den Browser-Ursprung mit `PUBLIC_ORIGIN=http://localhost:8080`. Die Ports werden nur an Loopback gebunden. Die HTTP-Entwicklungsadresse dient fiktiven Testdaten.

## 5. Durchgängigen Test ausführen

Direkt auf der VM (oder auf dem Entwicklungsrechner bei aktivem Tunnel), im Backend-Ordner:

```bash
python3 testenv/smoke.py
```

Der Test fragt das zuvor angelegte Admin-Konto ab. Je Lauf erstellt er einen neuen fiktiven Tf, meldet ihn an und sendet vier Einträge für September 2026 zweimal. Er prüft vier gespeicherte Einträge statt Duplikaten, 34:00 Stunden Gutschrift, 3:00 Stunden enthaltene Gastfahrt, 4:00 Stunden Auffüllung, je acht Stunden Urlaub/Krank und zwei erfolgreiche SMTP-Aufträge. Schließlich sucht er den Empfänger in Mailpit. Er nutzt die reale MySQL-Datenbank und den realen SMTP-Dienst; Versand wird nicht simuliert.

Anschließend in Mailpit beide E-Mails öffnen, den PDF-Anhang herunterladen und dessen Tabelle prüfen. Der Test bestätigt die SMTP-Übernahme und das Vorhandensein der Nachricht, die PDF-Darstellung muss zusätzlich geprüft werden. Die erzeugten Tf und Monatsdaten bleiben erhalten. Für App-Tests einen eigenen Tf mit bekanntem Passwort und einer fiktiven E-Mail wie `tf.test@example.com` im Admin anlegen; jede Empfängeradresse landet ausschließlich in Mailpit.

## 6. Android-App verbinden

Auf dem Entwicklungsrechner mit aktivem Tunnel in Android Studio das Repository öffnen. Die API-Adresse im Debug-Build mit Gradle-Projekteigenschaft `lokzeitleisteApiBaseUrl=http://10.0.2.2:8080` setzen. Beispiel bei installiertem Gradle und Android SDK:

```bash
gradle :app:assembleDebug -PlokzeitleisteApiBaseUrl=http://10.0.2.2:8080
```

Das Repository enthält derzeit keinen Gradle-Wrapper. Android Studio beziehungsweise eine passende Gradle-Installation und Android SDK werden für den App-Build benötigt. Der Android-Emulator erreicht über `10.0.2.2` den Entwicklungsrechner und damit den SSH-Tunnel. Mit dem im Backend angelegten Tf anmelden, Einträge erstellen, Monat senden und in Admin sowie Mailpit prüfen.

Für ein physisches Tablet braucht die App einen erreichbaren HTTPS-Endpunkt. Die aktuelle HTTP-Ausnahme gilt nur für den Debug-Emulator unter `10.0.2.2:8080`. Deshalb erfolgt der erste App-Test im Emulator; eine direkte Tablet-Verbindung zur VM wird separat eingerichtet.

## 7. Betrieb, Sicherung und Fehlersuche

```bash
sudo bash testenv/control.sh status
sudo bash testenv/control.sh logs
sudo bash testenv/control.sh backup
sudo bash testenv/control.sh stop
sudo bash testenv/control.sh start
```

`stop` behält die Volumes und alle Testdaten. Die Sicherung enthält die MySQL-Testdaten unter `testenv/backups/`, keine Testpostfachdaten; `.env.test` und Zertifikate separat geschützt aufbewahren. Zum Wiederherstellen in eine vorbereitete Testdatenbank:

```bash
sudo docker compose --env-file .env.test -f compose.test.yaml exec -T db sh -c 'MYSQL_PWD="$MYSQL_PASSWORD" exec mysql -u "$MYSQL_USER" "$MYSQL_DATABASE"' < testenv/backups/DATEI.sql
```

Nur in die dafür vorgesehene Testdatenbank importieren. Bei Fehlern: Apache `sudo apache2ctl configtest`, API/MySQL `control.sh logs`, Versandstatus beim Tf und Mailpit prüfen. HTTP 403 im Admin deutet häufig auf eine falsche Browser-Adresse hin. Alte lokale Compose-Dateien nicht zusätzlich auf denselben Ports starten.

## Prüfstatus des bereitgestellten Aufbaus

Skript- und Konfigurationsprüfungen sowie bestehende Backend-Tests können in der Entwicklungsumgebung ausgeführt werden. Der tatsächliche Containerstart, Apache-Konfiguration, MySQL-Lauf, SMTP-TLS und Android-Verbindung müssen auf der Debian-VM mit dem obigen Ablauf geprüft werden. Es besteht noch kein Zugang zur VM.

Quellen: Docker-Debian-Installation https://docs.docker.com/engine/install/debian/ ; Mailpit STARTTLS https://mailpit.axllent.org/docs/configuration/smtp/ ; Mailpit-Container https://mailpit.axllent.org/docs/install/docker/ .
