# GPS-Browsertest und kostenloses HTTPS auf dem Demo-Server

Für **ctl-software.io-goerlitz.eu / 212.227.86.251**, Ubuntu, Apache und vorhandenes Host-MySQL. Die Einrichtung aktualisiert die bestehende Installation einschließlich Datenbanksicherung. Bestehende Berichte bleiben erhalten. Keine neue Testdatenbank anlegen und keine TF-Daten zurücksetzen.

Let's Encrypt stellt kostenlose Zertifikate bereit. Certbot, die Browser-GPS-Funktion und die verwendeten OpenStreetMap-Daten benötigen keinen kostenpflichtigen API-Schlüssel. Die bereits vorhandenen Kosten für Server, Domain und Internet bleiben bestehen. Öffentliche Overpass-Abfragen sind für diesen kleinen Test vorgesehen und können zeitweise begrenzt werden. Für regelmäßigen größeren Betrieb ist ein eigener OSM-Datendienst einzuplanen.

## 1. Vorher lokale Arbeitsberichte synchronisieren

Noch unter der bisherigen HTTP-Adresse alle lokal gespeicherten Arbeitsberichte mit dem Server synchronisieren. Der Browser verwaltet HTTP und HTTPS als getrennte Ursprünge: lokale Browserentwürfe werden beim Wechsel nicht automatisch übernommen. Bei Bedarf vorher zusätzlich sichern. Danach die folgende Einrichtung ausführen.

## 2. Auf dem Ubuntu-Server anmelden und aktualisieren

Auf dem Mac im Terminal; `DEIN_SSH_BENUTZER` durch deinen Serverbenutzer ersetzen:

```bash
ssh DEIN_SSH_BENUTZER@212.227.86.251
```

Ab hier im Terminal auf dem Ubuntu-Server:

```bash
cd /opt/LokZeitleiste
git branch --show-current
git status --short
git pull --ff-only origin setup/debian-testumgebung
```

Die Branch-Ausgabe muss `setup/debian-testumgebung` sein. Bei lokalen Änderungen oder Git-Fehlern diese zuerst klären; keine Dateien mit `reset --hard` verwerfen.

## 3. DNS prüfen

```bash
dig +short A ctl-software.io-goerlitz.eu
dig +short AAAA ctl-software.io-goerlitz.eu
ip -6 addr show scope global
```

Der A-Eintrag muss **212.227.86.251** ergeben. Falls `dig` fehlt:

```bash
sudo apt-get update
sudo apt-get install -y dnsutils
```

Ein AAAA-Eintrag darf nur bestehen, wenn diese IPv6-Adresse auf genau diesem Server eingerichtet ist und die Domain über IPv6 auf denselben Apache erreichbar ist. Früher wurde `2a02:2479:58:ac00::1` angezeigt: das ausdrücklich mit der tatsächlichen Serverkonfiguration vergleichen. Ist IPv6 nicht eingerichtet, nur den AAAA-Eintrag **ctl-software.io-goerlitz.eu** beim zuständigen DNS-Anbieter beziehungsweise in der autoritativen BIND-Zone entfernen; keine anderen Hosts ändern. Nach DNS-Änderungen die TTL abwarten und erneut prüfen. Die Setup-Routine verändert DNS ohne `--bind-update` nicht.

## 4. Ports freigeben und Vorprüfung ausführen

Im Firewall-Bereich des Serveranbieters eingehend **TCP 80 und TCP 443** für diesen Server freigeben. Bei vorhandenem AAAA auch IPv6 berücksichtigen. Die bestehende SSH-Freigabe beibehalten.

Lokale Firewall prüfen:

```bash
sudo ufw status verbose
```

Nur wenn UFW bereits aktiv ist, zusätzlich ausführen:

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

UFW hierfür nicht neu aktivieren. Anschließend:

```bash
cd /opt/LokZeitleiste
sudo bash setup-demo.sh --https --check
```

Fehler bei DNS, Datenbank oder Ports zuerst beheben. Port 8000 ist der interne Anwendungsdienst; diesen nicht für GPS öffentlich freigeben.

## 5. Kostenloses HTTPS installieren

```bash
cd /opt/LokZeitleiste
sudo bash setup-https.sh
```

Die Routine fragt einmal nach deiner E-Mail-Adresse für das Let's-Encrypt-Zertifikatskonto. Sie installiert Certbot, beantragt ein kostenloses Zertifikat, akzeptiert dafür die Let's-Encrypt-Nutzungsbedingungen, richtet Apache ein und schaltet die Anwendung auf HTTPS um. Es ist weder eine Zahlung noch eine Kreditkarte nötig. Die Konto-E-Mail wird mit root-Rechten für spätere Updates gespeichert.

Alternativ ohne Rückfrage, mit deiner tatsächlichen Adresse statt des Platzhalters:

```bash
sudo bash setup-https.sh --email DEINE_EMAILADRESSE
```

Zertifikate und Schlüssel bleiben in `/etc/letsencrypt`. TCP 80 muss für die automatische HTTP-01-Verlängerung erreichbar bleiben. HTTP-Aufrufe werden nach der Einrichtung auf HTTPS umgeleitet.

## 6. Funktion und automatische Verlängerung prüfen

```bash
sudo apache2ctl configtest
curl -I https://ctl-software.io-goerlitz.eu/tf
curl --fail https://ctl-software.io-goerlitz.eu/health
sudo systemctl status certbot.timer --no-pager
sudo certbot renew --dry-run
```

`Syntax OK`, eine gültige HTTPS-Antwort und eine erfolgreiche Testverlängerung werden erwartet. `/tf` kann ohne Anmeldung zur Anmeldung umleiten. Bei Zertifikatsfehlern keine Browser-Ausnahme bestätigen und kein `curl -k` verwenden, sondern die Ursache beheben.

Im Browser öffnen und neu anmelden:

**https://ctl-software.io-goerlitz.eu/tf**

## 7. Eine Zugfahrt aufzeichnen

1. Standortdienste im Betriebssystem einschalten. Die HTTPS-Seite im Browser öffnen und die Standortfreigabe erlauben. Für verwertbare Tests ein GPS-fähiges Smartphone im Freien verwenden; Laptop-Standortbestimmung kann zu ungenau sein.
2. Im TF-Portal **Arbeitsbericht** öffnen, einen neuen Bericht erstellen und Dienstzeiten eintragen.
3. **Zugfahrt hinzufügen**, die Zugnummer eingeben. Danach wird **Zugfahrt per GPS aufzeichnen** bedienbar.
4. Button drücken und die Standortfreigabe bestätigen. Die Seite fordert ungefähr alle fünf Sekunden eine genaue Position an und speichert sie laufend im Browser. Wenn unterstützt, wird eine Bildschirmsperre über Screen Wake Lock verhindert; das ist keine Garantie.
5. **Tab sichtbar und Bildschirm eingeschaltet lassen.** Währenddessen nicht zu einem anderen Bericht wechseln. Tunnel, Energiesparen, Bildschirmsperre oder Browserwechsel können GPS-Lücken verursachen. Die aktuelle Browser-Testversion verspricht keine Hintergrundaufzeichnung bei gesperrtem Telefon. Eine spätere native Android-Funktion kann dafür einen eigenen Standortdienst erhalten.
6. Am Ziel **GPS-Aufzeichnung beenden** drücken. Die Positionen werden separat zum Arbeitsbericht synchronisiert, anschließend werden ZMS-Vorschläge geladen. Arbeitsbericht wie gewohnt separat speichern und synchronisieren.
7. Die Liste zeigt Start, erkannte Halte und Ende mit **Von / Bis / Dauer**. Halt bedeutet streng **unter 3 km/h und länger als fünf Minuten**. Genau fünf Minuten oder genau 3 km/h zählen nicht als Halt. Der Beginn und das Ende eines Halts beziehen sich auf die gemessenen langsamen Positionen.
8. Messlücken über 30 Sekunden und Positionsgenauigkeit schlechter als 50 Meter unterbrechen die Halterkennung. Diese Bereiche sind als Lücken beziehungsweise ungenaue Positionen sichtbar und werden nicht als Standzeit aufgefüllt. Der Streckenverlauf und der GPX-Export trennen solche Abschnitte ebenfalls.
9. ZMS-Vorschläge prüfen. Die Anwendung nutzt die OSM-Grunddaten, auf denen auch OpenRailwayMap beruht, und gleicht deren Kennungen mit dem vorhandenen DS100-Verzeichnis ab. In Fahrtrichtung gelegene Betriebsstellen in bis zu zwei Kilometern Entfernung werden bevorzugt; unmittelbar am Standort liegende Betriebsstellen bleiben auswählbar. Ohne erkennbare Bewegungsrichtung steht **Fahrtrichtung unbekannt**. Bahnhof/DS100 bei Bedarf per Suche korrigieren und **ZMS und Gründe speichern** drücken. Es werden keine DS100-Kürzel erfunden.
10. In jeder Zeile kann unter **Grund** derselbe Grund wie bei Zugfahrtereignissen gewählt werden. Bei **sonstiges** die Beschreibung mit maximal 256 Zeichen ergänzen. Die Auswahl wird lokal zwischengespeichert; **ZMS und Gründe speichern** übernimmt Betriebsstellen und Gründe auf den Server.
11. **GPX herunterladen** exportiert die Strecke. Standzeiten werden nicht automatisch als Pause eingetragen. Die Daten bleiben dem angemeldeten TF zugeordnet; andere TF erhalten darauf keinen Zugriff.

Die schematische Streckenanzeige benötigt keine Kartenkacheln oder kostenpflichtige Bibliothek. Die Datenquelle wird mit OpenStreetMap/ODbL ausgewiesen. Standortvorschläge sind keine gesicherte betriebliche Ortung und müssen insbesondere bei parallelen Gleisen oder dicht beieinanderliegenden Betriebsstellen geprüft werden.

### Unterbrechung und fehlendes Netz

GPS kann ohne Internet weiter lokal gespeichert werden, solange die geöffnete Seite weiter Positionsdaten erhält. Die Auswertung und ZMS-Zuordnung erfolgen über den Server, sobald Netz vorhanden ist. **GPS synchronisieren** beziehungsweise **ZMS-Vorschläge laden** erneut drücken. Nicht Browserdaten löschen oder den privaten Browsermodus verwenden. **GPS-Serverstand laden** überschreibt lokale Änderungen erst nach Rückfrage.

Nach einem Seitenneuladen kann ein lokaler unvollständiger Track **fortgesetzt oder beendet** werden. Zeiten ohne Messpunkte bleiben Lücken. Pro Zugfahrt sind maximal 20.000 Positionen beziehungsweise 48 Stunden vorgesehen; bei fünf Sekunden Abtastung wird die Punktgrenze nach ungefähr 27 Stunden erreicht. Vor einem bewussten Ersetzen eines Tracks bei Bedarf GPX sichern.

## 8. Spätere Updates

```bash
cd /opt/LokZeitleiste
git pull --ff-only origin setup/debian-testumgebung
sudo bash setup-https.sh
```

Auch `sudo bash setup-demo.sh` erhält eine bereits eingerichtete HTTPS-Konfiguration. `--http` ist ein ausdrücklicher Wechsel zurück auf HTTP; dort funktioniert Browser-GPS auf dieser öffentlichen Domain nicht.

## Fehler eingrenzen

- **Zertifikatsbeantragung fehlgeschlagen:** A/AAAA und öffentliche Ports 80/443 prüfen. `sudo journalctl -u apache2 --since '15 minutes ago'` und `/var/log/letsencrypt/letsencrypt.log` ansehen.
- **GPS fehlt oder wurde abgelehnt:** HTTPS ohne Zertifikatsfehler, Standortfreigabe für genau diese Domain und Betriebssystem-Standortdienste prüfen. Nach verweigerter Berechtigung diese in den Website-Einstellungen erlauben und Aufnahme fortsetzen.
- **Nur ungenaue Positionen:** im Freien auf einem GPS-fähigen Gerät erneut testen. Ungenaue Standortdaten werden bewusst nicht zu Halten erklärt.
- **ZMS-Dienst beschäftigt / Daten nicht verfügbar:** Track bleibt gespeichert. Später erneut Vorschläge laden oder DS100 manuell suchen. Öffentliche Overpass-Instanzen haben Kapazitätsgrenzen; kein kostenpflichtiger Dienst wird automatisch aktiviert.
- **Lokale Entwürfe fehlen nach HTTPS-Wechsel:** diese gehören zum bisherigen HTTP-Ursprung. Deshalb vor der Umstellung synchronisieren; serverseitige Berichte bleiben nach neuer Anmeldung vorhanden.

## Offizielle Grundlagen

- https://letsencrypt.org/getting-started/
- https://letsencrypt.org/docs/challenge-types/
- https://letsencrypt.org/docs/ipv6-support/
- https://certbot.eff.org/
- https://www.w3.org/TR/geolocation/
- https://wiki.openstreetmap.org/wiki/Overpass_API
- https://wiki.openstreetmap.org/wiki/OpenRailwayMap/API
- https://www.openstreetmap.org/copyright
