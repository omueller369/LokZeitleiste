# Eine Setupdatei: install-ctl-software.sh

Die Datei installiert LokZeitleiste inklusive 20 Test-TF mit Bildern auf einem **bereits mit ISPConfig eingerichteten Ubuntu-Server**. Alle Setup-Hilfsprogramme sind in dieser einen Datei enthalten. Der Anwendungscode wird bei Bedarf automatisch aus dem Projekt-Repository geladen.

## Vorbereitung in ISPConfig

- Die gewünschte Subdomain muss bereits als Website oder Website-Alias aktiv sein und per DNS auf diesen Server zeigen.
- Eine **eigene, leere MariaDB-/MySQL-Datenbank** mit zugeordnetem Datenbankbenutzer anlegen. Die vollständigen Namen einschließlich ISPConfig-Präfix bereithalten.
- Bei HTTPS das Zertifikat bereits in ISPConfig einrichten. Für den ersten HTTP-Test ist kein Zertifikat nötig.

## Datei herunterladen und starten

Nur die eine Datei herunterladen:

```bash
curl --fail --location \
  https://raw.githubusercontent.com/omueller369/LokZeitleiste/setup/debian-testumgebung/install-ctl-software.sh \
  --output install-ctl-software.sh
sudo bash install-ctl-software.sh
```

Alternativ die Datei aus GitHub im Browser herunterladen und auf den Server kopieren. In einem aktuellen Projekt-Checkout genügt ebenfalls `sudo bash install-ctl-software.sh`.

Die Routine fragt ab:

1. bestehende Subdomain ohne Protokoll/Pfad;
2. MariaDB-Datenbankname inklusive ISPConfig-Präfix;
3. MariaDB-Benutzername inklusive Präfix;
4. Datenbankhost, standardmäßig `127.0.0.1`;
5. HTTP oder HTTPS, standardmäßig **HTTP**;
6. vorhandenen Webserver Apache oder nginx;
7. internen API-Port, standardmäßig `18080`;
8. das Datenbankpasswort – **verdeckt**, ohne Übergabe als Kommandozeilenargument.

Wenn die Datei ohne sudo gestartet wurde, fordert sie die sudo-Rechte selbst an. Das sudo-Passwort und das anschließend abgefragte Datenbankpasswort sind unterschiedliche Zugangsdaten.

## Was automatisch eingerichtet wird

- Fehlende Pakete: `python3`, `python3-venv`, `python3-pip`, `git`, `ca-certificates`, `fonts-dejavu-core`. Das Script verwendet dafür `apt-get` mit Root-/sudo-Rechten. Es führt kein allgemeines Systemupgrade durch.
- Die Anwendung benötigt Python ab 3.11; auf älteren Ubuntu-Ausgaben mit älterem Standard-Python bricht sie mit einem Hinweis ab. Ubuntu 24.04 oder neuer verwenden.
- Bei Apache werden bei Bedarf die **vorhandenen** Module `proxy`, `proxy_http` und `headers` aktiviert, die Konfiguration geprüft und Apache neu geladen. Keine neue Apache-Installation.
- Isolierte Python-Abhängigkeiten der Anwendung, systemd-Dienste, Dokumentverzeichnisse, Datenbanktabellen und Grundwerte.
- Ein Admin mit zufälligem Passwort sowie die vorhandenen 20 Test-TF inklusive Bildern. Neue TF haben das Initialpasswort `tomcom123456` und müssen es beim ersten Login ändern.

**Apache/nginx, MariaDB, PHP und ISPConfig werden nicht neu installiert.** Bestehende Datenbanken werden nicht gelöscht. Eine nicht leere Datenbank und bereits vorhandene Anwendungsinstallationen werden abgelehnt.

Wenn die Datei innerhalb eines aktuellen Projekt-Checkouts liegt, verwendet sie diesen. Andernfalls klont sie das Projekt nach `/opt/ctl-software-source`, falls dieses Verzeichnis noch nicht vorhanden ist. Ein ausdrücklich gewählter aktueller Checkout kann mitgegeben werden:

```bash
sudo bash install-ctl-software.sh --source /opt/LokZeitleiste
```

Vorhandene Quelltextverzeichnisse werden nicht automatisch per Git zurückgesetzt oder aktualisiert.

## Einmalig die bestehende Subdomain weiterleiten

Nach erfolgreicher Anwendungsinstallation:

```bash
sudo cat /etc/lokzeitleiste-ispconfig/ispconfig-directives.conf
```

Den erzeugten Inhalt in **ISPConfig → Website → Optionen → Apache-/nginx-Direktiven** übernehmen und speichern. Das Script verändert keine von ISPConfig erzeugten VirtualHost-Dateien direkt und benötigt keine ISPConfig-API-Zugangsdaten. Bei nginx muss der angegebene Root-Location-Block die vorhandene Root-Location ersetzen; nicht zwei Root-Locations parallel eintragen. Die genaue Einbindung und die Prüfkommandos stehen in [der ausführlichen ISPConfig-Anleitung](SETUP-ISPCONFIG.md#5-website-mit-der-anwendung-verbinden).

Danach `http://DEINE-SUBDOMAIN/health` bzw. die gewählte HTTPS-Adresse aufrufen. Erwartet wird `{"status":"ok"}`. Die API ist intern unter `http://127.0.0.1:18080/health` erreichbar.

## Zugangsdaten und Fortsetzung

```bash
sudo cat /etc/lokzeitleiste-ispconfig/admin-initial-password
sudo cat /etc/lokzeitleiste-ispconfig/demo-tf.json
```

Adminname ist `admin`. Die zweite Datei enthält die Login-TF-Nummern der Testpersonen. Laufzeitkonfiguration und Daten liegen an denselben Orten wie in [SETUP-ISPCONFIG.md](SETUP-ISPCONFIG.md). Echter SMTP-Versand ist zunächst deaktiviert; es wird kein zusätzlicher Mailserver installiert.

Eine unterbrochene eigene Neuinstallation lässt sich nach Behebung des Fehlers fortsetzen:

```bash
sudo bash install-ctl-software.sh --resume
```

Die gespeicherten Installationswerte und Passwörter bleiben dabei erhalten. Eine bereits vollständig abgeschlossene Installation wird nicht erneut angelegt; diese Datei ist eine Neuinstallationsroutine, kein Update-Script.

Für die Weiterentwicklung wird die Setupdatei mit `python3 tools/build-ispconfig-installer.py` aus dem gemeinsamen Installer und seinem Hilfsprogramm erzeugt. Anwender benötigen dieses Werkzeug und die separaten Setup-Pythondateien nicht.
