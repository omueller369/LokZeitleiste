# Deutscher Bremszettel für Güterzüge

Eigene Dashboard-Kachel und Maske `/tf/bremszettel-de`, unabhängig vom internationalen Bremszettel. Bestehende Daten werden nicht überschrieben. Das Update legt die zusätzliche Tabelle `national_brake_sheet_drafts` über `init_db` automatisch an.

- Zunächst ein Tfz auswählen, optional ein zweites. Gemeinsame Bremsstellung G/P/R bestimmt den Stammdatenwert; Bremsstellung und Tfz-Fahrzeugnummer erscheinen nicht im PDF. Die manuell erfasste letzte Wagennummer in Zeile 7 bleibt davon unabhängig.
- Tfz-Gewichte kg → t; Tfz-Längen zunächst summieren und dann auf volle Meter aufrunden. Nur Stammdatenwerte verwenden; fehlende Angaben vor der PDF-Erstellung ergänzen. Bei zwischenzeitlich geänderten Fahrzeugstammdaten explizit aktualisieren.
- Wagenzuggewicht, -bremsgewicht und -achsen manuell. Gesamtwerte automatisch addieren. Vorhandene Bremshundertstel abschneiden, Differenz nur negativ ausgeben, sonst `/`.
- DS100/Bahnhofssuche zeigt Namen als Suchhilfe, übernimmt und druckt ausschließlich DS100. Erste Zugnummer erforderlich; fünf Ziffern, führende Nullen erhalten. Zweites Feld optional, weitere Nummern mit zugeordneter Betriebsstelle ergänzbar.
- Zeile 8 ohne Eingabe. Zeilen 9–12 optional, falls ausgefüllt ganze Zahlen 1–50. Zeile 14 Zahlen 1–50, Vorschlag aus Wagenzug-Achszahl solange nicht manuell überschrieben; bei >50 kein unzulässiger Vorschlag. Zeile 15 Wagenzugachsen × 9 / 10 abrunden.
- Zeile 16 pro Spalte Nein/Ja, Vorgabe Nein; nur bei Ja Geschwindigkeit bis 999. Deaktivierte Werte werden serverseitig entfernt.
- Reisezugabschnitt 21–29 vollständig diagonal von links unten nach rechts oben gestrichen. Zeile 31 Ja/Nein, Vorgabe Ja. Zeile 32 optionaler Text und Ja/Nein, Vorgabe Nein.
- Ersteller ist unveränderlich der TF-Name beim ersten Speichern. Datum manuell änderbar, Vorgabe heute in Europe/Berlin.

`Entwurf speichern` erlaubt unvollständige Angaben und geräteübergreifendes Laden. `Vorschau` zeigt das ausgefüllte Bild. `Speichern` archiviert die vollständige PDF, auch aus der Vorschau. Es gibt keinen Maildialog und keinen Versand. Archiv:

`Dokumente/Zugfahrten/JJJJ/MM/TT/Zugnummer/Bremszettel-DE-Zugnummer-JJJJ-MM-TT.PDF`

Datum/Ordner entsprechen dem Berichtdatum. Derselbe Entwurf aktualisiert sein Dokument; andere Entwürfe erhalten bei Namensgleichheit die bestehende sichere Kollisionsbehandlung. Zugriff nur auf eigene Entwürfe und Dateien. Revisionen verhindern unbemerkte Überschreibungen zwischen Geräten.

PDF wird als scharfe Vektorgrafik im A5-Hochformat entsprechend der gelieferten A5-Vorlage erstellt; Vorschau 1680×2380. Keine neue Laufzeitabhängigkeit oder E-Mail-Konfiguration notwendig. PDF-Layout und Formeln sind in automatisierten Tests geprüft; reale mobile Browser/Android und Onlineserver müssen nach dem Update noch geprüft werden.

Update auf dem bestehenden Testserver: `sudo bash install-ctlsoftware-test.sh --update`. Danach im Browser vollständig neu laden; im TF-Dashboard die Kachel „Deutscher Bremszettel“ wählen.

## Anpassung 26.10.2026
Bei gemeinsamer Bremsstellung G wird für jedes Tfz der Stammdatenwert G−25 % (abgeschnittene Ganzzahl) benutzt, P/R unverändert. Die Maske beginnt mit genau einer Zugnummer/Betriebsstelle; weitere Paare bleiben optional ergänzbar. Bestehende ausgefüllte Paare werden weiter geladen, keine Datenlöschung. Feld 11 erhält Achszahl/4 als Vorschlag, sofern ganzzahlig und im Bereich 1–50. Manuelle Änderungen werden nicht überschrieben; gespeicherte Werte haben Vorrang. Leere Datenfelder werden in Vorschau und PDF von links unten nach rechts oben durchgestrichen, ausgefüllte Werte (auch Nein) bleiben erhalten.
