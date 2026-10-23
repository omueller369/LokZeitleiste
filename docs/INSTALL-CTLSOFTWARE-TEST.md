# Vollständiger CTL-Testserver auf frischem Ubuntu 26.04

**Datei: `install-ctlsoftware-test.sh`**. Sie enthält die gesamte Setup-Logik; die Anwendung wird bei Bedarf aus dem Projekt-Repository geladen. Diese Routine ersetzt die vorausgesetzte ISPConfig-Umgebung durch einen selbst eingerichteten Server-Stack. Sie ist ausschließlich für einen frischen Server vorgesehen und lehnt vorhandenes ISPConfig, vorhandene Mail-/Datenbankinstallationen und belegte Anwendungsports ab.

## Festgelegte Werte

| Einstellung | Wert |
| --- | --- |
| Domain und Mailservername | `ctl-software.io-goerlitz.de` |
| Öffentliche IPv4 | `212.227.86.251` |
| MariaDB-Datenbank | `db_ctl` |
| MariaDB-Benutzer | `dbo_ctl` |
| Datenbankpasswort | Wird verdeckt eingegeben und zur Bestätigung wiederholt |
| Gmail-Weiterleitung | `omueller369@gmail.com` |
| Interner Anwendungsport | `127.0.0.1:18080` |

Die Server-IP muss bereits auf einem lokalen Netzwerkinterface konfiguriert sein. Diese Routine nimmt keine Netzwerkkarten-/NAT-Konfiguration vor. Sie veröffentlicht keine AAAA-Einträge und verwendet SMTP über IPv4.

## Start

Auf dem **frisch installierten Ubuntu 26.04**, nicht auf der bisherigen laufenden Umgebung:

```bash
curl --fail --location \
  https://raw.githubusercontent.com/omueller369/LokZeitleiste/setup/debian-testumgebung/install-ctlsoftware-test.sh \
  --output install-ctlsoftware-test.sh
sudo bash install-ctlsoftware-test.sh
```

Falls curl noch fehlt, die einzelne Datei im Browser herunterladen und per SCP/SFTP auf den Server kopieren. Das Script benötigt keinen vorherigen Repository-Checkout. Alternativ innerhalb eines aktuellen Checkouts starten oder `--source /Pfad/zum/Projekt` verwenden.

Das Script fragt nur das neue Passwort für `dbo_ctl` ab. Mindestens sechs Zeichen verwenden; Sonderzeichen werden als Datenbankparameter verarbeitet. Passwörter werden nicht als Prozessargumente übergeben. Die private Wiederaufnahmedatei liegt root-lesbar unter `/etc/ctlsoftware-test-setup/database-password`.

## Automatische Einrichtung

- Installation der Server- und Anwendungsabhängigkeiten über Ubuntu-Pakete: Apache, MariaDB, BIND, Postfix, Dovecot, OpenDKIM, PostSRSd, Certbot, UFW, Python und Hilfswerkzeuge.
- Apache mit HTTP-ACME-Pfad, öffentlich gültigem TLS-Zertifikat und HTTPS-Weiterleitung zur CTL-Anwendung. Certbot erhält `omueller369@gmail.com` als Kontaktadresse.
- MariaDB nur an `127.0.0.1`; Benutzer `dbo_ctl` erhält Rechte innerhalb `db_ctl`, keine globalen Administratorrechte.
- BIND als autoritativer Nameserver für **nur diese Subdomain**, ohne öffentliche Rekursion. A-, NS-, MX-, SPF-, DKIM- und DMARC-Einträge werden angelegt. Es wird nicht die übergeordnete Zone `io-goerlitz.de` überschrieben.
- Postfix für SMTP-Empfang und authentifizierten Versand, Dovecot 2.4 für IMAP, Authentifizierung und lokale Zustellung. OpenDKIM signiert eigene ausgehende Nachrichten. PostSRSd verwendet die 2.x-Socketmap-Schnittstelle zur Absenderumschreibung bei Weiterleitungen.
- Vier virtuelle Postfächer, ohne eigene Linux-Login-Konten. Passwörter stehen gehasht in einer root-/Dovecot-lesbaren Datei. Die Sieve-Regel führt sowohl `redirect` als auch ausdrücklich `keep` aus.
- UFW-Freigaben für die Dienste. Die tatsächlich konfigurierte SSH-Portnummer wird vorher ermittelt und freigegeben; vorhandene SSH-Schlüssel werden nicht ersetzt.
- CTL-Anwendung, Datenbanktabellen, Grundwerte, Admin mit Zufallspasswort, Dokumentverzeichnisse sowie die vorhandenen **20 Test-TF mit Bildern**.
- SMTP-/IMAP-Standardserver in der Anwendung und SMTP-Versand über `info@ctl-software.io-goerlitz.de`.

## Öffentliche DNS-Voraussetzungen

Das Script überprüft die öffentlichen Antworten bei zwei DNS-Resolvern. Ein bestehender A-Eintrag auf die Server-IP ist **keine NS-Delegation**. Damit BIND auf dem neuen Server für die erzeugten Einträge zuständig ist, muss beim Provider die entsprechende Delegation bestehen:

```dns
ctl-software.io-goerlitz.de.      NS  ns1.ctl-software.io-goerlitz.de.
ns1.ctl-software.io-goerlitz.de.  A   212.227.86.251
```

Der Provider muss dabei den nötigen Glue-Eintrag für den unterhalb der delegierten Zone liegenden Nameserver veröffentlichen. Der **PTR-/Reverse-DNS-Eintrag** wird im Serverprovider-Panel gesetzt:

```text
212.227.86.251 → ctl-software.io-goerlitz.de
```

Eine lokale BIND-Reverse-Zone kann diesen Provider-PTR nicht ersetzen. Die geplanten Provider-Einträge werden zusätzlich unter `/etc/ctlsoftware-test-setup/provider-dns.txt` gespeichert. Falls Delegation, sichtbarer MX/DKIM oder PTR noch fehlen, hält die Routine mit einer konkreten Fehlermeldung an. Nach DNS-Korrektur/Propagation:

```bash
sudo bash install-ctlsoftware-test.sh --resume
```

Auch eine externe Provider-Firewall muss die unten genannten öffentlichen Ports zulassen. Das Script kann nur die lokale UFW konfigurieren. Ein vorhandener AAAA-Eintrag muss entfernt werden, solange kein passendes IPv6 eingerichtet ist. Alte DS-/DNSSEC-Einträge bei geänderter Delegation müssen durch die zuständige DNS-Verwaltung geprüft werden.

## Postfächer

| Vollständiger IMAP-/SMTP-Benutzername | Initialpasswort | Zustellung |
| --- | --- | --- |
| `info@ctl-software.io-goerlitz.de` | `tomcom123456` | Lokal speichern und an Gmail weiterleiten |
| `diso@ctl-software.io-goerlitz.de` | `tomcom123456` | Lokal speichern und an Gmail weiterleiten |
| `vkplanung@ctl-software.io-goerlitz.de` | `tomcom123456` | Lokal speichern und an Gmail weiterleiten |
| `railpool@ctl-software.io-goerlitz.de` | `tomcom123456` | Lokal speichern und an Gmail weiterleiten |

Weiterleitungsziel für alle vier: `omueller369@gmail.com`. Zusätzlich bestehen `postmaster`, `abuse` und `root` als Aliase auf `info`; diese sind keine zusätzlichen Login-Konten.

| Dienst | Host | Port | Sicherheit |
| --- | --- | --- | --- |
| IMAP | `ctl-software.io-goerlitz.de` | 993 | TLS/SSL |
| IMAP alternativ | derselbe Host | 143 | STARTTLS, vor Anmeldung erforderlich |
| SMTP-Versand | derselbe Host | 465 | TLS/SSL mit Anmeldung |
| SMTP-Versand alternativ | derselbe Host | 587 | STARTTLS mit Anmeldung |
| SMTP-Empfang von anderen Servern | derselbe Host | 25 | STARTTLS angeboten, kein offenes Relay |

DNS benötigt zusätzlich TCP **und** UDP 53; die Website TCP 80/443. MariaDB 3306 und API 18080 werden nicht öffentlich freigegeben.

## Abschluss und Kontrollen

Nach erfolgreicher Installation:

```text
https://ctl-software.io-goerlitz.de/admin/start
https://ctl-software.io-goerlitz.de/tf
```

```bash
sudo cat /etc/ctlsoftware-test/admin-initial-password
sudo cat /etc/ctlsoftware-test/demo-tf.json
sudo systemctl status ctlsoftware-test ctlsoftware-test-worker
sudo journalctl -u ctlsoftware-test -n 100 --no-pager
sudo journalctl -u dovecot -u postfix -u postsrsd -n 100 --no-pager
```

Admin-Benutzer ist `admin`. Die TF-Liste enthält die Login-TF-Nummern. TF-Initialpasswort ist `tomcom123456`, mit Passwortwechsel beim ersten Login. Die Mailkonten sind unabhängig von den TF-Benutzerkonten.

Das Script prüft Dienststatus, öffentliche HTTPS-API, verschlüsselte Anmeldung aller vier Konten, ausgehende TCP-25-Erreichbarkeit zu Gmail-MX und die Ablehnung einer unauthentifizierten externen Relay-Anfrage. Dabei wird **keine Nachricht** an Gmail gesendet. Nach Abschluss selbst eine Nachricht an `info@ctl-software.io-goerlitz.de` senden und sowohl den IMAP-Eingang als auch den Gmail-Eingang prüfen. DNS/Signaturen ermöglichen Mailzustellung, können aber keine Annahme oder Posteingangsplatzierung durch Gmail erzwingen; insbesondere haben fremde Absender eigene DKIM-/DMARC-Regeln.

Konfigurationsdateien werden vor dem Ersetzen unter `/etc/ctlsoftware-test-setup/original-configs` gesichert. Anwendungskonfiguration liegt unter `/etc/ctlsoftware-test`, Benutzerdokumente unter `/var/lib/ctlsoftware-test`, Maildir-Postfächer unter `/var/vmail`. Bei Sicherungen diese Daten, Datenbank, Postfachpasswortdatei und die DKIM-/SRS-Schlüssel gemeinsam sichern.

`--resume` führt nur noch nicht abgeschlossene Schritte aus. Es löscht keine Datenbank und setzt keine fertig eingerichteten Testpersonen zurück. Nach vollständigem Abschluss lehnt die Routine eine erneute Installation ab; sie ist kein Update-Script.

Die Tests im Repository prüfen Konfigurationsgenerierung, feste Werte, Datenbankparameter, DNS-Abbruchbedingungen und die Wiederaufnahme mit simulierten Systemdiensten. Eine vollständige Ausführung auf einer realen Ubuntu-26.04-VM und eine echte Gmail-Zustellung sind damit nicht nachgewiesen. Zur Weiterentwicklung die einzelne Datei mit `python3 tools/build-fresh-test-installer.py` neu erzeugen.

## Technische Referenzen

- [Dovecot 2.4 Quick Configuration](https://doc.dovecot.org/2.4.2/core/config/quick.html)
- [Dovecot passwd-file](https://doc.dovecot.org/2.4.2/core/config/auth/databases/passwd_file.html)
- [Dovecot Sieve](https://doc.dovecot.org/2.4.2/core/plugins/sieve.html)
- [PostSRSd 2.x](https://github.com/roehling/postsrsd)
- [Ubuntu-26.04-Paket PostSRSd](https://packages.ubuntu.com/resolute/postsrsd)

## phpMyAdmin und kostenloser Webmailer

Das gleiche Script installiert PHP-FPM samt MySQL-, SQLite-, XML-, mbstring-, Intl-, Curl-, ZIP- und GD-Erweiterungen, phpMyAdmin und Roundcube aus Ubuntu-Paketen.

| Anwendung | Adresse | Anmeldung |
| --- | --- | --- |
| phpMyAdmin | https://ctl-software.io-goerlitz.de/phpmyadmin | `dbo_ctl` und das beim Setup eingegebene Datenbankpasswort |
| Roundcube | https://ctl-software.io-goerlitz.de/webmailer | Vollständige Postfachadresse und `tomcom123456` |

Roundcube verwendet die vier oben genannten IMAP-/SMTP-Konten mit geprüften TLS-Verbindungen. Seine Kontakte und Einstellungen liegen in einer eigenen SQLite-Datenbank unter `/var/lib/ctl-webmail`; die Projektdatenbank bleibt getrennt. phpMyAdmin nutzt Cookie-Anmeldung, erlaubt keinen Root-Login und keine frei eingebbaren Datenbankserver. Die Apache-Routen werden vor der Weiterleitung an das Backend eingerichtet. HTTP wird auf HTTPS umgeleitet.

Die Abschlussprüfung kontrolliert zusätzlich PHP-FPM und beide Anmeldeseiten. Ein Browser-Login samt E-Mail-Versand wurde hier nicht auf einem echten Server geprüft.
