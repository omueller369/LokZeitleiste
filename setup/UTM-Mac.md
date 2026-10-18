# Lokale Mac-Testumgebung mit UTM

Die Anwendung läuft in einer Ubuntu-Server-VM; der Mac öffnet die Weboberfläche über einen SSH-Tunnel. Die folgenden Setup-Skripte werden **in Ubuntu**, nicht in macOS ausgeführt.

## 1. Virtuelle Maschine vorbereiten

UTM von https://mac.getutm.app/ installieren. Ubuntu Server **26.04.1 LTS** als ISO über https://ubuntu.com/download/server beziehen:

| Mac | Ubuntu-ISO | VM-Architektur |
| --- | --- | --- |
| Apple Silicon (M1/M2/M3/M4 oder neuer) | ARM64 / aarch64 | ARM64, Virtualisierung |
| Intel | AMD64 / x86_64 | x86_64, Virtualisierung |

Empfehlung für diese Anwendung: 4 virtuelle CPU-Kerne, 8 GB RAM, 60 GB virtueller Datenträger. In UTM eine Linux-VM mit passender Architektur erstellen, ISO einlegen, Netzwerk **Shared Network / Gemeinsames Netzwerk** auswählen und Ubuntu installieren. Einen eigenen Ubuntu-Administrator anlegen und OpenSSH Server bei der Installation auswählen. Nach der Installation ISO auswerfen und neu starten.

Projekt und Dokumente auf dem Linux-Datenträger ablegen, etwa `/opt/LokZeitleiste`. Ein macOS-Freigabeordner ist wegen Linux-UIDs und ACLs nicht als Projekt-/Dokumentwurzel vorgesehen.

## 2. Ubuntu vorbereiten und Repository klonen

In der Ubuntu-Konsole:

```bash
sudo apt update
sudo apt install -y git openssh-server
sudo systemctl enable --now ssh
sudo timedatectl set-timezone Europe/Berlin
sudo install -d -o "$USER" -g "$(id -gn)" /opt/LokZeitleiste
git clone --branch setup/debian-testumgebung --single-branch https://github.com/omueller369/LokZeitleiste.git /opt/LokZeitleiste
cd /opt/LokZeitleiste
bash setup-new.sh --check
sudo bash setup-new.sh
```

Ein privates Repository benötigt GitHub-Anmeldung, beispielsweise einen persönlichen Token bei der Git-Passwortabfrage. Keine Zugangsdaten in die URL schreiben. `--check` installiert nichts und meldet auch noch fehlende Abhängigkeiten. Der eigentliche Installer installiert diese einschließlich Docker, Compose, Apache, ACL-Werkzeugen und Python; er baut die Container, bereitet MySQL/Mailpit vor und legt fehlende Konten/Verzeichnisse an. Betriebssysteminstallation und Neustarts erfolgen außerhalb der Projekt-Skripte.

Initiale Admin-Zugangsdaten lokal in Ubuntu anzeigen:

```bash
sudo cat /var/lib/lokzeitleiste/admin-initial-password
hostname -I
sudo bash backend/testenv/control.sh status
```

Die Kennwortdatei ist nur für root lesbar. Vorhandene Admin-Zugangsdaten werden bei späteren Updates beibehalten. Beim ersten Login ein neues Passwort setzen.

## 3. Vom Mac verbinden

Im **macOS-Terminal** `DEIN_UBUNTU_BENUTZER` und `VM_IP` durch Ubuntu-Benutzer und die zuvor angezeigte VM-IP ersetzen:

```bash
ssh -N -L 8080:127.0.0.1:8080 -L 8025:127.0.0.1:8025 DEIN_UBUNTU_BENUTZER@VM_IP
```

Das Terminal mit dem Tunnel geöffnet lassen. In einem zweiten macOS-Terminal:

```bash
open http://localhost:8080/admin
open http://localhost:8025
```

Mailpit zeigt die Test-E-Mails an; sie werden im Teststack nicht an reale Empfänger zugestellt. Die Dokumentenverwaltung ist nach Anmeldung unter `http://localhost:8080/documents` erreichbar.

Wenn Port 8080 am Mac belegt ist, beispielsweise `-L 18080:127.0.0.1:8080` verwenden und `http://localhost:18080/admin` öffnen. Bei OAuth-Anbindungen muss die konfigurierte Redirect-URL mit dem tatsächlich verwendeten Ursprung übereinstimmen.

Bei QEMU **Emulated VLAN** statt Shared Network kann UTM alternativ TCP-Hostport 2222 an Gastport 22 weiterleiten. Dann lautet der Tunnel:

```bash
ssh -p 2222 -N -L 8080:127.0.0.1:8080 -L 8025:127.0.0.1:8025 DEIN_UBUNTU_BENUTZER@127.0.0.1
```

Portweiterleitungen in UTM sind an den QEMU-Backendmodus Emulated VLAN gebunden. Beim Apple-Backend Shared Network die VM-IP verwenden.

## 4. Bestehende Testumgebung aktualisieren

Zunächst in Ubuntu ins **bisherige** Projektverzeichnis wechseln. Nicht erneut klonen und vorhandene `.env.test`, TF/VW-Verzeichnisse oder Docker-Volumes nicht löschen.

```bash
cd /opt/LokZeitleiste
git status --short
git switch setup/debian-testumgebung
git pull --ff-only origin setup/debian-testumgebung
bash setup-update.sh --check
sudo bash setup-update.sh
```

Lokale Änderungen vor `git pull` gesondert sichern oder committen; nicht mit `git reset --hard` verwerfen. Der Update-Installer prüft zuerst die Voraussetzungen, stoppt API und Mailer für die Sicherung und erzeugt unter `backend/testenv/backups/update-…/`:

- `database.sql.gz`: vollständiger Anwendungsdatenbank-Dump;
- `documents.tar.gz`: TF/VW einschließlich ACLs und numerischer Eigentümer;
- `config.tar.gz`: `.env.test` und Testzertifikate;
- `README.txt` und, falls verfügbar, Quellcode-Commit.

Danach installiert er fehlende Pakete, baut/startet die Dienste und führt Datenbank-/Dokumenten-Nachpflege sowie Linux-Kontenabgleich aus. Währenddessen ist die Anwendung kurz nicht verfügbar. Vorhandene Dokumente und Zugangsdaten bleiben erhalten. Die Sicherung enthält Geheimnisse und ist nur root zugänglich; zusätzlich extern sichern. Es erfolgt kein automatisches Zurücksetzen einer Datenbank. Bei einem Fehler wird der Sicherungspfad ausgegeben; Sicherungen eines abgebrochenen Laufs können unvollständig sein. Vor erfolgreicher Sicherung wird kein neuer Anwendungscode gestartet.

## 5. Betrieb und Kontrolle

In Ubuntu im Projektverzeichnis:

```bash
sudo bash backend/testenv/control.sh status
sudo bash backend/testenv/control.sh logs
sudo systemctl status lokzeitleiste-users.timer --no-pager
sudo systemctl start lokzeitleiste-users.service
curl --fail http://localhost:8080/health
python3 backend/testenv/smoke.py
```

Stoppen und wieder starten:

```bash
sudo bash backend/testenv/control.sh stop
sudo bash backend/testenv/control.sh start
```

`stop` behält Daten und Docker-Volumes. Neue Anwendungskonten erhalten ihre Linux-Rechte spätestens beim nächsten Minutenlauf des Timers. Keine Docker-Volumes mit `down -v` löschen. Für einen vollständig neuen Teststand eine separate VM verwenden.

Die Skripte aktualisieren das Projekt innerhalb des vorhandenen Betriebssystems; sie führen kein Ubuntu-Release-Upgrade aus. Eine vollständige VM-Sicherung zusätzlich bei heruntergefahrener VM anlegen. Diese Anleitung beschreibt den vorgesehenen Ablauf; ein echter UTM-/Docker-Installationslauf ist in der Entwicklungsumgebung nicht ausgeführt worden.

Offizielle Referenzen: [UTM Shared Network](https://docs.getutm.app/settings-apple/devices/network/), [UTM QEMU-Portweiterleitung](https://docs.getutm.app/settings-qemu/devices/network/port-forwarding/), [Ubuntu Server](https://ubuntu.com/download/server).
