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

Für eine unbeaufsichtigte Installation eine Passwortdatei außerhalb des Repositorys mit genau einer Zeile und einem Passwort von mindestens sechs Zeichen bereitstellen. Dateirechte auf `600` setzen. Keine Zugangsdaten in Git speichern.

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
# Benutzerverzeichnisse für Dokumente

Direkt im Software-/Repository-Verzeichnis werden zwei dauerhafte Ablagebereiche angelegt:

| Benutzer | Verzeichnis auf dem Linux-Host |
|---|---|
| Triebfahrzeugführer | `<Projektverzeichnis>/TF/<Loginname>/` |
| Verwaltungsmitarbeiter und Administratoren | `<Projektverzeichnis>/VW/<Loginname>/` |

Beispiel bei Installation unter `/opt/LokZeitleiste`: `/opt/LokZeitleiste/TF/787123/` und `/opt/LokZeitleiste/VW/buero.muster/`. Weitere Dokument-Unterordner werden erst nach Festlegung der Dokumentarten ergänzt. Die bestehende Speicherung von Fotos und Quittungsbelegen wird dadurch nicht verändert.

Beim regulären Start legt `init_db` fehlende Verzeichnisse auch für vorhandene und gesperrte Benutzer an. Neue TF, Verwaltungsmitarbeiter und Administratoren erhalten ihr Verzeichnis beim Anlegen. Bei Änderung einer TF-Nummer wird das bisherige Verzeichnis einschließlich seines Inhalts umbenannt. Ein belegtes Ziel wird nicht überschrieben oder zusammengeführt. Benutzerverzeichnisse werden beim Sperren oder beim Testdatenreset nicht gelöscht.

Die beiden Compose-Konfigurationen binden ausschließlich `TF` und `VW` vom Host nach `/user-files/TF` und `/user-files/VW` ein. Der einmalige Dienst `user-directories` bereitet die Besitzrechte für den bestehenden API-Benutzer mit UID 10001 vor. API und Mailer arbeiten anschließend weiterhin ohne root. Die Daten bleiben bei Container-Neubau und -Austausch auf dem Host erhalten. Die Basisrechte sind privat; nach Einrichtung der Hostkonten werden gezielte POSIX-ACLs ergänzt; die Ordner werden nicht als öffentliche Webdateien ausgeliefert und sind in Git ausgeschlossen.

Nach Aktualisierung der Quellen den Stack wie üblich starten, damit Initialisierung und Bind-Mounts aktiv werden:

```bash
bash backend/testenv/control.sh start
```

Fehlende Benutzerverzeichnisse lassen sich bei laufendem Teststack auch nachträglich ergänzen:

```bash
cd backend
docker compose --env-file .env.test -f compose.test.yaml exec api python -m lokzeitleiste.user_directories
```

Bei nativem Betrieb ist der Standard das Repository-Verzeichnis. Mit `LOKZEITLEISTE_FILES_ROOT` kann ein anderer **absoluter** Ablageroot angegeben werden; der Prozess benötigt dort Schreibrechte. Die Compose-Konfiguration setzt diese Variable im Container auf `/user-files`; auf dem Host bleiben die Ordner direkt im Projektverzeichnis. Änderungen an Login-Verzeichnissen dürfen nur über die Software oder durch den Serveradministrator erfolgen. Neben Datenbank und Konfiguration künftig auch beide Hostverzeichnisse `TF` und `VW` in die Datensicherung aufnehmen.

## Dokumentenmodul und Linux-Konten ohne Anmeldung

Für die Aktualisierung einschließlich Systemkonten und ACL-Paket einmal im Projektverzeichnis ausführen:

```bash
sudo bash setup.sh
```

Der Installer richtet `lokzeitleiste-users.service` und einen Timer ein. Beim Update erfolgt der Abgleich sofort, danach etwa jede Minute für neu angelegte Benutzer. Ein späterer Start über `sudo bash backend/testenv/control.sh start` stößt den eingerichteten Abgleich ebenfalls an. Der Containerstart allein erstellt die Ordner und ergänzt die Datenbank; die **Linux-Hostkonten** benötigen den einmaligen Installer-Aufruf mit root. Die Weboberfläche bleibt ohne root-Rechte.

Der Home-/Ablagepfad folgt weiterhin dem Login. Unter diesem Pfad wird folgende Struktur vorbereitet:

| TF | VW einschließlich Administratoren |
|---|---|
| `Dokumente/Arbeitsberichte/JJJJ/MM/TT/` | `Dokumente/Protokolle/` |
| `Dokumente/Monatsabrechnung/JJJJ/MM/` | `Dokumente/Sonstiges/` |
| `Dokumente/Fahrpläne/Trassen/` | |
| `Dokumente/Fahrpläne/FPLO/` | |
| `Dokumente/Fahrpläne/Sonstiges/` | |

Arbeitsberichte werden nach dem Datum des **Dienstbeginns** unter `Arbeitsberichte/JJJJ/MM/TT/` abgelegt, auch bei nachträglicher Erstellung oder einem Dienst über Mitternacht. Monatsdokumente verwenden den betreffenden **Abrechnungsmonat** unter `Monatsabrechnung/JJJJ/MM/`. Vorhandene automatisch archivierte PDFs werden beim Update in diese Struktur umsortiert; Fachliche Daten und Quellenzuordnung bleiben erhalten; bei einem PDF-Formatupdate werden die Dokumente aus diesen Daten neu erzeugt. Namenskollisionen überschreiben keine fremden Dokumente. Die Originaldatei wird erst nach erfolgreichem Datenbank-Commit entfernt; leere alte Datumsordner werden dabei entfernt. Manuelle Uploads bleiben an ihrem bisherigen Ort. Änderungen des Dienstbeginns verschieben auch den zugehörigen Arbeitsbericht. Bei neuen TF wird der aktuelle Tages-/Monatsordner vorbereitet. Beim nächsten Update werden fehlende Ordner für sämtliche vorhandenen Konten ergänzt. Vorhandene Arbeitsberichte werden aus den gespeicherten Berichtsdaten als PDFs ergänzt, vorhandene Monatsdaten als Monatszusammenfassung und Monatsbericht. Historische E-Mail-PDFs, deren Versanddaten bereits entfernt sind, werden nicht als unveränderte Original-E-Mails ausgegeben.

Jeder Anwendungsbenutzer erhält das technische Linux-Konto `lz_u_<Datenbank-ID>` mit stabiler UID `200000 + Datenbank-ID`, gesperrtem Passwort und `/usr/sbin/nologin`. Es entstehen keine interaktiv nutzbaren SSH-/Shell-Anmeldungen; Backend-Passwörter bleiben davon unabhängig. Das zusätzliche technische Konto `lz_api` mit UID 10001 bildet den vorhandenen Containerbenutzer auf dem Host ab. Namens-/UID-Kollisionen mit fremden Konten werden abgewiesen. Bei geänderten TF-Nummern folgt das Home-Verzeichnis der umbenannten Ablage. Bestehende Konten werden nicht gelöscht. Noch belegte Ablagen eines früheren Logins werden keinem neuen Mitarbeiter zugeordnet; auch der Testdatenreset reserviert bereits vorhandene Verzeichnisnamen.

Die Benutzer erhalten Eigentum und Lese-, Schreib- und Löschrechte in ihrer eigenen Ablage. POSIX-ACLs geben zusätzlich ausschließlich dem technischen API-/Mailer-Benutzer Zugriff; notwendige Elternverzeichnisse erhalten für den jeweiligen Benutzer nur Durchtrittsrecht. Default-ACLs erhalten diese Rechte auch bei neuen Dateien und Ordnern. Dies setzt ein Linux-Dateisystem mit ACL-Unterstützung voraus. Die Vorbereitungsroutine folgt keinen symbolischen Links. Ein anderer Linux-Benutzer erhält dadurch keinen Zugriff auf fremde Benutzerablagen.

**Meine Dokumente** ist unter `/documents`, im TF Portal und im Backend-Menü für jeden angemeldeten Benutzer erreichbar. Das Modul benötigt keine fremden Mitarbeiterrechte und zeigt ausschließlich die eigene Ablage. Es bietet einen aufklappbaren Ordnerbaum, Suche nach Datei-/Ordnernamen, Downloads und Uploads in einen ausgewählten Ordner. Pro Upload sind höchstens 10 MiB zulässig; übergroße Requests werden bereits vor der Multipart-Verarbeitung begrenzt. Dateien werden nur als Downloads, niemals als ausführbare Webinhalte ausgeliefert. Doppelte Uploadnamen erhalten einen eindeutigen Zusatz.

Die neue Tabelle `document_files` speichert Eigentümer, Hochladenden, Dateipfad, Prüfsumme und Herkunft. Löschen ist ausschließlich für eigene Uploads möglich. Automatisch erzeugte oder manuell auf dem Server abgelegte Dokumente haben keine entsprechende Uploadfreigabe. Die Linux-Dateirechte und die Löschprüfung im Modul sind getrennte Ebenen; Linux-Konten sind für Endbenutzer nicht anmeldbar. Keine neue Dokumentenroute ermöglicht den Zugriff auf einen anderen Benutzer.

Beim Synchronisieren eines Arbeitsberichts werden sein PDF und die zugehörigen Monats-PDFs archiviert. Das Arbeitsbericht-PDF wird über die vorhandene dauerhafte Versandwarteschlange an die hinterlegte TF-E-Mail-Adresse versandt. Vor der E-Mail-Zustellung bestätigt der Versandworker die Archivablage; bei Fehlern bleibt der Versand wiederholbar. Änderungen an Zugfahrtdaten aktualisieren die Ablage und erzeugen eine neue Versandversion. Ein alter Versandwiederholungsversuch überschreibt keine neuere Berichtsversion. SMTP-Einstellungen und die bisherigen Wiederholungsgrenzen gelten weiterhin. Der bestehende Empfänger für Quittungsbelege wird dadurch nicht geändert.

Monatszusammenfassung und Monatsbericht liegen als zwei PDFs im betreffenden Monatsordner. Pausen werden dokumentiert und nicht von der Arbeitszeit abgezogen. Monatsgrenzen und über Mitternacht reichende Dienste werden bei der Ablage berücksichtigt. Der vorhandene Worker ergänzt fehlende Dateien und aktualisiert Monatsausgaben nach Arbeitszeitkorrekturen. Keine nachträgliche Ordner-/Archivergänzung versendet alte Berichte erneut.

Für eine vollständige Sicherung werden jetzt **Datenbank einschließlich `document_files`, beide Verzeichnisbäume und die Host-Konfiguration der Linux-Konten/ACLs** benötigt. Nach einer Wiederherstellung zuerst die Datenbank und Dateien zurückspielen und anschließend den Installer/Benutzerdienst erneut ausführen; dadurch werden die stabilen UID-Zuordnungen und ACLs wiederhergestellt.

## Getrennte Installation und Aktualisierung

- **Neue Testumgebung:** `sudo bash setup-new.sh` im Projektstamm. Verweigert die Wiederverwendung vorhandener Testkonfiguration, Benutzerdateien oder des Standard-Testdatenbankvolumes.
- **Bestehende Testumgebung:** `sudo bash setup-update.sh` im bisherigen Projektstamm. Sichert vor dem Neubau Datenbank, TF/VW mit ACLs, Konfiguration und Zertifikate in einem geschützten zeitgestempelten Verzeichnis unter `backend/testenv/backups/`. Vorhandene Passwörter bleiben bestehen. Kein automatischer Datenbank-Rollback und kein Datenreset.
- Beide unterstützen `--check` (nur prüfen) sowie die Admin-Optionen von `setup.sh`. Der Installer aktualisiert die aktuell ausgecheckten Quellen; `git pull --ff-only` vorher selbst ausführen.

Die vollständigen Befehle für Ubuntu in **UTM auf dem Mac**, inklusive Clone, Neuinstallation, Update, SSH-Tunnel, Admin-Zugang und Betrieb, stehen in [UTM-Mac.md](UTM-Mac.md).

## Öffentlicher Demo-Server

`sudo bash setup-demo.sh` richtet die Demo für **ctl-software.io-goerlitz.eu / 212.227.86.251** zunächst mit HTTP und interner Test-E-Mail-Zustellung ein. Bei vorhandener Umgebung wird zuerst die Update-Sicherung ausgeführt. DNS, Firewallvoraussetzungen, SSH-/Clone-Befehle, Zugriff, Updates und Kontrollen: [DEMO-Server.md](DEMO-Server.md).

HTTPS bleibt für später optional: `sudo bash setup-demo.sh --https --email DEINE-EMAIL@BEISPIEL.DE`. Ohne `--https` werden kein Zertifikat und keine HTTPS-Weiterleitung eingerichtet.

Die externe Demo verwendet standardmäßig MySQL auf dem Ubuntu-Host (`ctl-software`, Datenbank `ctl_software`, Passwortabfrage beim ersten Setup). Konfiguration: `backend/.env.host`, Betrieb: `backend/testenv/control-host.sh`. Es wird kein weiterer MySQL-Server installiert. Der bisherige Docker-Datenbankweg ist über `setup-demo.sh --docker-mysql` verfügbar.

## Tabellenlayout und Neuerstellung vorhandener PDFs

Arbeitsberichte zeigen Dienstzeiten/Kopfdaten, Gastfahrten, Zugdaten und Ereignisse in getrennten Tabellen. Monatszusammenfassungen verwenden Tabellen für Kopfdaten, Soll/Ist-Summen und einzelne Tage. Monatsberichte und Eingangsbestätigungen bleiben tabellarisch. Planungs-PDFs zeigen auch Kopf-, Hinweis-, Feiertags- und Notizdaten in Tabellen.

Dateiname für Arbeitsberichte: `JJJJ-MM-TT-VERSION-ID-Arbeitsbericht.pdf`, beispielsweise `2026-10-12-1-42-Arbeitsbericht.pdf`. Das Datum ist der Dienstbeginn, ID die Berichts-ID. Version beginnt bei 1 und steigt bei Änderungen der Zugfahrtdaten; reine Neuformatierung behält sie bei. Archiv und neue E-Mail-Anhänge verwenden denselben Namen. Im Dokumentenmodul liegt der aktuelle Berichtsstand. Bereits versendete E-Mails und deren Dateinamen werden nicht nachträglich verändert.

Beim nächsten Update werden vorhandene automatisch erzeugte Arbeitsberichte und beide Monatsdokumente aus ihren gespeicherten Quelldaten neu erstellt und gegebenenfalls umbenannt. Die zusätzliche Tabelle `document_render_states` speichert den Formatstand, damit die Neuerstellung einmal pro Dokument erfolgt. Sie wird beim regulären Datenbankstart automatisch angelegt. Es werden dadurch keine alten Berichte erneut per E-Mail versendet. Manuell hochgeladene PDFs bleiben unverändert. Planungs-PDFs werden beim nächsten Export im neuen Layout erzeugt.

Externer Server: `git pull --ff-only origin setup/debian-testumgebung`, danach `sudo bash setup-demo.sh`. Die reguläre Sicherung erfolgt vor Schema-/PDF-Aktualisierung. Lokale Testumgebung: `sudo bash setup-update.sh`.
