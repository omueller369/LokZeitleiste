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

## Bremsenzahlen 0–300
Zeilen 8–12 sind optionale Ganzzahlen von 0 bis 300 einschließlich. Zeile 8 ist wieder eingebbar. Null wird gedruckt, nur fehlende Werte werden gestrichen. Feld-11-Vorschläge nutzen ebenfalls den Bereich 0–300; Zeile 14 bleibt unverändert 1–50.

## Einheitliche Mengenfelder und Hervorhebung
Alle numerischen Eingabefelder der Zugparameter, einschließlich bedingter Geschwindigkeiten, erlauben ganze Zahlen 0–5000. Zug-/Fahrzeugnummern bleiben Kennungen mit ihrem bisherigen Format. Automatisch berechnete technische Gewichte werden weiterhin exakt aus den Stammdaten abgeleitet und nicht still gerundet. Fehlende Pflichtfelder und Format-/Bereichsfehler werden mit rotem 3px-Rahmen und aria-invalid markiert; unvollständige Entwürfe bleiben speicherbar, ungültige Werte nicht. Zeilen 5, 6 und 15 werden in Maske, Vorschau und PDF fett und blau hervorgehoben. Maske/Bedienelemente sind größer; die mobile Anordnung bricht weiter um.

## Kompakte Maske, Ergebnisfarben nur am Bildschirm
Zeilen 5/15 nur in der Maske blau und fett. Zeile 6: Zahl rot, sonst schwarz. PDF/PNG-Vorschau zeigen die berechneten Werte einheitlich mit 7pt ohne besondere Fettschrift; Zeilen 5/15 schwarz, Zeile 6 bei einer Zahl rot und sonst schwarz. Eingetragene Zugnummern, Betriebsstellen und übrige Standardwerte ebenfalls 7pt. Maske wieder kompakt (15px, kleinere Abstände); mobile Eingaben bleiben mindestens 16px und 40px hoch. Rote Validierungsrahmen bleiben erhalten.

## Ausnahmen für leere PDF-Felder
Zugnummer/Betriebsstelle sowie Zeilen 8–12 und 14–15 in Spalten 5/6 bleiben ohne diagonale Streichung. Zeile 32 bei Nein: kein Text, kein Nein-Vermerk und keine Streichung im Datenbereich. Bei Ja bleiben Text und Ja-Vermerk erhalten. Gilt gleichermaßen für PDF und Bildvorschau.

## Verdichtete Eingabemaske
Tfz- und Zugdaten am Desktop nebeneinander; Datum/Zugnummer/DS100 in einer Zeile. Mengenfelder auf 9 Zeichen Breite begrenzt. Parametertabelle und Detailfelder nebeneinander auf breiten Bildschirmen, darunter letzte Fahrzeugnummer und Geschwindigkeiten. Güterzugangaben und Erstellung nebeneinander. Kleinere Innenabstände und Schaltflächen; auf mobilen Displays automatische Umbrüche sowie 16px-Schrift und mindestens 40px-Höhe für Eingaben. Berechnungen/PDF bleiben unverändert.

## Tfz-Namen und kompakte Feldgruppen
Tfz-Auswahl zeigt nur den Namen, technische Auswahl erfolgt weiterhin eindeutig per ID. Felder 4/14 bilden die erste Zweiergruppe, die übrigen Detailfelder folgen darunter. Feld 15 ist nur in der Eingabemaske verborgen, Berechnung/PDF bleiben erhalten. Feld 7 und die halbe Breite belegende Abfrage 16 nebeneinander (mobil darunter). Feld 16 zeigt Wagen 1–3 ohne die Überschriften Arbeitende Tfz/Gesamtzug; die drei gespeicherten Ja/Nein-Geschwindigkeitsangaben bleiben erhalten.

## Reisezugabschnitt der PDF
Diagonale nur von der unteren linken Ecke des Zeilennummernfeldes 29 zur oberen rechten Ecke der Beschreibung in Zeile 21. Spalte 4 enthält in Zeilen 21–29 festes „nein / ja“, ohne Auswahl. Spalten 5/6 sind in diesem Abschnitt zu einer einzigen leeren Zelle über alle neun Zeilen verbunden. Gilt auch für Bildvorschau.

## Weitere Zellverbindungen
Spalten 5/6 über Zeilen 8–12 als eine leere Zelle sowie über Zeilen 14–15 als eine weitere leere Zelle. Trennlinien innerhalb dieser Bereiche entfallen, Wagenzugfelder bleiben getrennt. Reisezug-Diagonale endet jetzt an der oberen rechten Ecke von Spalte 4 in Zeile 21.

## Zentrierte Zahlen und Zugdaten
Numerische Datenzellen, Zeilen-/Spaltennummern, letzte Fahrzeugnummer, Geschwindigkeitswerte sowie Zugnummer/Betriebsstelle werden in PDF und PNG horizontal und vertikal innerhalb ihrer Zellen zentriert. PDF nutzt Schriftmetriken, PNG die tatsächlichen Glyphengrenzen. Bei mehreren Zugnummern wird der Datenbereich gleichmäßig in zentrierte Zeilen aufgeteilt. Farben und Streichungen bleiben erhalten.

Zeilen 4–6 sind in Spalte 4 sowie getrennt davon in Spalte 5 jeweils vertikal verbunden. Die vorhandenen Diagonalen durchziehen die zwei verbundenen Zellen; Spalte 6 behält separate zentrierte Werte.
