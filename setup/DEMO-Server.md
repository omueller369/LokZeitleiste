# Öffentliche Demo: ctl-software.io-goerlitz.eu

Ziel: **212.227.86.251**, **https://ctl-software.io-goerlitz.eu**. Die neue Routine `setup-demo.sh` baut auf der vollständigen Testinstallation auf und stellt sie per Apache/HTTPS bereit. Sie ist für einen dedizierten Ubuntu-Server **26.04 LTS / 26.04.1**, amd64 oder arm64, vorgesehen. Sie installiert kein neues Betriebssystem. Ein lokaler Teststack und diese Demo sollten in getrennten Servern/VMs laufen, da die Demo den Teststack dieses Projektverzeichnisses verwendet.

## Voraussetzungen beim Provider

- DNS-A-Record: `ctl-software.io-goerlitz.eu` → `212.227.86.251`. Weitere A-Records müssen entfernt/angepasst werden. Ein bestehender AAAA-Record muss zunächst entfernt werden, solange IPv6 nicht gesondert eingerichtet ist. DNS-Änderungen können verzögert sichtbar werden.
- Eingehend TCP **22** (bzw. eigener SSH-Port), **80** und **443** in der Provider-Firewall erlauben. Eine bereits aktive Host-Firewall muss die verwendeten Ports ebenfalls erlauben. Die Routine ändert keine Firewallregeln und schaltet die Firewall nicht ein oder aus.
- TCP 80 muss auch nach der Installation für die Zertifikatserneuerung erreichbar bleiben.
- Kein anderer Webserver darf Port 80/443 belegen. Bestehende andere Apache-Domains werden nicht deaktiviert; eine bereits vorhandene Konfiguration für diese Domain wird nicht ungefragt ersetzt.
- Eine eigene E-Mail-Adresse für das Let's-Encrypt-Zertifikatskonto bereithalten. Der Aufruf stimmt den Let's-Encrypt-Nutzungsbedingungen zu.

## Erstinstallation

Im Mac-/PC-Terminal mit dem vorhandenen Ubuntu-Administratorkonto verbinden. `BENUTZER` ersetzen; bei eingerichtetem Root-SSH ist auch `root` möglich:

```bash
ssh BENUTZER@212.227.86.251
```

Dann **auf dem Server**:

```bash
sudo apt update
sudo apt install -y git python3 openssh-server
sudo install -d -o "$USER" -g "$(id -gn)" /opt/LokZeitleiste
git clone --branch setup/debian-testumgebung --single-branch https://github.com/omueller369/LokZeitleiste.git /opt/LokZeitleiste
cd /opt/LokZeitleiste
sudo bash setup-demo.sh --check
sudo bash setup-demo.sh --email DEINE-EMAIL@BEISPIEL.DE
```

Die E-Mail-Adresse ersetzen. Ein privates GitHub-Repository erfordert GitHub-Zugang beim Klonen. Zugangsdaten nicht in die URL schreiben. `--check` prüft lesend DNS und die Voraussetzungen; noch fehlende Pakete werden erst beim eigentlichen Setup installiert.

Die Routine installiert Abhängigkeiten, baut/startet Docker-Dienste, richtet Datenbank, Benutzerverzeichnisse, Linux-Konten und Admin-Zugang ein, erstellt das Zertifikat und aktiviert HTTPS. Datenbank und API werden nicht direkt öffentlich veröffentlicht: Die API bindet an `127.0.0.1:8000`; der Zugriff erfolgt über Apache. Das Testpostfach bleibt unter `127.0.0.1:8025`. Origin wird auf `https://ctl-software.io-goerlitz.eu` gesetzt, Sitzungscookies werden nur über HTTPS gesendet.

HTTP leitet auf HTTPS um; vor Ausstellung des Zertifikats werden darüber ausschließlich die ACME-Challenges ausgeliefert. Zertifikatserneuerungen übernimmt `certbot.timer`, anschließend wird Apache neu geladen. Es wird nur `ctl-software.io-goerlitz.eu` eingerichtet, **kein** zusätzliches `www.ctl-software.io-goerlitz.eu`.

## Aufrufen und anmelden

- Administration: https://ctl-software.io-goerlitz.eu/admin
- TF-Portal: https://ctl-software.io-goerlitz.eu/tf
- Dokumente: https://ctl-software.io-goerlitz.eu/documents

Initialer Administrator: **administrator**, falls noch kein aktiver Admin existiert. Zufälliges Initialpasswort auf dem Server anzeigen:

```bash
sudo cat /var/lib/lokzeitleiste/admin-initial-password
```

Bei vorhandenen Admins werden die bisherigen Zugangsdaten beibehalten. Keine automatische Erstellung oder Zurücksetzung von Beispiel-TFs; Vorführkonten über die Administration mit eigenen Passwörtern anlegen.

## Test-E-Mails ansehen

Alle automatischen Test-E-Mails werden in Mailpit aufgefangen und nicht über einen realen SMTP-Provider versendet. Das Postfach wird nicht öffentlich freigegeben. Im Mac-/PC-Terminal:

```bash
ssh -N -L 8025:127.0.0.1:8025 BENUTZER@212.227.86.251
```

Dann http://localhost:8025 öffnen. Individuell eingerichtete externe E-Mail-Konten sind davon getrennt; deren Funktionen verbinden sich mit dem jeweiligen Anbieter.

## Aktualisieren

Auf dem Server im bisherigen Projektverzeichnis:

```bash
cd /opt/LokZeitleiste
git status --short
git pull --ff-only origin setup/debian-testumgebung
sudo bash setup-demo.sh --email DEINE-EMAIL@BEISPIEL.DE
```

Lokale Änderungen vorher sichern/committen. Bei vorhandener `.env.test` wird automatisch `setup-update.sh` ausgeführt: Sicherung von Datenbank, Dokumenten inklusive ACLs, Testkonfiguration und Zertifikaten unter `backend/testenv/backups/update-…/`, anschließend Migrationen/Archivumsortierung und Neubau. Die Admin-Passwörter bleiben erhalten. Kein Datenreset und kein automatischer Datenbank-Rollback. Let's-Encrypt-Dateien unter `/etc/letsencrypt` und die Apache-Konfiguration zusätzlich in die Server-Sicherung aufnehmen; diese liegen außerhalb des Projekt-Backups.

## Prüfen und Fehler finden

```bash
curl --fail https://ctl-software.io-goerlitz.eu/health
sudo bash backend/testenv/control.sh status
sudo bash backend/testenv/control.sh logs
sudo apache2ctl configtest
sudo systemctl status certbot.timer --no-pager
sudo systemctl status lokzeitleiste-users.timer --no-pager
sudo certbot renew --dry-run
sudo tail -n 100 /var/log/apache2/lokzeitleiste-ctl-demo-error.log
```

Ein Zertifikatsfehler deutet häufig auf DNS-/AAAA-Zuordnung, CAA-Regeln oder nicht erreichbaren Port 80 hin. Erst diese Ursache beheben und dann die Demo-Routine erneut starten. Für Google/Microsoft-OAuth im Anbieterportal Redirect-URLs passend zur öffentlichen Domain registrieren; `localhost`-Freigaben gelten dafür nicht automatisch.

Die Erstellung der Routine ist lokal geprüft. SSH-Zugriff, Provider-DNS, Firewall und der tatsächliche Installationslauf auf **212.227.86.251** wurden nicht durchgeführt.

Offizielle Dokumentation: [Certbot Webroot und Erneuerung](https://eff-certbot.readthedocs.io/en/stable/using.html), [Docker Port-Bindings](https://docs.docker.com/engine/network/port-publishing/).

## Vorhandene Apache- und BIND-Installation

Die Demo verwendet eigene VirtualHosts `lokzeitleiste-ctl-demo-http.conf` und `lokzeitleiste-ctl-demo-https.conf`. Vorhandene Websites, die Hauptdomain `io-goerlitz.eu` und andere BIND-Zoneneinträge werden nicht verändert. Apache wird nach erfolgreicher Konfigurationsprüfung neu geladen; ein Neustart von Apache oder BIND ist nicht vorgesehen. Mit `sudo apache2ctl -S` prüfen, ob ein bestehender Wildcard-VirtualHost die Subdomain bereits abfängt. Ein solches Alias gezielt in der bisherigen Konfiguration anpassen.

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
sudo bash setup-demo.sh --bind-update --email DEINE-EMAIL@BEISPIEL.DE
```

Die Option verwendet `nsupdate -l`, aktualisiert ausschließlich den A-Record von `ctl-software.io-goerlitz.eu` und bricht bei vorhandenem CNAME oder AAAA ab. BIND führt bei dynamischen Updates die Seriennummer selbst nach. Die Routine überschreibt weder `named.conf` noch Update-Policies oder andere Records. Ohne bestehende Update-Erlaubnis wird abgebrochen; dann den statischen Weg oder die vorhandene DNS-Verwaltung verwenden. `--check --bind-update` bleibt lesend und führt kein DNS-Update aus.

DNS und anschließend HTTPS prüfen:

```bash
dig @127.0.0.1 ctl-software.io-goerlitz.eu A
dig @1.1.1.1 ctl-software.io-goerlitz.eu A
sudo bash setup-demo.sh --check
curl --fail https://ctl-software.io-goerlitz.eu/health
```

Nach DNS-Änderungen zunächst deren Veröffentlichung abwarten und dann die Setup-Routine ausführen. Zertifikat, Weiterleitung und `PUBLIC_ORIGIN` werden ausschließlich für `ctl-software.io-goerlitz.eu` eingerichtet.
