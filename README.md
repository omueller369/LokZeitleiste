# LokZeitleiste v0.5

LokZeitleiste ist jetzt in eine Android-App für Tf und ein Python-Backend für Admins und Monatsdaten geteilt.

## Projektteile

- `app/`: Android-Frontend mit Monatsübersicht, lokaler Erfassung, Zugfahrtbereich aus LokZeit und manuellem Versand des ausgewählten Monats. Die App nutzt ein vom Admin angelegtes Tf-Konto. Sie kann selbst keine Benutzer anlegen.
- `backend/`: FastAPI-Webserver mit MySQL. Admins melden sich unter `/admin` an und legen Tf an. Stammdaten pro Tf: Name, Vorname, Personalnummer, monatliche Sollstunden, Urlaubstage, Geburtsdatum und BahnCard 50 oder 100. Monatsdaten und Einträge gehören zu genau einem Tf.
- `docs/` und `design/`: Anforderungen und Tablet-Vorschauen aus den bisherigen Arbeitsschritten.

## Start

Die [Backend-Anleitung](backend/README.md) beschreibt MySQL, Admin-Erstanlage, HTTPS und Webserver. Für die App wird beim Build eine HTTPS-Adresse als Gradle-Eigenschaft `lokzeitleisteApiBaseUrl` benötigt, beispielsweise `-PlokzeitleisteApiBaseUrl=https://zeit.example.org`. Die Konfiguration gehört zur jeweiligen Serverumgebung; es ist noch kein Server bereitgestellt.

Die App speichert Einträge weiterhin lokal pro Tf. Der Button „Monat senden“ überträgt die Einträge des ausgewählten Monats mit stabilen Kennungen; wiederholtes Senden aktualisiert denselben Datensatz. Einträge werden serverseitig dem angemeldeten Tf zugeordnet. Die Zugfahrt-Standzeiten aus LokZeit bleiben zunächst lokal und sind noch nicht mit den Monatsdaten verbunden.

## Noch offen

- Ein echter Webserver, Domain, TLS-Zertifikat, MySQL-Zugang und die Erstverteilung der Tf-Passwörter fehlen noch.
- Es gibt noch keinen vollständigen Abgleich zwischen App und Server: lokale Löschungen werden nicht übertragen, Serverdaten nicht automatisch abgerufen, parallele Geräte nicht zusammengeführt.
- Die achtstündige Höchstgrenze für Bereitschaft ist weiterhin eine vorläufige Annahme. Rufbereitschaft ist auf 08:00–20:00 Uhr und höchstens acht Stunden beschränkt.
- Berechnung von Arbeits-, Nacht- und Sonntagsstunden und später Ausbleibe benötigt noch verbindliche Fachregeln. Die bisherigen vorläufigen Regeln stehen in der App und in den früheren Anforderungen.
- Nach 365 Tagen läuft das Anmeldetoken ab. Danach ist eine neue Anmeldung nötig. Passwortzurücksetzung, weitere Admin-Funktionen und Schema-Migrationen folgen später.

Der Python-API-Testlauf wurde lokal mit SQLite als isolierter Testdatenbank geprüft. Ein MySQL-Integrationslauf und ein Android-Build waren in dieser Umgebung ohne MySQL-Server bzw. Android SDK nicht möglich. LokZeit selbst wurde nicht verändert.
