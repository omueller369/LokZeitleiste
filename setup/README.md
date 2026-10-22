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

Dateiname für Arbeitsberichte: `JJJJ-MM-TT-VERSION-ID-Arbeitsbericht.pdf`, beispielsweise `2026-10-12-1-42-Arbeitsbericht.pdf`. Das Datum ist der Dienstbeginn, ID die Berichts-ID. Version beginnt bei 1 und steigt bei Änderungen der Zugfahrtdaten; ab Formatstand 5 erhöht auch die Neuerstellung vorhandener Arbeitsberichte beim Formatupdate diese Version. Archiv und neue E-Mail-Anhänge verwenden denselben Namen. Im Dokumentenmodul liegt der aktuelle Berichtsstand. Bereits versendete E-Mails und deren Dateinamen werden nicht nachträglich verändert.

Beim nächsten Update werden vorhandene automatisch erzeugte Arbeitsberichte und beide Monatsdokumente aus ihren gespeicherten Quelldaten neu erstellt und gegebenenfalls umbenannt. Die zusätzliche Tabelle `document_render_states` speichert den Formatstand, damit die Neuerstellung einmal pro Dokument erfolgt. Sie wird beim regulären Datenbankstart automatisch angelegt. Es werden dadurch keine alten Berichte erneut per E-Mail versendet. Manuell hochgeladene PDFs bleiben unverändert. Planungs-PDFs werden beim nächsten Export im neuen Layout erzeugt.

Externer Server: `git pull --ff-only origin setup/debian-testumgebung`, danach `sudo bash setup-demo.sh`. Die reguläre Sicherung erfolgt vor Schema-/PDF-Aktualisierung. Lokale Testumgebung: `sudo bash setup-update.sh`.

Arbeitsbericht-Formatstand 3: Titel `Arbeitsbericht vom TT.MM.JJJJ` mit Datum des Dienstbeginns. Zeitspalten zeigen bei eintägigen Diensten nur `HH:MM`. Bei Diensten über Mitternacht wird `TT.MM.JJJJ HH:MM` beim Wechsel gegenüber dem vorherigen Zeitwert der jeweiligen Tabelle angezeigt; danach wieder nur die Uhrzeit. Der Zugfahrt-Ereignisblock ist um die Breite der Zugnummer-Spalte eingerückt. Vorhandene automatisch erzeugte Berichte werden beim Update erneut auf diesen Formatstand gebracht, ohne ihre fachliche Versionsnummer zu erhöhen oder alte E-Mails neu zu versenden.

Arbeitsbericht-Formatstand 4: DIN A4 Hochformat, Kopfdaten in zwei gleich hohen Blöcken nebeneinander. Die Mindestpausen-Zeile wird nicht gedruckt; eine leere Begründung für mehr als zwölf Stunden wird ausgeblendet. Die Gastfahrt-Spalte Sz erscheint nur, wenn mindestens eine Gastfahrt als Selbstzahler markiert ist. Jede Zugfahrt beginnt auf einer eigenen Seite und wird bei umfangreichen Ereignislisten proportional auf die verfügbare Seite eingepasst. Vorhandene Systemberichte werden beim nächsten Update erneut erstellt. Die fachliche Berechnung und Versionsnummer bleiben dabei unverändert.

Arbeitsbericht-Formatstand 5: TF-Nummer und ihr Wert entfallen aus der Kopftabelle. Beim Update erhalten bestehende Arbeitsbericht-PDFs einmalig eine höhere Version in Kopftabelle und Dateiname. Weitere Starts ohne Formatänderung erhöhen die Version nicht. Bereits versendete E-Mails bleiben erhalten; es erfolgt kein erneuter Versand alter Berichte.

## Monatliches Überstundenkonto

In Verwaltung oder TF-Übersicht öffnet **Überstundenkonto** das Konto des gewählten TF. Die Aktivierung gilt ab dem ausgewählten Monat bis zur nächsten Aktivierungs-/Deaktivierungsänderung. Neue und vorhandene TF starten ohne aktiviertes Konto; bei der Installation werden nur zusätzliche Tabellen angelegt, keine alten Stunden automatisch gebucht.

Pro gespeicherter Dienstschicht (Arten Sonstige Erfassung/Dienstschicht oder Zugfahrt) zählt max(0, Dienstende − Dienstbeginn − 480 Minuten). Bereitschaft, Rufbereitschaft, Ausfallschicht, Urlaub und Krank erzeugen hier keine Überstunden. Mehrere Einträge werden jeweils einzeln gerechnet. Pausen werden nicht abgezogen. Gastfahrten außerhalb des Dienstes sind nicht in der Dienstspanne enthalten. Eine durchgehende Nachtschicht wird einmal gerechnet und dem Monat ihres Dienstbeginns zugeordnet, auch über Monats-/Jahresgrenzen.

Nach Monatsende wählt die Verwaltung den Abschluss: sämtliche Stunden zur Auszahlung vormerken oder bis zur freien Kapazität ins Jahresüberstundenkonto buchen und den Rest zur Auszahlung vormerken. Vor dem Abschluss wird die Verteilung in Stunden/Minuten bestätigt. Der gesamte Kontostand kann höchstens 40 Stunden betragen. Guthaben bleibt über Jahreswechsel erhalten; der Kalenderjahreswechsel setzt es nicht zurück. Eine tatsächliche Banküberweisung, Lohnabrechnung oder automatische Auszahlung wird hierdurch nicht ausgelöst. Entnahmen aus bereits gebuchtem Jahresguthaben sind in diesem Schritt noch kein eigener Vorgang.

Berechtigung im vorhandenen Modul Monatsabrechnung und PDF-Versand: Lesen (Stufe 1) zeigt Konten, Lesen/Schreiben (2) erlaubt Monatsabschlüsse, Administration (3) erlaubt zusätzlich Aktivierung/Deaktivierung und Wiederöffnung mit Begründung. TF können diese Verwaltungsendpunkte nicht aufrufen. Parallele Schreibvorgänge werden je TF serialisiert; Quellen, Kontostand und Abschlussstand werden vor Buchung erneut geprüft. Ein bereits geschlossener Monat kann nicht doppelt gebucht werden.

Abschlüsse sind gespeicherte Schnappschüsse. Nach Arbeitszeitkorrekturen zeigt das Konto eine Prüfmarkierung und blockiert neue Abschlüsse, bis die Abweichung durch Wiederöffnung und erneuten Abschluss behandelt wurde. Die Wiederöffnung nimmt die Stundenbuchung im Konto zurück; bereits außerhalb dieser Software geleistete Auszahlungen müssen gesondert korrigiert werden. Die Historie mit Verwaltungsbenutzer und Zeitstempel bleibt erhalten. Aktivierungseinstellungen dürfen geschlossene Zeiträume nicht rückwirkend verändern.

Die Tabellen overtime_policies, overtime_closings und overtime_audits werden durch den üblichen init_db-Aufruf bei Neuinstallation und Update angelegt. Die vorhandene Sicherung vor dem Update bleibt erforderlich. Bestehende Zeit-, PDF- und Personaldaten bleiben erhalten. Fachtests: python -m unittest discover -s backend/tests -p 'test_overtime.py' -v (PYTHONPATH=backend setzen oder im backend-Verzeichnis starten).

## Persönliches Bahnhofsverzeichnis im TF-Portal

Unter TF Portal → Bahnhofsverzeichnis führt jeder TF seine eigene Liste. Bahnhof hinzufügen öffnet die Suche im vorhandenen DS100-Stammdatenbestand nach DS100 oder Orts-/Bahnhofsname. Die Auswahl übernimmt den eindeutigen DS100-Code und den Namen aus dem Stammdatensatz. Mehrfaches Anlegen desselben Codes für denselben TF wird verhindert. Anschließend lassen sich Kontakte ergänzen; jede Nummer benötigt eine Bezeichnung. Festnetz, Mobilnetz, Bada-Nummer, Langwahl und Ortsfunk/Kurzwahl unterstützen mehrere Einträge (insgesamt höchstens 100 pro Bahnhof). Nummern bleiben Textwerte und behalten führende Nullen, Pluszeichen und Kurz-/Sonderwahlzeichen.

Die persönliche Liste ist nach DS100 sortiert und nach DS100/Ort durchsuchbar. Ein Klick zeigt die gespeicherten Kontakte und den Bahnhofsplan; Bearbeiten erlaubt Änderungen und das Entfernen einzelner Nummern oder des gesamten eigenen Eintrags. Ungespeicherte Eingaben lösen beim Verlassen eine Rückfrage aus. Gleichzeitige Änderungen werden anhand einer Revisionsnummer geprüft.

Pro Listeneintrag kann ein Bahnhofsplan als PDF, JPEG oder PNG bis 10 MB hochgeladen, heruntergeladen, ersetzt oder gelöscht werden. Dateien werden auf gültiges Format geprüft und mit privater Downloadantwort ausgeliefert. Die Ablage erfolgt in der Datenbank und wird von der bestehenden Datenbanksicherung erfasst; es gibt keinen öffentlichen Dateipfad. Kontaktdaten und Pläne gehören jeweils nur dem angemeldeten TF. Andere TF oder Verwaltungsbenutzer können diese persönlichen API-Endpunkte nicht lesen oder ändern.

Beim regulären Update/bei der Neuinstallation legt init_db die zusätzlichen Tabellen tf_stations und tf_station_plans an. Bestehende Konten beginnen mit einer leeren Liste. Es werden keine vorhandenen Personen-, Arbeitszeit-, PDF- oder Überstundendaten geändert. Der vorhandene TF-Testdatenreset berücksichtigt die neuen abhängigen Datensätze. Die neue Oberfläche ist in Deutsch, Englisch, Polnisch, Russisch und Spanisch eingebunden.

### Bahnhöfe direkt an andere TF senden

Einzelne oder mehrere eigene Bahnhöfe auswählen (höchstens 50), „Auswahl an TF senden“ oder „Diesen Bahnhof an TF senden“ anklicken und den Empfänger aus der systeminternen TF-Liste auswählen. Angezeigt werden andere aktive TF ausschließlich mit Vor- und Nachname; gesperrte oder ausgetretene TF werden ausgeschlossen. Optional werden die Bahnhofspläne mitgegeben (zusammen höchstens 20 MB). Erst „An TF senden“ legt eine unabhängige Kopie in der Zwischenablage dieses Empfängers ab. Es wird keine E-Mail versendet.

Unter „Meine Zwischenablage“ sieht ausschließlich der Empfänger die Zusendungen mit Absender, Datum und DS100-Codes. „Ansehen“ zeigt Rufnummern und Pläne. Für jeden ausgewählten Bahnhof kann er einen neuen Eintrag unter dem ursprünglichen DS100-Code oder einen vorhandenen eigenen Zielbahnhof wählen. Bei vorhandenem gleichem DS100-Code ist dieser als Ziel vorbelegt. „Nur neue Bahnhöfe übernehmen“ überspringt vorhandene Ziele; „Neue übernehmen und vorhandene ergänzen“ ergänzt Kontakte und optional fehlende Pläne. Zielname und DS100, eigene Kontakte und bestehende Pläne bleiben erhalten. Identische Kategorie, Bezeichnung und Nummer werden nicht doppelt angelegt. Pro Übernahme darf ein Ziel nur einmal ausgewählt werden. Konflikte oder eine Überschreitung der Kontaktgrenze brechen die gesamte Auswahl ab; danach die Zusendung erneut öffnen.

Übernehmen entfernt die Zusendung nicht. Der Empfänger löscht sie mit „Zusendung löschen“ nach eigener Entscheidung; es gibt keinen automatischen Ablauf. Importierte Einträge bleiben erhalten. Spätere Änderungen des Absenders verändern die Kopie nicht. Andere TF und der Absender können die Zwischenablage nicht einsehen, importieren oder löschen.

Das normale Setup/Update legt zusätzlich tf_station_deliveries an; vorhandene Stationen, Kontakte und Pläne bleiben erhalten. Die früheren Linkfreigaben sind nicht mehr über die API abrufbar und müssen bei Bedarf neu an einen ausgewählten TF gesendet werden. Bereits daraus übernommene Daten bleiben erhalten. Zusendungen inklusive Plänen liegen in der Datenbank und werden mitgesichert. Die Suche nach DS100/Ort steht direkt unter „Meine Bahnhöfe“ oberhalb der Auswahl und Liste.


### Hinweise je Bahnhof

Beim Anlegen und Bearbeiten stehen „Lokabstellung“ und „Züge sichern“ mit jeweils höchstens 120 Zeichen sowie „Sonstige Besonderheiten“ mit höchstens 1024 Zeichen zur Verfügung. Das mehrzeilige Feld hat fünf sichtbare Zeilen und darüber einen dynamischen Restzeichenzähler. Die Angaben werden in der Ansicht angezeigt und zusammen mit dem Bahnhof als unveränderliche Kopie an andere TF gesendet. Bei der Übernahme werden nur leere Hinweisfelder des Zielbahnhofs ergänzt; vorhandene eigene Hinweise bleiben erhalten. Die Vorschau zeigt die eingegangenen Texte vollständig.

Das normale Update legt die zusätzlichen Tabellen tf_station_notes und tf_station_share_notes an. Vorhandene Bahnhöfe und ältere Zusendungen haben zunächst leere Hinweisfelder. Die bisherigen Daten bleiben unverändert; die neuen Tabellen werden über die bestehende Datenbanksicherung mitgesichert.


### Vertrauliche TF-Nummer

Die Empfängerauswahl liefert ausschließlich interne Datensatz-ID sowie Vor- und Nachname. Die Login-/TF-Nummer wird weder im Label noch in zusätzlichen API-Feldern an andere TF ausgeliefert; auch die Sortierung verwendet sie nicht. Zusendungen und Zwischenablagen enthalten keine TF-Nummer des Absenders oder Empfängers. Die eigene Identität bleibt für den jeweiligen TF sichtbar; administrative Stammdaten bleiben durch die bestehenden Verwaltungsrechte geschützt.

Die Bahnhofsfelder Lokabstellung, Züge sichern und Sonstige Besonderheiten stehen nach den Kontakten und dem Bahnhofsplan am Ende der Angaben, unmittelbar vor dem Speichern.

Automatisch versendete Quittungs-E-Mails enthalten ebenfalls keine Login-/TF-Nummer mehr. Die Zuordnung erfolgt über die Arbeitsbericht-ID.


### Bahnhöfe umbenennen

Beim Bearbeiten stehen DS100 (höchstens 10 Zeichen) und Bahnhofsname (höchstens 200 Zeichen) als freie Pflichtfelder bereit. DS100 wird ohne äußere Leerzeichen in Großbuchstaben gespeichert; beim Namen werden äußere Leerzeichen entfernt. Bei bereits vorhandenem DS100 oder gleichem Namen in der eigenen Liste erscheint ein Warnhinweis mit „Name oder DS100 ändern“. Die Eingaben bleiben erhalten, damit ein anderer Name oder Code gewählt werden kann. Namensvergleiche berücksichtigen Groß-/Kleinschreibung nicht. Andere TF haben unabhängige Listen.

Die Umbenennung behält die Eintrags-ID, Kontakte, Hinweise und den Bahnhofsplan bei. Die globale DS100-Stammdatenliste und bereits versendete Kopien werden nicht verändert. Nach dem Speichern werden Suche und sortierte Liste aktualisiert. Vorhandene ältere Clients können ohne Namens-/Code-Felder weiterhin Kontakte speichern; deren bisheriger Name und DS100 bleiben dabei erhalten. Keine zusätzliche Datenbankmigration erforderlich.


### Einheitliche Rückkehr ins TF-Portal

Alle Seiten der Standardoberfläche erhalten über den gemeinsamen Seitenstart (i18n.js → /tf/return.js) automatisch oben und unten im Hauptbereich einen Button „zurück TF-Portal“, sobald ein TF angemeldet ist. Das gilt auch für neue Module, die den üblichen Seitenaufbau mit main und i18n.js verwenden. Die Portal-Startseite selbst erhält keine Rückkehr-Buttons. Verwaltungs- und abgemeldete Benutzer erhalten diese TF-Navigation nicht. An-/Abmeldung und Sprachwechsel werden berücksichtigt. Die Buttons verwenden die normale Seitennavigation; bestehende Warnungen vor ungespeicherten Änderungen bleiben wirksam. Einzelne, zusätzliche Rückkehr-Links sollen nicht mehr in Modultemplates eingebaut werden.


### Ruhetagsplan aller TF in der Personalplanung

Die neue Gesamtübersicht oberhalb der Einzelplanung zeigt standardmäßig den aktuellen Monat (Berliner Datum). Jahr und Monat lassen sich separat wählen. „Monat: alle TF“ listet alle TF alphabetisch nach Nachname/Vorname untereinander mit sämtlichen Monatstagen als Spalten. „Jahr: alle TF“ zeigt dieselben Zeilen mit allen 365 bzw. 366 Tagen, nach Monaten gruppiert. Die Namen bleiben beim horizontalen Scrollen sichtbar; die Datumsköpfe bleiben beim vertikalen Scrollen sichtbar. Die Ansicht lässt sich auf mobilen Geräten in beide Richtungen scrollen.

R steht für Ruhetag, U für Urlaub, A für Arbeitstag, GT/GN für Grenzdienst Tag/Nacht und ? für ungeplant. Berliner Feiertage werden mit der jeweiligen Tagesart diagonal kombiniert; ungeplante Feiertage erscheinen violett. Wochenenden sind zusätzlich unterstrichen. Titel und zugängliche Zellbeschreibungen zeigen Datum, Name, Status und gegebenenfalls Feiertag und Schicht.

Die Gesamtübersicht verwendet ausschließlich die gespeicherten Einzelpläne über die bestehenden Planungs-APIs. Sie steht mit Lesefreigabe für Personalplanung zur Verfügung und enthält alle vorhandenen TF einschließlich Konten ohne gespeicherten Plan (deren Tage erscheinen ungeplant). Änderungen erfolgen weiterhin in der Einzelplanung. Ungespeicherte Entwürfe werden von der Übersicht nicht übernommen oder verworfen. „Aktualisieren“ lädt die TF-Liste und Planungsdaten neu. Erfolgreiches Speichern oder Übernehmen eines Excel-Imports aktualisiert die Übersicht ebenfalls. Die Jahresübersicht lädt höchstens vier TF-Pläne gleichzeitig; fehlgeschlagene Anfragen zeigen einen Fehler statt einer unvollständigen Tabelle. Keine Datenbankänderung erforderlich.


### Triebfahrzeuge verwalten

Im Verwaltungsmenü unter Administration → Triebfahrzeuge stehen Übersicht, Suche nach Fahrzeugnummer/Baureihe/Name/Leasing-Geber, Statusfilter sowie Anlegen und Bearbeiten bereit. Das neue Modulrecht vehicles („Triebfahrzeuge“) wird in der Verwaltungsmitarbeiter-Maske automatisch angeboten: Lesen erlaubt Übersicht und Ansicht; Lesen/Schreiben sowie Administration erlauben zusätzlich Anlegen und Bearbeiten. Administratoren erhalten automatisch Vollzugriff. Vorhandene Verwaltungsmitarbeiter benötigen eine ausdrückliche Freigabe für das neue Modul.

Die Fahrzeugnummer wird als zwölf Ziffern in den Gruppen 2–2–4–3–1 erfasst und im Format 00 00 0000 000-0 gespeichert. Führende Nullen bleiben erhalten; Nummern sind eindeutig. Der Status verwendet stabile Codes ready, unavailable und limited mit gemeinsam definierten Beschriftungen/Farben in der API. Nicht einsatzbereit benötigt einen Grund, eingeschränkt einsatzbereit eine Einschränkung (je höchstens 1024 Zeichen). Einsatzbereit entfernt den zuvor gespeicherten Statushinweis.

Baureihe (120), Leasing-Geber (200), Hotline (60), Name (120) und Leistung in kW (40 Zeichen) werden als Text gespeichert. Bremsgewichte R/P/G und Federspeicher sind ganze Zahlen von 0 bis 999. G−25 % wird ausschließlich abgeleitet: G × 75 // 100; beispielsweise 101 → 75 und 999 → 749. Der Wert ist nicht editierbar und wird auch serverseitig berechnet. Federspeicher unterstützt t oder kN. Die nächste Revision ist ein optionales Datum, der Kilometerstand liegt zwischen 0 und 9.999.999. Hinweise unterstützen mehrere Zeilen bis 4096 Zeichen.

Einträge werden über Revisionsnummern vor Überschreiben zwischenzeitlicher Änderungen geschützt. Nicht gespeicherte Änderungen lösen beim Verlassen eine Rückfrage aus. Das normale Setup/Update legt railway_vehicles an; Fahrzeugdaten sind anschließend Teil der normalen Datenbanksicherung. Es ist kein separater Import oder manueller SQL-Schritt erforderlich.


Die Triebfahrzeugliste zeigt genau Status, Fahrzeugnummer und Name. Der Status wird mit einem grünen, roten bzw. gelben Kreis über dem ausgeschriebenen Statustext dargestellt. Oberhalb steht „Hinzufügen“ für Benutzer mit Schreibrecht. Ein Klick auf eine beliebige Stelle einer Zeile lädt die aktuellen Fahrzeugdaten direkt zur Bearbeitung; die Fahrzeugnummer ist zusätzlich als per Tastatur bedienbare Schaltfläche erreichbar. Benutzer mit ausschließlichem Leserecht öffnen dieselbe Maske schreibgeschützt. Der Menüpunkt „Triebfahrzeuge“ befindet sich im Backend-Menü unter Administration und ist mit Modulfreigabe sichtbar.
