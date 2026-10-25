# TF-Portal und Verwaltung als Browser-App installieren

Die Serveraktualisierung übernimmt alle erforderlichen App-Dateien automatisch:

```bash
sudo bash install-ctlsoftware-test.sh --update
```

Voraussetzung ist eine gültige HTTPS-Verbindung. Auf dem Produktivsystem:

- TF-Portal: https://ctl-software.io-goerlitz.eu/tf/install
- Verwaltung: https://ctl-software.io-goerlitz.eu/admin/install

Die Links sind auch auf der Bereichsauswahl im Domain-Root vorhanden. Auf den Einstiegsseiten beider Bereiche stehen ebenfalls Installationsschaltflächen.

## Android (Chrome oder Edge)

1. Den gewünschten Installationslink im Browser öffnen.
2. „TF-Portal installieren“ bzw. „Verwaltung installieren“ antippen.
3. Die Installation im Browser bestätigen.
4. Falls der Browser noch keinen Installationsdialog anbietet: im Browsermenü „App installieren“ oder „Zum Startbildschirm hinzufügen“ verwenden.
5. Für die zweite Anwendung den anderen Installationslink öffnen und wiederholen.

Beide Anwendungen besitzen ein eigenes Symbol, einen eigenen Namen und einen eigenen Einstiegspunkt. Anmeldung, Passwortwechsel und Modulberechtigungen gelten unverändert.

## iPhone / iPad (Safari)

1. Den Installationslink des gewünschten Bereichs in Safari öffnen.
2. „Teilen“ → „Zum Home-Bildschirm“ wählen.
3. „Als Web-App öffnen“ aktivieren, sofern angeboten.
4. „Hinzufügen“ antippen.
5. Für den anderen Bereich wiederholen.

Der Installationsbutton zeigt auf Apple-Geräten diese Anleitung an; Safari stellt keinen frei aufrufbaren Installationsdialog wie Chromium bereit.

## Betrieb und Aktualisierungen

Die Apps öffnen die aktuelle Software des Servers in einem eigenen Fenster. Ein Serverupdate wird beim nächsten Laden der Seite verwendet. Es wird kein automatisches Neuladen erzwungen; laufende Eingaben oder GPS-Aufzeichnungen werden dadurch nicht unterbrochen.

Zum Öffnen der App ist eine Internetverbindung notwendig. Die vorhandene lokale Speicherung von Arbeitsberichten bleibt bestehen; die Installation ergänzt keine vollständige Offline-Version aller Module. Zugangsdaten, API-Antworten, Dokumente und angemeldete Seiten werden vom neuen Service Worker nicht zwischengespeichert.

Technisch bestehen zwei Manifeste mit stabilen, unterschiedlichen IDs `/pwa/apps/tf` und `/pwa/apps/backend`. Die gemeinsame Scope `/` hält gemeinsame Seiten wie Konto, Dokumente und Arbeitszeiten innerhalb des App-Fensters. Diese Installationen sind keine getrennten Sicherheits- oder Datenspeicherbereiche; die vorhandenen Rollen und Sitzungsmechanismen bleiben maßgeblich.

Die Installierbarkeit und genaue Menübezeichnung hängen vom verwendeten Browser ab. Die Bereitstellung wurde durch API- und simulierte Browsertests geprüft; eine reale Geräteinstallation ist zusätzlich auf dem Zielgerät zu prüfen.
