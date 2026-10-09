# LokZeitleiste v0.12

LokZeitleiste ist jetzt in eine Android-App für Tf und ein Python-Backend für Admins und Monatsdaten geteilt.

## Projektteile

- `app/`: Android-Frontend mit Monatsübersicht, lokaler Erfassung, Zugfahrtbereich aus LokZeit und manuellem Versand des ausgewählten Monats. Die App nutzt ein vom Admin angelegtes Tf-Konto. Sie kann selbst keine Benutzer anlegen.
- `backend/`: FastAPI-Webserver mit MySQL. Admins melden sich unter `/admin` an und legen Tf an. Stammdaten pro Tf: Name, Vorname, Personalnummer, monatliche Sollstunden, Urlaubstage, Geburtsdatum und BahnCard 50 oder 100. Monatsdaten und Einträge gehören zu genau einem Tf.
- `docs/` und `design/`: Anforderungen und Tablet-Vorschauen aus den bisherigen Arbeitsschritten.

Die [Gesamtvorschau](design/gesamtvorschau.html) zeigt die früheren Masken. Die [Vorschau für Tagesbeleg und Monatsabrechnung](design/monatsabrechnung-preview.html) zeigt die neuen Masken mit Beispieldaten.

Das Backend enthält jetzt ein Modul für tabellarische PDF-Eingangsbestätigungen mit direktem E-Mail-Versandauftrag und wiederholbarem Versand. E-Mail-Adresse und Bundesland sind Tf-Stammdaten. Eine zweite Backend-Funktion berechnet eine tägliche und monatliche Stundenübersicht mit Gastfahrt, Auffüllung auf acht Stunden nur an Einsatztagen, Urlaub und Krankheit mit jeweils acht Stunden je Tag. Regeln, API-Endpunkte und SMTP-Einrichtung stehen in der [Backend-Anleitung](backend/README.md).

Das [Planungsmodul](backend/lokzeitleiste/planning/README.md) ergänzt administrative Arbeits-, Urlaubs- und Ruhetagspläne pro Tf, Excel-Import mit Vorschau, planbasierte Monatssollstunden und farbige Monats-/Jahres-PDFs.

Die Weboberfläche unter `/admin/planning` bietet einen farbigen Monatskalender mit Tagesbearbeitung, eine Tagesliste für Sammeländerungen, eine Jahresmatrix und Excel-Import.

## Start

Die [automatische Ubuntu-Setup-Routine](setup/README.md) prüft Abhängigkeiten und installiert die vollständige Backend-Testumgebung einschließlich Admin-Konto ohne Rückfragen. Vorprüfung: `bash setup.sh --check`; Installation: `sudo bash setup.sh`. Das zufällige initiale Admin-Passwort steht nur für root lesbar in `/var/lib/lokzeitleiste/admin-initial-password`.

Die [Backend-Anleitung](backend/README.md) beschreibt die Testumgebung auf Ubuntu Server 26.04.1 LTS: Apache läuft auf dem Host, Python-API und MySQL 8.4 in Containern. Im Android-Emulator nutzt ein Debug-Build `-PlokzeitleisteApiBaseUrl=http://10.0.2.2:8080`. Spätere Release-Builds benötigen eine erreichbare HTTPS-Adresse. Die Dienste sind noch nicht auf einem Rechner installiert oder gestartet.

Die App speichert Einträge weiterhin lokal pro Tf. Der Button „Monat senden“ überträgt die Einträge des ausgewählten Monats mit stabilen Kennungen; wiederholtes Senden aktualisiert denselben Datensatz. Einträge werden serverseitig dem angemeldeten Tf zugeordnet. Die Zugfahrt-Standzeiten aus LokZeit bleiben zunächst lokal und sind noch nicht mit den Monatsdaten verbunden.

## Noch offen

- Apache, MySQL und Python-API müssen auf dem vorgesehenen lokalen Rechner installiert und gestartet werden. Für ein physisches Tablet wird später eine erreichbare HTTPS-Adresse benötigt.
- Es gibt noch keinen vollständigen Abgleich zwischen App und Server: lokale Löschungen werden nicht übertragen, Serverdaten nicht automatisch abgerufen, parallele Geräte nicht zusammengeführt.
- Die achtstündige Höchstgrenze für Bereitschaft ist weiterhin eine vorläufige Annahme. Rufbereitschaft ist auf 08:00–20:00 Uhr und höchstens acht Stunden beschränkt.
- Berechnung von Arbeits-, Nacht- und Sonntagsstunden und später Ausbleibe benötigt noch verbindliche Fachregeln. Die bisherigen vorläufigen Regeln stehen in der App und in den früheren Anforderungen.
- Nach 365 Tagen läuft das Anmeldetoken ab. Danach ist eine neue Anmeldung nötig. Passwortzurücksetzung, weitere Admin-Funktionen und Schema-Migrationen folgen später.

Der Python-API-Testlauf wurde lokal mit SQLite als isolierter Testdatenbank geprüft. Ein MySQL-Integrationslauf und ein Android-Build waren in dieser Umgebung ohne MySQL-Server bzw. Android SDK nicht möglich. LokZeit selbst wurde nicht verändert.

## Arbeitszeitkorrekturen

Administratoren können Arbeitsbeginn und Arbeitsende je Mitarbeiter unter `/admin/worktime` bearbeiten. Tages-, Wochen- und Monatswerte werden neu berechnet; jede tatsächliche Änderung erzeugt eine E-Mail mit Vorher-/Nachher-Werten und einen nachvollziehbaren Änderungsverlauf. [Bedienung, Versand und Update](backend/lokzeitleiste/worktime/README.md). In der Testumgebung landen Benachrichtigungen in Mailpit.

## Verwaltungsmitarbeiter und Passwörter

Unter `/admin/staff` Verwaltungsmitarbeiter mit Stammdaten, mehreren Adressen und Modulrechten anlegen. Neue Konten müssen beim ersten Login ihr Initialpasswort ändern. Mitarbeiter und Administratoren ändern ihr eigenes Passwort unter `/account`; Administratoren können Initialpasswörter zurücksetzen. [Berechtigungen und Bedienung](backend/lokzeitleiste/accounts/README.md). Die Android-App ab Version 0.7 unterstützt Erstlogin und eigenen Passwortwechsel.
