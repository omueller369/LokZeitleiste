# HTTP-Demo: ctl-software.io-goerlitz.eu

Ziel: **212.227.86.251**, **http://ctl-software.io-goerlitz.eu**. Die Routine verwendet zunächst **HTTP ohne Zertifikat und ohne HTTPS-Weiterleitung**. Vorhandene Apache-Websites und BIND-Dienste werden weiterverwendet; die Hauptdomain bleibt unverändert. Ubuntu Server 26.04 LTS / 26.04.1, amd64 oder arm64, wird vorausgesetzt.

## DNS und Ports

Den A-Record `ctl-software.io-goerlitz.eu` auf `212.227.86.251` setzen. Für diesen Host keine abweichenden A-/CNAME-Einträge verwenden. AAAA-Einträge sind erlaubt, wenn die IPv6-Adressen lokal auf dem Server eingerichtet sind und TCP 80 auch über IPv6 erreichbar ist. TCP 80 und der verwendete SSH-Port müssen durch Provider- und Host-Firewall erreichbar sein. Die Routine ändert keine Firewallregeln. Port 443 und ein Zertifikatskonto sind für HTTP nicht erforderlich.

## Installation

Vom Mac/PC verbinden (`BENUTZER` ersetzen):

```bash
ssh BENUTZER@212.227.86.251
```

Auf dem Server:

```bash
sudo apt update
sudo apt install -y git python3 openssh-server
sudo install -d -o "$USER" -g "$(id -gn)" /opt/LokZeitleiste
git clone --branch setup/debian-testumgebung --single-branch https://github.com/omueller369/LokZeitleiste.git /opt/LokZeitleiste
cd /opt/LokZeitleiste
sudo bash setup-demo.sh --check
sudo bash setup-demo.sh
```

Bei privatem Repository die GitHub-Anmeldung beim Klonen verwenden. Eine vorhandene Installation nicht erneut klonen, sondern aktualisieren:

```bash
cd /opt/LokZeitleiste
git status --short
git pull --ff-only origin setup/debian-testumgebung
sudo bash setup-demo.sh
```

Lokale Änderungen vorher sichern/committen. Standardmäßig wird jetzt die vorhandene **MySQL-Installation auf dem Ubuntu-Host** verwendet. Beim ersten Start werden Benutzer (Standard `ctl-software`), Datenbank (Standard `ctl_software`) und Passwort abgefragt. Der Benutzer benötigt die Rechte zum Anlegen dieser Datenbank und zum Anlegen/Ändern/Lesen/Schreiben ihrer Tabellen. Die Routine verändert keine MySQL-Benutzer, Grants oder Serverkonfiguration. Verbindung: `127.0.0.1:3306`; kein zusätzlicher MySQL-Container wird gestartet. Die Datenbank wird nur mit `CREATE DATABASE IF NOT EXISTS` angelegt.

Die Verbindungsdaten liegen in `backend/.env.host` (Modus 600, nicht im Repository). Vor jedem Start mit Schemaänderungen wird ein Datenbank-Dump und eine Sicherung von Dokumenten/ACLs und Projektkonfiguration erstellt; bei Updates wird dafür API/Mailer kurz gestoppt. Bestehende Daten und Passwörter bleiben bestehen. Alte Docker-Testvolumes bleiben unangetastet und werden nicht automatisch in die Host-Datenbank importiert. Ein parallel laufender alter Teststack auf Port 8000/8025 muss vorab regulär gestoppt werden. Mit `--docker-mysql` lässt sich der bisherige Docker-Testdatenbankweg ausdrücklich auswählen. Zugangsdaten bleiben erhalten. Die Sicherungen liegen unter `backend/testenv/backups/update-…/`. Apache-/BIND-Konfigurationen zusätzlich in die vorhandene Server-Sicherung aufnehmen.

Die Routine setzt `PUBLIC_ORIGIN=http://ctl-software.io-goerlitz.eu` und `COOKIE_SECURE=false`, damit die Anmeldung über HTTP funktioniert. Ein zuvor von dieser Routine aktivierter Demo-HTTPS-VirtualHost wird deaktiviert; andere HTTPS-Sites und vorhandene Zertifikate bleiben erhalten. Cookies, Passwörter und Dokumente sind bei HTTP unverschlüsselt: für diese vorläufige Demo ausschließlich fiktive Daten und eigene Demo-Passwörter verwenden. Externe OAuth-Anbieter können HTTPS für Redirect-URLs verlangen.

## Aufrufen und prüfen

- Administration: http://ctl-software.io-goerlitz.eu/admin
- TF-Portal: http://ctl-software.io-goerlitz.eu/tf
- Dokumente: http://ctl-software.io-goerlitz.eu/documents

Bei erstmaliger Anlage lautet der Admin-Benutzer `administrator`; sein zufälliges Initialpasswort anzeigen:

```bash
sudo cat /var/lib/lokzeitleiste/admin-initial-password
curl --fail http://ctl-software.io-goerlitz.eu/health
sudo bash backend/testenv/control-host.sh status
sudo bash backend/testenv/control-host.sh logs
sudo apache2ctl configtest
sudo apache2ctl -S
sudo tail -n 100 /var/log/apache2/lokzeitleiste-ctl-demo-error.log
```

Vorhandene Admin-Zugangsdaten werden beibehalten. Die Routine erzeugt keine TFs mit bekannten Beispielpasswörtern. API und Testpostfach binden ausschließlich lokal; die Datenbank veröffentlicht keinen Hostport. Automatische Demo-E-Mails landen in Mailpit. Im Mac-/PC-Terminal dafür einen Tunnel öffnen:

```bash
ssh -N -L 8025:127.0.0.1:8025 BENUTZER@212.227.86.251
```

Danach http://localhost:8025 öffnen. Einzeln eingerichtete externe E-Mail-Konten verbinden sich unabhängig davon mit dem jeweiligen Anbieter.

## Später optional HTTPS einschalten

```bash
sudo bash setup-demo.sh --https --email DEINE-EMAIL@BEISPIEL.DE
```

Dafür zusätzlich TCP 443 öffnen und eine eigene E-Mail-Adresse einsetzen. Erst mit `--https` werden Certbot, Zertifikat, HTTP-Weiterleitung auf HTTPS und sichere Cookies eingerichtet. Der Aufruf stimmt den Let's-Encrypt-Nutzungsbedingungen zu. Certbot übernimmt die Erneuerung über seinen Timer. Ein erneuter Aufruf **ohne** `--https` schaltet diese Demo wieder auf HTTP.

Ein Browser kann eine frühere permanente HTTPS-Weiterleitung zwischengespeichert haben; gegebenenfalls Website-Daten für die Demo-Subdomain löschen und die HTTP-Adresse ausdrücklich neu öffnen. Eine von anderen Serverkonfigurationen gesetzte HSTS-Richtlinie einschließlich Subdomains kann HTTP im Browser verhindern.

Die Routine ist lokal geprüft; auf dem externen Server wurden keine Änderungen ausgeführt.

## Vorhandene Apache- und BIND-Installation

Die Demo verwendet eigene VirtualHosts `lokzeitleiste-ctl-demo-http.conf` auf Port 80. Vorhandene Websites, die Hauptdomain `io-goerlitz.eu` und andere BIND-Zoneneinträge werden nicht verändert. Apache wird nach erfolgreicher Konfigurationsprüfung neu geladen; ein Neustart von Apache oder BIND ist nicht vorgesehen. Mit `sudo apache2ctl -S` prüfen, ob ein bestehender Wildcard-VirtualHost die Subdomain bereits abfängt. Ein solches Alias gezielt in der bisherigen Konfiguration anpassen.

Für öffentlichen autoritativen DNS-Betrieb muss der vorhandene BIND über TCP und UDP 53 erreichbar und bei den zuständigen Nameservern der Domain eingebunden sein.

Der vorhandene BIND muss für die öffentliche Zone `io-goerlitz.eu` autoritativ sein, damit eine lokale Änderung im Internet wirksam wird. Läuft BIND nur als Resolver oder liegen die autoritativen Nameserver beim Provider, den A-Record stattdessen dort anlegen. Den Hauptdomain-A-Record nicht ändern.

### Statische BIND-Zone

Den tatsächlich geladenen Dateipfad zunächst ermitteln:

```bash
sudo rndc zonestatus io-goerlitz.eu
```

Die Zonendatei sichern und mit `sudoedit` bearbeiten. Im bisherigen `$ORIGIN io-goerlitz.eu.` folgenden Record ergänzen (bei anderem Origin den vollständigen Namen mit abschließendem Punkt verwenden):

```dns
ctl-software.io-goerlitz.eu. 300 IN A 212.227.86.251
```

Die **SOA-Seriennummer erhöhen**; vorhandene Records nicht ersetzen. Ein Muster liegt unter `setup/bind/ctl-software.zone.inc`. Danach mit dem tatsächlichen Dateipfad prüfen und ausschließlich diese Zone neu laden:

```bash
sudo named-checkzone io-goerlitz.eu /PFAD/ZUR/ZONENDATEI
sudo rndc reload io-goerlitz.eu
```

`/PFAD/ZUR/ZONENDATEI` ersetzen. Bei dynamischen oder DNSSEC-verwalteten Zonen nicht direkt in Journal-/Signaturdateien schreiben; das vorhandene Update-/Signierungsverfahren verwenden.

### Optional: bereits freigegebene lokale dynamische BIND-Updates

Wenn die vorhandene Zone lokale Updates über BINDs Session-Key erlaubt (beispielsweise bereits eingerichtetes `update-policy local;`), kann die Routine den einzelnen Host-A-Record selbst setzen:

```bash
sudo apt install -y bind9-dnsutils
sudo bash setup-demo.sh --bind-update
```

Die Option verwendet `nsupdate -l`, aktualisiert ausschließlich den A-Record von `ctl-software.io-goerlitz.eu` und bricht bei vorhandenem CNAME ab. AAAA-Records bleiben erhalten und werden anschließend gegen die lokalen IPv6-Adressen geprüft. BIND führt bei dynamischen Updates die Seriennummer selbst nach. Die Routine überschreibt weder `named.conf` noch Update-Policies oder andere Records. Ohne bestehende Update-Erlaubnis wird abgebrochen; dann den statischen Weg oder die vorhandene DNS-Verwaltung verwenden. `--check --bind-update` bleibt lesend und führt kein DNS-Update aus.

DNS und anschließend HTTP prüfen:

```bash
dig @127.0.0.1 ctl-software.io-goerlitz.eu A
dig @1.1.1.1 ctl-software.io-goerlitz.eu A
sudo bash setup-demo.sh --check
curl --fail http://ctl-software.io-goerlitz.eu/health
```

Nach DNS-Änderungen zunächst deren Veröffentlichung abwarten und dann die Setup-Routine ausführen. `PUBLIC_ORIGIN` und der HTTP-VirtualHost werden ausschließlich für `ctl-software.io-goerlitz.eu` eingerichtet.

## Meldung zum bestehenden AAAA-Eintrag

`2a02:2479:58:ac00::1` wird akzeptiert, wenn diese globale IPv6-Adresse lokal auf dem Server eingerichtet ist. Auf dem Server prüfen:

```bash
ip -6 addr show scope global
dig +short AAAA ctl-software.io-goerlitz.eu
```

Falls die Adresse nicht lokal vorhanden ist, nur den AAAA-Record **dieser Subdomain** korrigieren oder entfernen. IPv6 für andere Dienste nicht abschalten. Bei vorhandenem IPv6 auch die Firewall für TCP 80 berücksichtigen.

## Host-MySQL vorab prüfen

Auf dem Ubuntu-Server kann die Verbindung ohne Passwort in der Befehlszeile geprüft werden:

```bash
mysql --protocol=TCP -h 127.0.0.1 -u ctl-software -p -e "SELECT VERSION();"
```

Das Passwort erst bei der Abfrage eingeben. Ein `Access denied` bedeutet, dass Anmeldung oder TCP-Zugriffsrechte dieses Kontos geprüft werden müssen; die Routine verändert diese Rechte nicht automatisch. Nach erfolgreicher Erstinstallation verwendet sie die gespeicherte `.env.host` und fragt das Passwort nicht erneut ab.

Betrieb der Host-Datenbankvariante:

```bash
sudo bash backend/testenv/control-host.sh status
sudo bash backend/testenv/control-host.sh logs
sudo bash backend/testenv/control-host.sh stop
sudo bash backend/testenv/control-host.sh start
```

`stop` stoppt ausschließlich Anwendungscontainer und Mailpit, nicht den bestehenden MySQL-Server. `backup` erstellt eine Sicherung und lässt API/Mailer bis zum anschließenden `start` gestoppt. Es gibt keinen automatischen Import und kein `DROP DATABASE`. Auf dem Server wurde diese Variante noch nicht ausgeführt; geprüft sind Konfiguration, Zugangsdatenbehandlung und die vorbereiteten Befehle.
