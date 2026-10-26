# Internationaler Bremszettel DE/PL – abgestimmte Eingabefelder

Quelle: vom Benutzer bereitgestellte einseitige PDF-Vorlage „Internationaler Bremszettel Güterzüge Grenzverkehr-DE-PL“. Die Vorlage enthält keine AcroForm-Felder. Bildvorschau auf Originalvorlage vorhanden. PDF-Export ist noch nicht enthalten; zweiter Abschnitt und ETCS bleiben leer. Die Eingabemaske und die bestätigten Berechnungen des ersten Abschnitts sind als Entwurf umgesetzt.

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
16a/b. Übernahme aus 4a/b. 16c/d bleiben nach letzter Vorgabe leer.
17/18. Fahrzeugnummer des ersten/letzten Fahrzeugs: erstes Paar Pflicht; zweites Paar bleibt nach letzter Vorgabe leer. Manuelle Eingabe in fünf Blöcken 2–2–4–3–1 Ziffern wie Tfz-Verwaltung, keine Defaultwerte. Benutzernummerierung der Teilfelder weicht teilweise von PDF ab; Zuordnung visuell vor Export prüfen.

## Triebfahrzeuge, bis zu fünf Zeilen

28. Position 1–5.
29. Auswahl eines Tfz aus Stammdaten, Fahrzeugnummer übernehmen.
30. Baureihe aus Tfz.
31. Anzahl Radsätze aus Tfz (einstellige positive Zahl).
32. Länge über Puffer in Metern aus Tfz.
33. Gesamtgewicht in kg aus Tfz; Stammdateneingabe in t, Speicherung als ganze kg.
34. Bremssohlenart D/K aus Tfz.
35. Bremsstellung G/P/R, Default G.
36. Bei Feld 15 G: Tfz-Bremsgewicht G. Bei G+P: Tfz G−25 %, ganzzahlig abgeschnitten. Bei P: Tfz-Wert P und Stellung P; bei R: Tfz-Wert R und Stellung R. LL+P: eigene Bremsgewichtsangabe, Stellung G/P/R auswählbar. Die Optionen bleiben G+P und LL+P; G+R/LL+R waren ausdrücklich korrigierte Tippfehler. Bei G+P steht in Spalte 35 G und in Spalte 36 der reduzierte G-Wert.
36a. Tfz-Federspeicherwert und dessen Einheit t oder kN übernehmen.
37. Bemerkung pro Zeile: Freitext maximal 20 Zeichen.

## Summen erster Abschnitt

19a = Anzahl ausgewählter Tfz in Zeilen 1–5.
20a = Summe Spalte 32, danach auf nächsten vollen Meter aufrunden (nicht jede Lok einzeln). 20a+b verwendet den aufgerundeten 20a-Wert.
21a = optional manuelle Festhaltekraft; Einheit noch bestätigen.
22a = Summe Spalte 36, Bremsgewicht t.
23a = Summe Spalte 33 geteilt durch 1000, Tonnen. 23b wird ebenfalls in Tonnen eingegeben (100–5000).
19b: optionale ganze Fahrzeuganzahl 1–50 (neueste Vorgabe). 22b, 23b: Zahlenwerte 100–5000; 20b: 10–720 (Maße/Gewichte bis drei Nachkommastellen). 21b: optional frei eingebbarer nichtnegativer Zahlenwert ohne Vorgabe. Dies überschreibt die zwischenzeitliche Vorgabe leerer b-Felder.
19a+b–23a+b = die jeweiligen Summen aus a+b. Noch leere optionale b-Werte erhöhen die Summe nicht.
24 = 22(a+b) × 100 / 23(a+b), Nachkommastellen abschneiden, nicht runden; Gewichte zuvor auf gleiche Einheit bringen.
25 = Zahl 50–150.
26 = 24 minus 25; nur negative Differenzen anzeigen, bei null oder positiven Werten ausstreichen (Anzeige „/“).
27 = „/“.

## Noch abzustimmen

- Alleinige Pflicht zur ersten Tfz-Zeile sowie Duplikate/weitere Zugnummernbezeichnungen.
- Gewichts-, Festhaltekraft- und Dezimalvorgaben der Summenzeilen.
- Der gesamte zweite Abschnitt c/d/c+d, einschließlich 24–27 c+d, bleibt nach Vorgabe leer.
- ETCS bleibt zunächst leer.
- Felder 38/39/40 sind bestätigt und umgesetzt: Erstelldatum, Uhrzeit und TF-Name beim ersten Speichern serverseitig setzen und unverändert erhalten. 41–44 bleiben leer.
- Speichern/Versionieren, PDF-Zuordnung und Ausgabe im Originalformular.

## Bereits implementierte Grundlage

Tf-Portal-Kachel und geschützter Modulplatzhalter vorhanden. Tfz-Verwaltung ergänzt um optionale LüP (bis drei Nachkommastellen), Gewichtseingabe in t mit exakter Speicherung kg, Radsätze 1–9 und D/K. Separate Tabelle vehicle_technical_data wird bei init_db auf Neuinstallation und Update angelegt. Bestehende technische Daten fehlen explizit (NULL), keine Schätzwerte. Nicht mitgelieferte technische Felder bleiben bei Legacy-Updates erhalten. Kopieren eines Tfz übernimmt die ergänzten technischen Daten.

## Umsetzung der Eingabemaske

Eigenes Formular `/tf/bremszettel`, TF-authentifizierte APIs `/api/v1/tf/brake-sheets`, `/vehicles`, `/calculate`. Bis zu fünf unterschiedliche Tfz, erste Zugnummer und weitere fünfstellige Nummern mit führenden Nullen. Vorläufige unvollständige Entwürfe sind erlaubt; kein endgültiger PDF-Export. Tfz-Revisionen werden serverseitig geprüft; Stammdatenänderungen erfordern die bewusste Aktualisierung der Fahrzeugauswahl. Fehlende Maße/Gewichte werden nicht als 0 geschätzt. Berechnung mittels Decimal, 24 ganzzahlig abschneiden. Private Entwürfe mit Versionsprüfung verhindern das Überschreiben auf einem anderen Gerät. Erstellerdaten unveränderlich; keine Überprüfungsdaten 41–44. Android-Routen und mitgelieferte Web-Assets aktualisiert; keine APK gebaut.

## Bildvorschau

„Vorschau“ wird nach vollständigen Pflichtangaben verfügbar. Vor der Darstellung werden aktuelle Änderungen als eigener Entwurf gesichert. Die PNG-Vorschau befüllt eine aus dem Original-PDF extrahierte Rastervorlage positionsgenau. ETCS, der zweite Abschnitt und 41–44 werden nicht beschrieben. Authentifizierter POST `/api/v1/tf/brake-sheets/{id}/preview` prüft Eigentümer, Entwurfsrevision, Tfz-Revision und Vollständigkeit; Ausgabe mit no-store. Zu lange Texte werden mit einer verständlichen Fehlermeldung abgewiesen, nicht abgeschnitten. Die Ansicht ist ein Bild-Overlay; noch kein PDF-Export.
