# Automatische Setup-Routine für Ubuntu Server 26.04.1 LTS

Die Routine installiert die vollständige **Backend-Testumgebung**: Apache und SSH-Zugang auf Ubuntu, Git, Docker Engine und Compose, Python-API samt Python-Abhängigkeiten, MySQL 8.4, PDF-Versandworker und Mailpit-Testpostfach. Ein aktueller Android-Build gehört nicht zur Serverinstallation; die bestehende App wird anschließend über den Emulator angeschlossen.

Vorgesehen ist **Ubuntu Server 26.04.1 LTS (Resolute)** mit systemd auf amd64/arm64. Ubuntu meldet Point-Releases in `/etc/os-release` üblicherweise als `VERSION_ID=26.04`; beide Schreibweisen werden erkannt. Für bestehende Installationen bleiben Debian 12/13 unterstützt. Empfohlen: 2 CPU, 4 GB RAM und 20 GB freier Speicher. Internet ist für APT, Docker-Images und Python-Pakete erforderlich. Das private Repository muss bereits mit berechtigtem GitHub-Zugang auf die VM kopiert oder geklont sein. Auf einer frischen Ubuntu-VM kann `sudo apt install git` dafür erforderlich sein.

## Start

Der Setup-Stand liegt im Branch `setup/debian-testumgebung`:

```bash
git clone --branch setup/debian-testumgebung git@github.com:omueller369/LokZeitleiste.git
cd LokZeitleiste
bash setup.sh --check
sudo bash setup.sh
```

Nach Übernahme in `main` kann der Branch-Parameter beim Klonen entfallen. Auf einem bestehenden Checkout zuerst lokale Änderungen prüfen, dann den Setup-Branch auschecken. Der Vorprüflauf installiert nichts. `sudo bash setup.sh` installiert anschließend fehlende Pakete, baut und startet alle Backend-Dienste und legt ohne Rückfragen den Admin **administrator** mit einem zufälligen Passwort an. Ubuntu selbst muss bereits auf dem Server installiert sein.

Das initiale Admin-Passwort liegt ausschließlich auf dem Server in `/var/lib/lokzeitleiste/admin-initial-password`, im Verzeichnis mit Rechten `700` und als Datei mit Rechten `600`. Anzeigen:

```bash
sudo cat /var/lib/lokzeitleiste/admin-initial-password
```

Ein bestehendes aktives Admin-Konto wird beibehalten. Dann wird keine neue Passwortdatei erzeugt. Nach fehlgeschlagener Erstinstallation wird die bereits erzeugte Datei beim nächsten Lauf wiederverwendet. Das Passwort wird nicht im Installationsprotokoll ausgegeben. Die Datei enthält das initiale Passwort; spätere Passwortänderungen aktualisieren sie nicht.

Der gemeinsame Installer liegt in `setup/install.sh`. `setup.sh` aktiviert standardmäßig `--auto-admin`. `install-ubuntu.sh` und der ältere Einstieg `install-debian.sh` leiten ebenfalls an den gemeinsamen Installer weiter; ohne Admin-Optionen fragen diese beiden Einstiege interaktiv nach Zugangsdaten.

Die Routine prüft Betriebssystem, Architektur, systemd, Projektdateien, freien Speicher, benötigte Pakete, Docker/Compose und Ports. Bei bestehenden konkurrierenden Diensten oder Paketkonflikten stoppt sie mit einem konkreten Hinweis. Nutzbare vorhandene Docker-Installationen werden verwendet. Fremde Containerplattformen werden nicht automatisch deinstalliert.

Die Python-Pakete werden beim Containerbuild anhand von `backend/requirements.txt` installiert. Datenbank und API haben Gesundheitsprüfungen; der Versandworker startet nach der Datenbankinitialisierung. Abschließend werden API, Admin-Seite und Mailpit abgefragt. Das SMTP-Testzertifikat wird lokal erzeugt und vom Backend geprüft. Mailpit fängt alle Test-E-Mails ab; echte Empfänger erhalten keine Nachrichten.

## Installation ohne Eingabe

Der empfohlene Einstieg ist `sudo bash setup.sh`. Alternativ: `sudo bash setup/install-ubuntu.sh --auto-admin`. Für selbst festgelegte Zugangsdaten:

Für eine unbeaufsichtigte Installation eine Passwortdatei außerhalb des Repositorys mit genau einer Zeile und einem Passwort von mindestens zwölf Zeichen bereitstellen. Dateirechte auf `600` setzen. Keine Zugangsdaten in Git speichern.

```bash
chmod 600 /geschuetzter/pfad/admin-passwort
sudo bash setup/install-ubuntu.sh --admin-user administrator --admin-password-file /geschuetzter/pfad/admin-passwort
```

Das Passwort wird über stdin an den Admin-Bootstrap übergeben und nicht als Kommandozeilenargument oder Umgebungsvariable weitergegeben. Ist dieser aktive Admin bereits vorhanden, bleibt sein Passwort unverändert. Ein vorhandenes Tf-Konto wird niemals in ein Admin-Konto umgewandelt. Nach erfolgreicher Anlage die Passwortdatei geschützt verwahren oder entfernen.

Mit `--skip-admin` lassen sich nur die Dienste installieren; danach ist der Admin über `sudo bash backend/testenv/control.sh admin` anzulegen. Bei einem interaktiven Wiederholungslauf wird ein bereits vorhandenes aktives Admin-Konto beibehalten.

## Nach der Installation

Direkt auf der VM:

- Admin und Tf-Stammdaten: http://localhost:8080/admin
- Planung: http://localhost:8080/admin/planning
- API-Dokumentation: http://localhost:8080/docs
- Testpostfach und PDF-Anhänge: http://localhost:8025

Die Dienste sind an Loopback gebunden. Vom Entwicklungsrechner einen SSH-Tunnel zur VM öffnen:

```bash
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:8080:127.0.0.1:8080 -L 127.0.0.1:8025:127.0.0.1:8025 BENUTZER@VM_IP
```

Bei NAT-Portweiterleitung den SSH-Port über `-p PORT` angeben. Browser auf `http://localhost:8080/admin` öffnen; der genaue Ursprung wird für Admin-Schreibzugriffe geprüft. Die App im Android-Emulator verwendet einen Debug-Build mit `-PlokzeitleisteApiBaseUrl=http://10.0.2.2:8080`. Android Studio und SDK werden auf dem Entwicklungsrechner benötigt.

Den echten Datenbank-/SMTP-Prüflauf direkt auf der VM starten:

```bash
python3 backend/testenv/smoke.py
```

Dieser fragt das Admin-Konto ab, legt einen fiktiven Tf an, sendet vier Einträge zweimal und prüft Monatsberechnung, gespeicherte Daten und SMTP-Übernahme in Mailpit. Anschließend die PDF-Anhänge in Mailpit visuell prüfen. Weitere Einzelheiten zur App-Verbindung und Sicherung stehen in [backend/testenv/README.md](../backend/testenv/README.md).

## Wiederholung und Fehler

Dieselbe Setup-Routine kann erneut gestartet werden. MySQL-Passwörter, Testdaten, Testpostfach und bestehende Admin-Zugangsdaten bleiben erhalten. Änderungen am Code werden neu gebaut. Bei künftigen Schemaänderungen muss eine passende Migration erfolgen; `create_all` verändert bestehende Spalten nicht.

Die Routine installiert fehlende Abhängigkeiten und kann erforderliche Paketupdates durch APT auslösen. Sie führt keine allgemeine Betriebssystem-Aktualisierung durch. Abweichende Apache-Site-Dateien werden nicht überschrieben. Bei fehlerhaftem Apache-Konfigurationstest wird die neu angelegte Site zurückgenommen und Apache nicht neu geladen. Bereits zuvor installierte Pakete und gestartete Container bleiben bei einem Fehler bestehen, sodass der Lauf nach Korrektur fortgesetzt werden kann.

```bash
sudo bash backend/testenv/control.sh status
sudo bash backend/testenv/control.sh logs
sudo bash backend/testenv/control.sh backup
```

Der Installer führt keinen destruktiven Reset aus. Datenbank-Volumes niemals zur Fehlerbehebung ungeprüft löschen. Das Setup richtet eine lokale Testumgebung ein; für einen öffentlich erreichbaren Server oder ein physisches Tablet folgt eine separate HTTPS-Konfiguration.

## Prüfung

Die GitHub-Prüfung validiert Bash-Syntax, ShellCheck, Compose-Konfiguration und Backend-Tests. Ein tatsächlicher Erstinstallationslauf auf einer Ubuntu-26.04.1-VM und ein Android-Build stehen noch aus. Der Installer wird in GitHub nicht mit Root-Rechten auf einem fremden Server gestartet.

Grundlagen: [Docker auf Ubuntu](https://docs.docker.com/engine/install/ubuntu/), [Apache-Konfigurationstest](https://httpd.apache.org/docs/2.4/programs/apachectl.html), [Mailpit SMTP/TLS](https://mailpit.axllent.org/docs/configuration/smtp/).

## Weboberfläche des Planungsmoduls

Nach Admin-Anmeldung unter `/admin` beim jeweiligen Tf **Arbeitszeitplan** wählen. Unter `/admin/planning` stehen Monatskalender, Tagesliste, Jahresansicht und Excel-Import als eigene Ansichten bereit. Ein Kalendertag öffnet Tagesart und Notiz; danach die Änderungen speichern. Die Kennzahlen reagieren auf die Eingabe. Die Jahresmatrix und PDF-Exporte zeigen gespeicherte Daten.

Die Tagesliste erlaubt Einzel- und Sammeländerungen. Die Jahresmatrix führt per Klick auf einen Tag zum zugehörigen Monat. Excel wird erst nach Prüfung und Bestätigung übernommen. Monats-/Jahres-PDFs und die Excel-Vorlage lassen sich herunterladen. Anmeldung und Schreibrechte werden vom Backend geprüft.
