# Arbeitsbericht im TF Portal (v0.25)

Einstieg: `/tf/arbeitsbericht`. Jeder TF erfasst ausschließlich den eigenen Dienst. Die Anmeldung und der abgeschlossene Initialpasswortwechsel sind erforderlich.

## Dienst und Pausen

Datum und minutengenaue Uhrzeit für Dienstbeginn und Dienstende; Enddatum kann der Folgetag sein. Die Gesamtarbeitszeit in der Maske ist die **Dienstspanne vor Pausenabzug**, berechnet aus den eingegebenen lokalen Ortszeiten. Die Berechnungsweise entspricht den vorhandenen Arbeitszeitintervallen; sie ist keine separate UTC-Zeitmessung bei Zeitumstellung.

Die vom Auftrag vorgegebene betriebliche Pausenregel wird auf diese Dienstspanne angewendet:

| Dienstspanne | Berechnete Mindestpause |
|---|---|
| Bis einschließlich 6 Stunden | 0 Minuten |
| Mehr als 6 bis einschließlich 9 Stunden | 30 Minuten |
| Mehr als 9 bis einschließlich 10 Stunden | 45 Minuten |
| Mehr als 10 Stunden | 45 Minuten plus jede Minute über 10 Stunden |

Beispiele: 10:01 h → 46 Minuten, 11:00 h → 105 Minuten, 12:00 h → 165 Minuten. Über zwölf Stunden: rote, fette Dienstspanne und Pflichtbegründung bis 1.000 Zeichen, auch serverseitig geprüft. Die zusätzliche Pause über zehn Stunden ist die gewünschte betriebliche Regel. Die allgemeinen 30-/45-Minuten-Grenzen stehen in [§ 4 ArbZG](https://www.gesetze-im-internet.de/arbzg/__4.html); die Maske bildet keine vollständige arbeitsrechtliche Prüfung ab.

**Tatsächliche Pause** wird separat eingegeben. Der berechnete Mindestwert wird nicht automatisch als tatsächlich genommen verbucht. Die Monatsarbeitszeit verwendet Dienstspanne minus angegebener Pause. Eine Unterschreitung der berechneten Mindestpause wird angezeigt, ohne die Erfassung der tatsächlich geleisteten Zeit zu verhindern.

## Gastfahrten

Bis zu 50 Gastfahrten je Dienst: DS100-Abfahrts-/Ankunftscode mit Suchvorschlägen, Start-/Enddatum und Uhrzeit, Zug, Auto, Taxi, ÖPNV oder anderes Verkehrsmittel mit Pflichtfreitext bis 140 Zeichen. Codes werden gegen die vorhandene Bahnhofsdatenbank geprüft. Gastfahrten liegen innerhalb des Dienstes und überschneiden sich nicht. Hinzufügen, Bearbeiten und Entfernen sind im Entwurf möglich. Die Tabelle zeigt Start, Ende, Dauer, Verkehrsmittel und DS100-Codes; darunter steht die Summe.

Die Gastfahrtzeit ist **Teil** der Arbeitszeit und wird nicht nochmals addiert. Ein synchronisierter Bericht erzeugt genau einen `WorkEntry` mit Pausen- und Gastfahrtminuten und explizitem Enddatum. Damit berücksichtigt ihn die vorhandene Tages-, Wochen- und Monatsberechnung und die administrative Korrektur-/Sperrfunktion.

Für unveränderte Berichte verwendet die Tagesberechnung die tatsächlichen Gastfahrtintervalle, auch über Mitternacht und Monatswechsel. Ohne Angaben zur zeitlichen Lage einer Pause verteilt die Berechnung deren Dauer von hinten auf die Nicht-Gastfahrtabschnitte. Das ist eine Berechnungsannahme; zeitlich aufgelöste Pausen können in einer späteren Ausbaustufe ergänzt werden. Nach administrativen Zeitänderungen gilt der korrigierte `WorkEntry`; die ursprünglich eingereichten Berichtsdaten bleiben erhalten.

## Synchronisation und Belege

Der Browser hält den Entwurf je Benutzer-ID lokal und ausgewählte Belegdateien in IndexedDB. Bei Netzfehlern bleiben sie für einen weiteren Synchronisationsversuch erhalten; die Weboberfläche muss zuvor geladen worden sein. Beim Wechsel zu einem neuen Dienst müssen ausstehende Belege zuvor synchronisiert oder entfernt werden. Nach erfolgreicher Synchronisation sind Dienst und Gastfahrten in dieser Maske unveränderlich. Die administrative Arbeitszeitkorrektur bleibt verfügbar.

Bis zu 20 Belege pro Bericht, PDF/JPEG/PNG, je höchstens 10 MB. PDF wird strukturell geprüft, muss unverschlüsselt sein und 1–100 Seiten enthalten; Bilder werden geprüft und dürfen höchstens 25 Megapixel haben. Originaldateien werden in der Datenbank gespeichert, nicht öffentlich als statische Dateien abgelegt. Downloads prüfen Berichtseigentümer und liefern ausschließlich Anhänge. Gesperrte Arbeitszeitdatensätze erlauben keine neuen Beleganhänge.

Erst wird der Dienst gespeichert, dann werden die Belege synchronisiert und in eine dauerhafte Versandwarteschlange aufgenommen. API-Hintergrundauftrag und vorhandener Mailer-Worker versenden automatisch über die globale SMTP-Konfiguration. Status: wartet auf Versand, fehlgeschlagen oder versendet. Bei Fehlern bis zu fünf automatische Versuche; danach kann der TF einen erneuten Versand anstoßen. Ohne gültigen Empfänger oder SMTP-Konfiguration bleiben die Daten wartend gespeichert.

Empfänger in **API und Mailer** über `WORK_REPORT_RECEIPT_EMAIL` setzen. Der Teststack setzt standardmäßig `omueller369@gmail.com`; die vorhandene Mailpit-Instanz fängt diese Testmails ab. Für externe Zustellung ist eine entsprechend konfigurierte reale SMTP-Verbindung erforderlich. Außerhalb des Teststacks ist der Empfänger zunächst leer. Der beim Versand verwendete Empfänger wird am Beleg gespeichert. E-Mail-Texte folgen der Sprache des TF.

Die Client-UUID verhindert doppelte Arbeitszeiteinträge beim Wiederholen derselben Synchronisation. Ein Inhaltsprüfwert verhindert doppelte Belegaufträge für dieselbe Datei im selben Bericht. Versand und Datenbank können keine gemeinsame atomare Transaktion bilden; bei einem Prozessabbruch unmittelbar nach SMTP-Annahme ist trotz stabiler Message-ID eine erneute Zustellung möglich.

## Monatsübersicht

Ganz unten: Excel-artige Tabelle mit den geleisteten Arbeitszeiten des laufenden Berliner Kalendermonats, Dienstbeginn/-ende, Nettoarbeitszeit, enthaltenen Gastfahrten und tatsächlichen Pausen. Sie enthält auch bestehende Arbeitszeiteinträge aus anderen Erfassungswegen. Dienste über Mitternacht und Monatsgrenzen werden auf die betroffenen Kalendertage verteilt. Gespeicherte Berichte lassen sich auswählen, um ihre ursprünglichen Daten und Belege anzusehen oder weitere Belege anzuhängen.

Neue Tabellen `duty_reports`, `duty_guest_trips`, `duty_receipts` werden durch den regulären `init_db`-Schritt angelegt. Der explizite TF-Testdatenreset entfernt diese zugehörigen Daten ebenfalls. Die Oberfläche und Meldungen sind in allen sieben Projektsprachen verfügbar. Arbeitsberichte sind bisher die Weboberfläche des TF Portals; eine native Android-Arbeitsberichtmaske wurde in dieser Änderung nicht ergänzt.
