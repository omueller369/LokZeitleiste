# Internationaler Bremszettel DE/PL – abgestimmte Eingabefelder

Quelle: vom Benutzer bereitgestellte einseitige PDF-Vorlage „Internationaler Bremszettel Güterzüge Grenzverkehr-DE-PL“. Die Vorlage enthält keine AcroForm-Felder. Noch kein fertiger PDF-Export und keine freigegebene Bremsberechnung; die folgenden Anforderungen werden schrittweise abgestimmt.

## Kopf und Zugdaten

1. Aussteller-EVU: Dropdown CTL DE / CTL PL.
2. Zugnummern: erste (DE-Zugnummer) Pflicht, weitere hinzufügbar und später ergänzbar, insbesondere Grenztrassenummer. Je exakt fünf Ziffern, führende Nullen erhalten.
3. Abfahrtsdatum: aktuelles Datum Europe/Berlin vorschlagen, manuell änderbar; später Übernahme aus Zugfahrt.
4a/b. Gültig ab/bis Bahnhof: vorhandene Suche nach DS100 oder Bahnhofsnamen mit DS100 + Name; freie manuelle Angaben für z. B. polnische Betriebsstellen zulassen.
5. Vier Länderspalten, DE oder PL. Erste zwei Pflicht, dritte/vierte optional.
6. Je Länderspalte P oder G, gleiche Pflicht-/Optionslogik.
7. Je Länderspalte Vmax 80/90/100/110/120, Default 100, gleiche Pflicht-/Optionslogik.
8/9. Bemerkungen während der Fahrt / Besonderheiten: je optionaler mehrzeiliger Text, maximal 500 Zeichen, Restzähler.
10–13. Checkboxen Gefahrgut, außergewöhnliche Sendung, zusätzliche Einschränkungsdokumente, Abfalltransporte. Nur Gefahrgut voreingestellt.
14. DE-Auswahl D3 – 22,5 t / D4 – 22,5 t; PL-Auswahl C – 20,5 t / D – 22,5 t. DE D4 setzt PL auf D.
15. Radiobuttons G / P / G+P / LL+P / R, Default G.
16a/b. Übernahme aus 4a/b. 16c/d optional, gleiche Bahnhofssuche mit Freitext wie 4a/b.
17/18. Fahrzeugnummer des ersten/letzten Fahrzeugs: zwei Paare, erstes Paar Pflicht, zweites optional. Manuelle Eingabe in fünf Blöcken 2–2–4–3–1 Ziffern wie Tfz-Verwaltung, keine Defaultwerte. Benutzernummerierung der Teilfelder weicht teilweise von PDF ab; Zuordnung visuell vor Export prüfen.

## Triebfahrzeuge, bis zu fünf Zeilen

28. Position 1–5.
29. Auswahl eines Tfz aus Stammdaten, Fahrzeugnummer übernehmen.
30. Baureihe aus Tfz.
31. Anzahl Radsätze aus Tfz (einstellige positive Zahl).
32. Länge über Puffer in Metern aus Tfz.
33. Gesamtgewicht in kg aus Tfz; Stammdateneingabe in t, Speicherung als ganze kg.
34. Bremssohlenart D/K aus Tfz.
35. Bremsstellung G/P/R, Default G.
36. Bei Feld 15 G: Tfz-Bremsgewicht G. Bei G+P: Tfz G−25 %, ganzzahlig abgeschnitten. Andere Zuordnungen und Verhältnis zur zeilenweisen Bremsstellung 35 noch bestätigen.
36a. Tfz-Federspeicherwert und dessen Einheit t oder kN übernehmen.
37. Bemerkung: noch nicht abgestimmt.

## Summen erster Abschnitt

19a = Anzahl ausgewählter Tfz in Zeilen 1–5.
20a = Summe Spalte 32, Meter.
21a = optional manuelle Festhaltekraft; Einheit noch bestätigen.
22a = Summe Spalte 36, Bremsgewicht t.
23a = Summe Spalte 33; Einheit in Summenzeile noch bestätigen (Vorlage t, Quellspalte kg).
19b–23b = manuelle Zahlenwerte, höchstens vier Stellen; Nachkommastellen und Einheiten noch bestätigen.
19a+b–23a+b = jeweilige Summen a+b, nur mit gleichen Einheiten berechnen.
24 = 22(a+b) × 100 / 23(a+b), Nachkommastellen abschneiden, nicht runden; Gewichte zuvor auf gleiche Einheit bringen.
25 = Zahl 50–150.
26 = Benutzerangabe: wenn 25 < 24 Differenz, andernfalls „/“. Vor Umsetzung bestätigen: Feldtitel lautet „Fehlende Bremshundertstel“, daher Differenzrichtung unklar.
27 = „/“.

## Noch abzustimmen

- Alleinige Pflicht zur ersten Tfz-Zeile sowie Duplikate/weitere Zugnummernbezeichnungen.
- Verhältnis Feld 15 und zeilenweiser Bremsstellung 35; Gewichte für P, R, LL+P.
- Gewichts-, Festhaltekraft- und Dezimalvorgaben der Summenzeilen.
- Berechnung und Eingabe des zweiten Abschnitts c/d/c+d.
- ETCS-Spalte, Spalte 37 sowie Felder 38–44 (Erstellung und Überprüfung).
- Speichern/Versionieren, PDF-Zuordnung und Ausgabe im Originalformular.

## Bereits implementierte Grundlage

Tf-Portal-Kachel und geschützter Modulplatzhalter vorhanden. Tfz-Verwaltung ergänzt um optionale LüP (bis drei Nachkommastellen), Gewichtseingabe in t mit exakter Speicherung kg, Radsätze 1–9 und D/K. Separate Tabelle vehicle_technical_data wird bei init_db auf Neuinstallation und Update angelegt. Bestehende technische Daten fehlen explizit (NULL), keine Schätzwerte. Nicht mitgelieferte technische Felder bleiben bei Legacy-Updates erhalten. Kopieren eines Tfz übernimmt die ergänzten technischen Daten.
