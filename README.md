# LokZeitleiste v0.8

LokZeitleiste ist jetzt in eine Android-App für Tf und ein Python-Backend für Admins und Monatsdaten geteilt.

## Projektteile

- `app/`: Android-Frontend mit Monatsübersicht, lokaler Erfassung, Zugfahrtbereich aus LokZeit und manuellem Versand des ausgewählten Monats. Die App nutzt ein vom Admin angelegtes Tf-Konto. Sie kann selbst keine Benutzer anlegen.
- `backend/`: FastAPI-Webserver mit MySQL. Admins melden sich unter `/admin` an und legen Tf an. Stammdaten pro Tf: Name, Vorname, Personalnummer, monatliche Sollstunden, Urlaubstage, Geburtsdatum und BahnCard 50 oder 100. Monatsdaten und Einträge gehören zu genau einem Tf.
- `docs/` und `design/`: Anforderungen und Tablet-Vorschauen aus den bisherigen Arbeitsschritten.

Die [Gesamtvorschau](design/gesamtvorschau.html) zeigt die früheren Masken. Die [Vorschau für Tagesbeleg und Monatsabrechnung](design/monatsabrechnung-preview.html) zeigt die neuen Masken mit Beispieldaten.

Das Backend enthält jetzt ein Modul für tabellarische PDF-Eingangsbestätigungen mit direktem E-Mail-Versandauftrag und wiederholbarem Versand. E-Mail-Adresse und Bundesland sind Tf-Stammdaten. Eine zweite Backend-Funktion berechnet eine tägliche und monatliche Stundenübersicht mit Gastfahrt, Auffüllung auf acht Stunden nur an Einsatztagen, Urlaub und Krankheit mit jeweils acht Stunden je Tag. Regeln, API-Endpunkte und SMTP-Einrichtung stehen in der [Backend-Anleitung](backend/README.md).

## Start

Die [Backend-Anleitung](backend/README.md) beschreibt den ersten lokalen Aufbau auf Debian: Apache läuft auf dem Host, Python-API und MySQL 8.4 in Containern. Im Android-Emulator nutzt ein Debug-Build `-PlokzeitleisteApiBaseUrl=http://10.0.2.2:8080`. Spätere Release-Builds benötigen eine erreichbare HTTPS-Adresse. Die Dienste sind noch nicht auf einem Rechner installiert oder gestartet.

Die App speichert Einträge weiterhin lokal pro Tf. Der Button „Monat senden“ überträgt die Einträge des ausgewählten Monats mit stabilen Kennungen; wiederholtes Senden aktualisiert denselben Datensatz. Einträge werden serverseitig dem angemeldeten Tf zugeordnet. Die Zugfahrt-Standzeiten aus LokZeit lassen sich lokal den Details eines Monatseintrags vom Typ Zugfahrt zuordnen. Der Monatsversand überträgt diese Standzeitdetails noch nicht an das Backend.

## Noch offen

- Apache, MySQL und Python-API müssen auf dem vorgesehenen lokalen Rechner installiert und gestartet werden. Für ein physisches Tablet wird später eine erreichbare HTTPS-Adresse benötigt.
- Es gibt noch keinen vollständigen Abgleich zwischen App und Server: lokale Löschungen werden nicht übertragen, Serverdaten nicht automatisch abgerufen, parallele Geräte nicht zusammengeführt.
- Die achtstündige Höchstgrenze für Bereitschaft ist weiterhin eine vorläufige Annahme. Rufbereitschaft ist auf 08:00–20:00 Uhr und höchstens acht Stunden beschränkt.
- Berechnung von Arbeits-, Nacht- und Sonntagsstunden und später Ausbleibe benötigt noch verbindliche Fachregeln. Die bisherigen vorläufigen Regeln stehen in der App und in den früheren Anforderungen.
- Nach 365 Tagen läuft das Anmeldetoken ab. Danach ist eine neue Anmeldung nötig. Passwortzurücksetzung, weitere Admin-Funktionen und Schema-Migrationen folgen später.

Der Python-API-Testlauf wurde lokal mit SQLite als isolierter Testdatenbank geprüft. Ein MySQL-Integrationslauf war ohne MySQL-Server nicht möglich. Der Android-Debug-Build und die sieben ergänzten Unit-Tests wurden für die GPS-Erweiterung erfolgreich in GitHub Actions ausgeführt.

## GPS-Ortssuche und Zugfahrtdetails

Die GPS-Aufzeichnung erkennt einen Stillstand nach zwei Minuten im Bereich von 75 m (gemeldete Geschwindigkeit höchstens 1,5 m/s). Bewegung über 150 m oder über 2,5 m/s bestätigt nach 30 Sekunden die Abfahrt. Zeiten werden auf den Beginn der jeweiligen Erkennung zurückgesetzt. Veraltete/ungenaue Positionen werden ignoriert; längere Datenlücken gelten nicht als Stillstandsnachweis. GPS benötigt den geöffneten Bildschirm und einen laufenden Dienst. Erkannte Zeiten müssen weiterhin geprüft, mit einem Grund versehen und gespeichert werden.

Zur Standortzuordnung werden ausschließlich OSM-Ortsnamen (Stadt, Gemeinde, Dorf, Ortsteil) innerhalb von 5 km gesucht und mit dem lokalen DS100-Verzeichnis über den Ortsnamen abgeglichen. Es wird keine nächstgelegene Betriebsstelle ausgewählt. Mehrere Treffer stehen zur Auswahl; ohne Treffer oder bei Netzfehler bleiben DS100 und Bahnhofsname leer und können manuell ergänzt werden. Standzeiten lassen sich ohne Standort speichern und später bearbeiten.

**Datenstand:** Das enthaltene DS100-Verzeichnis ist ein Archivstand der Deutschen Bahn AG von **April 2018**, CC BY 4.0, und muss fachlich geprüft werden. Es ist kein aktuelles Verzeichnis. Herkunft und Verarbeitung stehen in `app/src/main/assets/ds100-SOURCE.txt`. Für einen neueren Stand kann `ds100.tsv` durch UTF-8-Daten mit einer Zeile `Kürzel<TAB>Name` pro Betriebsstelle ersetzt werden; Quellenangabe und angezeigten Stand dabei ebenfalls aktualisieren. OSM-Ortsdaten: © OpenStreetMap-Mitwirkende, ODbL, https://www.openstreetmap.org/copyright.

Vor jedem gespeicherten Standort befindet sich eine Checkbox. „Übernehmen“ öffnet die Auswahl einer bestehenden Zugfahrt aus der Monatsübersicht. Die ausgewählten Standzeiten müssen in deren Zeitraum liegen. Sie werden zusätzlich unter „Details“ dieser Zugfahrt gespeichert, nach Ankunft sortiert und können dort bearbeitet werden. Wiederholtes Übernehmen desselben Halts aktualisiert ihn anhand seiner stabilen Kennung. Die ursprüngliche Aufzeichnung wird dabei nicht entfernt.

Bestehende lokale Speicherbereiche, Benutzerzuordnungen und Monatseinträge bleiben erhalten. Alte Standzeiten werden ohne Formatwechsel gelesen und erhalten beim Speichern zusätzlich stabile Kennungen. Zugfahrtdetails werden lokal mit dem Monatseintrag gespeichert; der bestehende Monatsversand überträgt diese zusätzlichen Standzeitdetails noch nicht an das Backend.

Die Tests für Erkennung, Ortsabgleich, wiederholte Übernahme und Altformat-Lesen laufen mit `gradle :app:testDebugUnitTest`; der PR-Workflow prüft außerdem `:app:assembleDebug`.

Nach mehr als fünf Minuten laufendem GPS-Stillstand ohne eingetragenen Standort fragt die App einmal pro Aufenthalt nach dem Standort. Im Dropdown kann offline nach Ortsname oder DS100 gesucht werden (bis zu 50 Treffer, exakte DS100-Treffer zuerst). Ein Treffer ergänzt Bahnhofsname und Kürzel; „Nur Ortsnamen übernehmen“ speichert den Freitext ohne DS100. „Später“ beendet die Abfrage ohne Datenänderung; über „Standort per Ort / DS100 ergänzen“ lässt sie sich erneut öffnen. Die Zeiten laufen währenddessen weiter.
