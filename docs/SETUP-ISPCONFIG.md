# Neuinstallation auf Ubuntu mit vorhandenem ISPConfig

Diese Routine installiert **nur LokZeitleiste einschließlich 20 fiktiver TF mit Bildern**. Apache/nginx, MySQL/MariaDB, PHP, DNS, Mailserver, Docker und ISPConfig werden weder installiert noch neu konfiguriert. Sie verwendet eine bereits in ISPConfig angelegte Website und eine eigene leere Datenbank.

Sie ist für einen neuen Anwendungsstand gedacht und bricht bei vorhandenen Installationszielen oder einer nicht leeren Datenbank ab. Die bisherigen Routinen `setup-demo.sh`, `setup-new.sh` und `setup-update.sh` gehören zu den anderen Installationsarten und sind hierfür nicht zu verwenden.

## 1. Voraussetzungen

- Ubuntu mit bereits funktionsfähigem ISPConfig und Apache **oder** nginx.
- Root-/sudo-Zugriff für den Anwendungsdienst und dessen Benutzer ohne Shell-Login.
- Python ab 3.11 einschließlich `venv` und `ensurepip`. Fehlende Voraussetzungen meldet `--check`; das Script installiert keine Systempakete. Die Serveradministration muss diese bei Bedarf vorab bereitstellen.
- Internetzugriff für die Python-Abhängigkeiten aus `backend/requirements.txt`.
- Bei Apache müssen `proxy`, `proxy_http` und `headers` bereits aktiviert sein.
- Für vollständige Unicode-PDFs sind vorhandene DejaVu-Schriften unter `/usr/share/fonts/truetype/dejavu` empfehlenswert. Andernfalls verwendet die Software die mit ReportLab gelieferten Ersatzschriften.

## 2. Website und Datenbank in ISPConfig vorbereiten

1. Eine **eigene Website** für die gewünschte Subdomain anlegen, beispielsweise `ctl-software.io-goerlitz.eu`. Nicht die ISPConfig-Verwaltungsdomain und nicht eine bestehende fremde Website verwenden. PHP ist für LokZeitleiste nicht erforderlich.
2. Den DNS-Eintrag dieser Subdomain auf den **neuen** Server zeigen lassen. Vorhandene IPv6-Einträge müssen ebenfalls zu diesem Server passen.
3. Für HTTPS das Zertifikat und die HTTPS-Weiterleitung über ISPConfig einrichten. Für einen ersten HTTP-Test die HTTPS-Weiterleitung ausgeschaltet lassen und unten `--http` verwenden.
4. In ISPConfig einen **neuen Datenbankbenutzer und eine neue leere MySQL-Datenbank** anlegen. Diesen Benutzer der Datenbank zuordnen und ihm die Rechte innerhalb dieser Datenbank geben. Die Anwendung erstellt Tabellen, aber keine Datenbank. MySQL-Root-Zugang und globale Rechte zum Anlegen von Datenbanken sind nicht erforderlich.
5. Die vollständigen Namen **einschließlich ISPConfig-Präfix** notieren, z. B. Datenbank `c1_ctlsoftware`, Benutzer `c1_ctlsoftware`. Das Passwort wird beim Setup verdeckt abgefragt.

Der Datenbankhost `127.0.0.1` verwendet TCP. Der in ISPConfig angelegte Benutzer muss sich mit diesem Host verbinden dürfen. Für einen separaten Datenbankserver `--db-host HOST --db-port PORT` angeben.

## 3. Repository klonen und prüfen

```bash
git clone --branch setup/debian-testumgebung --single-branch \
  https://github.com/omueller369/LokZeitleiste.git
cd LokZeitleiste
sudo bash setup-ispconfig.sh --check --webserver apache
```

Bei nginx statt Apache:

```bash
sudo bash setup-ispconfig.sh --check --webserver nginx
```

`--check` prüft lokale Voraussetzungen und den freien internen Port. Es verändert nichts und fragt keine Passwörter ab. Die Datenbankverbindung wird während der Installation geprüft, nachdem die Python-Abhängigkeiten verfügbar sind.

## 4. Installation starten

Für einen ersten HTTP-Test mit vorhandenem Apache:

```bash
sudo bash setup-ispconfig.sh \
  --domain ctl-software.io-goerlitz.eu \
  --webserver apache \
  --http \
  --db-name c1_ctlsoftware \
  --db-user c1_ctlsoftware
```

Die Beispielnamen durch die **wirklichen Werte aus ISPConfig** ersetzen. Für nginx `--webserver nginx` verwenden. Für eine bereits über ISPConfig eingerichtete HTTPS-Website `--http` weglassen. Dann werden sichere HTTPS-Cookies und der passende öffentliche Ursprung gesetzt. GPS-Aufzeichnung im öffentlichen Browser benötigt HTTPS.

Die API bindet ausschließlich an `127.0.0.1:18080`. Ist dieser Port belegt, beispielsweise `--port 18081` ergänzen. Er muss nicht in der Firewall geöffnet werden.

Die Routine:

1. erstellt einen eigenen Systembenutzer `lokzeitleiste-ispconfig` ohne Login-Shell;
2. kopiert den aktuellen Anwendungscode nach `/opt/lokzeitleiste-ispconfig/backend`;
3. erstellt eine isolierte Python-Umgebung und installiert die Projektabhängigkeiten;
4. prüft die vorhandene Datenbank auf Verbindung und vollständige Leere;
5. erstellt alle Anwendungstabellen und Grundwerte;
6. legt einen Admin mit zufälligem Passwort und 20 Test-TF samt Bildern an;
7. bereitet die TF-/VW-Dokumentverzeichnisse vor;
8. startet API und Hintergrundverarbeitung als eigene systemd-Dienste;
9. prüft die lokale API und erstellt die Direktiven für die ISPConfig-Website.

Die bestehende Webserverkonfiguration und andere Websites werden nicht überschrieben. Die öffentliche Weiterleitung folgt im nächsten Schritt.

## 5. Website mit der Anwendung verbinden

```bash
sudo cat /etc/lokzeitleiste-ispconfig/ispconfig-directives.conf
```

Den ausgegebenen Inhalt in **ISPConfig → Sites/Websites → betreffende Website → Optionen → Apache-Direktiven bzw. nginx-Direktiven** übernehmen und speichern. Je nach Sprache/ISPConfig-Version heißen die Felder etwas anders. Die Direktiven müssen durch einen ISPConfig-Administrator eingetragen werden können.

- Bei Apache stehen die Direktiven im VirtualHost-Kontext, nicht in einer `.htaccess`. Die Ausnahme für `/.well-known/acme-challenge/` bleibt für die Zertifikatsverwaltung erhalten.
- Bei nginx muss der erzeugte `location ^~ /`-Block die bestehende Root-Location **ersetzen**. Keine zweite Root-Location parallel belassen. Wenn die verwendete ISPConfig-Version die Root-Location nicht über die benutzerdefinierten Direktiven ersetzt, muss die Serveradministration diese Integration über das ISPConfig-Template für diese Website lösen. Längere bestehende ACME-Locations beibehalten. Nicht in automatisch erzeugten Dateien unter `sites-enabled` dauerhaft herumeditieren.
- ISPConfig aktualisiert die Website-Konfiguration. Danach die Syntax prüfen: bei Apache `sudo apache2ctl configtest`, bei nginx `sudo nginx -t`. Falls ISPConfig eine fehlerhafte Änderung zurückweist, diese im Panel korrigieren.

Dann im Browser aufrufen:

```text
http://ctl-software.io-goerlitz.eu/health
http://ctl-software.io-goerlitz.eu/admin/start
http://ctl-software.io-goerlitz.eu/tf
```

Bei HTTPS entsprechend `https://` verwenden. `/health` muss die JSON-Antwort `{"status":"ok"}` liefern. Eine ISPConfig-Standardseite bedeutet, dass die Website-Weiterleitung noch nicht greift.

## 6. Zugangsdaten und Testdaten

Admin-Benutzername: `admin`, sofern kein anderer mit `--admin-user NAME` angegeben wurde.

```bash
sudo cat /etc/lokzeitleiste-ispconfig/admin-initial-password
sudo cat /etc/lokzeitleiste-ispconfig/demo-tf.json
```

Die zweite Datei enthält die Namen und Login-TF-Nummern der importierten Personen. Alle neuen TF verwenden das Initialpasswort **`tomcom123456`** und müssen es beim ersten Login ändern.

Importiert werden die bestehenden 20 fiktiven Personen mit Bildern: 14 männlich, 4 weiblich, 1 divers und 1 ohne Angabe; 40 Wochenstunden und 30 Urlaubstage; 3 Grenz-TF, 2 Grenz-/Strecken-TF; 18 BahnCard 100, 1 BahnCard 50, 1 ohne BahnCard. TF-Nummern beginnen mit 787. Zufallsdaten und BahnCard-Gültigkeiten werden zum Installationstag berechnet.

Der echte Emailversand ist absichtlich nicht konfiguriert. Es wird kein Mailpit-/SMTP-Server installiert. Die Hintergrundverarbeitung läuft für interne Aufgaben. Vor einer späteren SMTP-Aktivierung die hinterlegten Test-Empfänger prüfen und die vorhandenen SMTP-Einstellungen in `/etc/lokzeitleiste-ispconfig/app.env` setzen.

## 7. Dienste, Dateien und Fehlerbehebung

```bash
sudo systemctl status lokzeitleiste-ispconfig lokzeitleiste-ispconfig-worker
sudo journalctl -u lokzeitleiste-ispconfig -n 100 --no-pager
sudo journalctl -u lokzeitleiste-ispconfig-worker -n 100 --no-pager
curl --fail http://127.0.0.1:18080/health
```

| Pfad | Inhalt |
| --- | --- |
| `/opt/lokzeitleiste-ispconfig/backend` | Installierte Anwendung |
| `/opt/lokzeitleiste-ispconfig/venv` | Isolierte Python-Abhängigkeiten |
| `/etc/lokzeitleiste-ispconfig/app.env` | Private Laufzeitkonfiguration |
| `/etc/lokzeitleiste-ispconfig/environment.json` | Private Wiederaufnahme-Konfiguration |
| `/var/lib/lokzeitleiste-ispconfig/files/TF` | Dokumentverzeichnisse der TF |
| `/var/lib/lokzeitleiste-ispconfig/files/VW` | Dokumentverzeichnisse der Verwaltung |

Konfiguration, Schlüssel und Passwörter sind nur für root lesbar. Diese Dateien gehören **nicht** in den öffentlichen Webroot oder in Git. Bei einer Sicherung neben der Datenbank auch `/etc/lokzeitleiste-ispconfig` und `/var/lib/lokzeitleiste-ispconfig` sichern. Insbesondere den Postfach-Verschlüsselungsschlüssel aufbewahren.

Nach Behebung einer fehlgeschlagenen Voraussetzung innerhalb einer bereits begonnenen Installation:

```bash
sudo bash setup-ispconfig.sh --resume
```

`--resume` übernimmt die gespeicherten Installationswerte, setzt keine Passwörter zurück und verwendet den wiederholbaren Import der Test-TF. Nach erfolgreichem Abschluss wird eine erneute Neuinstallation einschließlich `--resume` abgelehnt. Diese Routine ist **kein Update-Script**. Ein späteres `git pull` im ursprünglichen Checkout ändert die nach `/opt` kopierte laufende Anwendung ebenfalls nicht.

Eine automatische Konfiguration der ISPConfig-Website oder Zertifikate ist nicht Teil des Scripts: hierfür liegen keine ISPConfig-API-Zugangsdaten vor. Das Script erzeugt die einzutragende Konfiguration vollständig, statt ISPConfig-generierte Dateien zu überschreiben.
