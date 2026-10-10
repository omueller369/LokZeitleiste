# Administrativer Arbeitszeit-, Urlaubs- und Ruhetagsplan

Admins öffnen beim jeweiligen Tf den Link **Arbeitszeitplan** oder `/admin/planning`. Der Plan kann für jeden Tf und jeden Monat/Jahr zwischen 2000 und 2100 angelegt und jederzeit geändert werden. Die Weboberfläche bietet Monatskalender, Tagesliste, Jahresansicht und Excel-Import. Ein Klick auf einen Kalendertag öffnet Tagesart und Notiz. Einzelne Tagesarten und Notizen sind bearbeitbar; markierte Tage können gemeinsam umgestellt werden. Speichern aktualisiert Berechnung und Änderungsverlauf.

## Verbindliche Planregel

Nur ausdrücklich geplante Tage werden berücksichtigt:

| Tagesart | Erforderlicher Arbeitstag | Stunden im Plansoll |
|---|---:|---:|
| Arbeitstag | 1 | 8 |
| Urlaub | 0 | 8 |
| Ruhetag | 0 | 0 |
| Ungeplant | offen | noch unberechnet |

Monatliches Arbeitssoll = Summe der Tages-Sollzeiten: Streckendienst 8 Stunden, Grenzdienst Tag/Nacht 12 Stunden; Feiertage bleiben 0. Soll inklusive Urlaub = Arbeitssoll + Anzahl Urlaubstage × 8 Stunden. Die Jahreswerte addieren die zwölf Monate, inklusive Schaltjahr. Wochenenden werden nicht automatisch zu Ruhetagen. Gesetzliche Berliner Feiertage werden automatisch mit 0 Sollstunden berücksichtigt. **Ungeplant** hebt eine vorhandene Tagesplanung samt Notiz auf; ausgelassene Datumszeilen bleiben unverändert.

Die tatsächliche Monatsabrechnung aus App-Einträgen erhält `planning`, `target_minutes` und `balance_minutes`. Der Saldo wird nur bei vollständig geplantem Monat berechnet: tatsächlich gutgeschriebene Minuten minus Plansoll inklusive Urlaub. Solange Tage ungeplant sind, bleibt der Saldo leer. Der allgemeine Sollstundenwert in den Tf-Stammdaten wird nicht überschrieben. Die Monatssollberechnung nutzt den datumsbezogenen Plan.

Ein geplanter Urlaubstag an einem Nichtfeiertag erhält acht Stunden **im Plan**. Er erzeugt keinen tatsächlichen App-Arbeitszeiteintrag. In der bisherigen Ist-Abrechnung werden die aus der App übermittelten Urlaubs- und Krankheitstage weiter mit jeweils acht Stunden berücksichtigt. So wird Urlaub nicht doppelt gutgeschrieben; zukünftige Planungen verändern keine empfangenen Tagesbelege.

## Excel

Die Verwaltung exportiert eine aktuelle XLSX-Vorlage für das gewählte Jahr und den ausgewählten Tf. Die Datei enthält für jeden Kalendertag eine Zeile, Farben, Tagesart-Auswahl, Text-Personalnummern und einen Tabellenfilter. Importierte XLSX-Dateien müssen folgendes Format haben:

- Blattname: `Plan`.
- Spalte A `Datum`: echtes Excel-Datum, `YYYY-MM-DD` oder `DD.MM.YYYY`.
- Spalte B `Art`: `Arbeitstag`, `Urlaub`, `Ruhetag` oder `Ungeplant`.
- Optional Spalte C `Notiz`: höchstens 500 Zeichen.
- Optional Spalte D `Personalnummer`: als Text, passend zum ausgewählten Tf. Führende Nullen erhalten.
- Optional Spalte E `Schicht`: `standard`, `border_day` oder `border_night`.

Vor dem Import zeigt die Oberfläche Datum, bisherige und neue Tagesart sowie die neue Notiz. Erst **Import übernehmen** speichert die Änderungen. Es werden nur die enthaltenen Datumszeilen geändert; „Ungeplant“ entfernt die Planung dieses Tages. Doppelte Daten, fremde Personalnummern, falsches Jahr, ungültige Tagesarten, Formeln, Makros und übergroße Dateien werden abgelehnt. Maximal 2 MB Datei, 20 MB entpackt und 366 Tageszeilen. Alte `.xls`-Dateien bitte zuerst als `.xlsx` speichern. Abweichende bestehende Excel-Layouts müssen in dieses Format gebracht werden.

Alle Änderungen eines Imports erfolgen gemeinsam. Wird zwischen Vorschau und Übernahme ein betroffener Monat geändert, wird der gesamte Import mit HTTP 409 zurückgewiesen. Auch manuelle Änderungen prüfen die geladene Monatsrevision. Danach den Plan neu laden und erneut prüfen. Der Verlauf protokolliert Datum, vorherige/neue Tagesart und Notiz, Admin, Zeitpunkt und Quelle. Die Oberfläche zeigt die letzten 100 Änderungen des Jahres.

## PDFs

- Monatsplan: farbiger Kalender auf A4, Kennzahlen und gegebenenfalls Notizen auf Folgeseiten.
- Jahresplan: Jahresmatrix auf A3 quer, 12 Monate mit Tageskennzeichen und Monatssummen.
- Blau = Arbeitstag, Grün = Urlaub, Orange = Ruhetag, Grau = ungeplant, Violett = Berliner Feiertag (F, 0 h Soll). Kennzeichen A/U/R/? und Legende erlauben auch einen Schwarzweiß-Ausdruck.

Die Exporte zeigen den aktuellen gespeicherten Stand; noch nicht gespeicherte Änderungen erscheinen nicht im PDF. Die Pläne werden heruntergeladen, nicht automatisch per E-Mail versandt. Muster mit fiktiven Daten liegen unter `design/Plan-Monat-Muster.pdf` und `design/Plan-Jahr-Muster.pdf`.

## Installation und Datenbank

Das Modul gehört zum vorhandenen bestehenden Setup-Branch. Beim neuen Containerstart führt `init_db` `create_all` aus und legt die neuen Tabellen `plan_months`, `plan_days` und `plan_changes` an. Bestehende Tabellen/Einträge werden dafür nicht verändert. Die hinzugefügten Python-Abhängigkeiten werden beim Containerbuild installiert.

Bei einer laufenden Testumgebung im aktuellen Branch:

```bash
sudo bash backend/testenv/control.sh backup
git pull --ff-only
sudo bash backend/testenv/control.sh start
```

Alternativ die Setup-Routine erneut ausführen. Danach bei `/admin` anmelden und beim Tf **Arbeitszeitplan** öffnen. Der MySQL-Betrieb des neuen Moduls ist noch auf der Ubuntu-VM zu prüfen. Automatisierte Tests verwenden SQLite; sie prüfen Rechte, Berechnung, Revisionen, atomaren Import, fehlerhafte Dateien, Excel-Rundlauf und PDF-Endpunkte.

## API

Alle Verwaltungsendpunkte erfordern ein aktives Admin-Cookie; Schreibzugriffe zusätzlich den konfigurierten Browser-Ursprung. Pfadpräfix: `/api/v1/admin/tf/{tf_id}/plan`.

| Methode | Pfad | Funktion |
|---|---|---|
| GET | `/{year}` | Jahresplan mit Monatssummen |
| GET | `/{year}/{month}` | Monatsplan und Revision |
| PUT | `/{year}/{month}` | Enthaltene Tage ändern, `expected_revision` erforderlich |
| GET | `/{year}/template.xlsx` | Aktueller Jahresplan als XLSX |
| POST | `/{year}/import/preview` | XLSX im Multipart-Feld `file` prüfen |
| POST | `/{year}/import` | Geprüfte `days` und `expected_revisions` gemeinsam übernehmen |
| GET | `/{year}/{month}/pdf` | Monats-PDF |
| GET | `/{year}/pdf` | Jahres-PDF |
| GET | `/{year}/history` | Letzte Änderungen |

## Mehrfachauswahl in allen Ansichten

In Monatskalender und Jahresmatrix **Mehrfachauswahl** aktivieren und mehrere Tage antippen. Die Tagesliste und Excel-Vorschau besitzen Auswahlcheckboxen. **Alle Tage der Ansicht wählen** bezieht sich auf den aktuellen Monat, das gesamte Jahr oder die Importzeilen. **Auswahl leeren** entfernt Markierungen. Die gewählte Tagesart wird mit **Auf markierte Tage anwenden** gemeinsam gesetzt; vorhandene Notizen bleiben erhalten, außer bei Ungeplant.

Kalender, Liste und Jahresmatrix teilen ihre Auswahl. Beim Monatswechsel desselben Tf/Jahrs bleiben Auswahl und Änderungen erhalten. Die Jahresübersicht zeigt auch den noch ungespeicherten Entwurf. **Änderungen speichern** übernimmt alle geänderten Tage des Jahres gemeinsam über `POST /api/v1/admin/tf/{tf_id}/plan/{year}/bulk`, mit `days` und `expected_revisions` je betroffenem Monat. Veraltete Revisionen verhindern sämtliche Änderungen. Wechsel des Mitarbeiters/Jahrs oder Neuladen fragt bei ungespeicherten Änderungen nach. PDFs zeigen weiterhin ausschließlich den gespeicherten Stand.

Die Excel-Vorschau hat eine eigene Mehrfachauswahl. Sammeländerungen ändern zunächst nur die geprüften Importzeilen. **Import übernehmen** speichert anschließend die gesamte Vorschau mit den geprüften Monatsrevisionen. Manuelle Entwurfsänderungen müssen davor gespeichert oder verworfen werden.

## Berliner Feiertagskalender ab v0.14

Für alle Tf-Pläne gilt der gesetzliche Feiertagskalender Berlin (BE), unabhängig vom Bundesland der Tf-Stammdaten. Das bestehende Bundesland bleibt für die Ist-Arbeitszeit-/Feiertagsberechnung erhalten. Feiertage erhalten Namen, eigene Farbe und Kennzeichen F in Kalender, Tagesliste, Jahresmatrix, Importvorschau und PDF. Excel markiert Feiertage violett, nennt Namen und 0 Sollstunden im Datumskommentar und führt sie zusätzlich im Blatt „Feiertage Berlin“ auf. Das importierbare Blatt „Plan“ behält die bisherigen vier Spalten und ergänzt optional eine fünfte Spalte `Schicht`.

An gesetzlichen Berliner Feiertagen ist das Plansoll immer 0 Minuten. Dies gilt auch bei gespeicherter oder neu importierter Tagesart Arbeitstag/Urlaub. Bestehende Tagesarten und Notizen bleiben als Planangaben erhalten; für erforderliche Arbeitstage, Urlaubs-Sollgutschrift, Ruhetage und offene Tage werden Feiertage separat gezählt. Ein ungeplanter Feiertag verhindert keinen vollständigen Plan. Mehrfachauswahl und manuelle Änderungen können die Feiertagsregel nicht aufheben. Tatsächlich geleistete/erfasste Zeiten bleiben unverändert.

Die API liefert je Tag `is_holiday`, `holiday_name`, `holiday_state` und das korrigierte `target_minutes`, je Monat/Jahr zusätzlich `holiday_days`. Die bestehende holidays-Abhängigkeit (mindestens 0.105) berechnet bewegliche Feiertage und historisch geltende Feiertage einschließlich einmaliger Berliner Feiertage. Ersatzfeiertage und Schulferien werden nicht als gesetzliche Feiertage übernommen. Quelle und Abgleich: [Berliner Feiertage 2026/2027](https://www.berlin.de/tourismus/infos/1887651-1721039-feiertage-schulferien.html), [einmaliger Feiertag 17. Juni 2028](https://www.berlin.de/sen/bjf/service/kalender/ferien/termine/). Bei späteren Gesetzesänderungen Kalenderabhängigkeit aktualisieren und erneut prüfen. Keine Datenbankmigration erforderlich.

## Diagonale Feiertagsdarstellung ab v0.15

Ist ein Berliner gesetzlicher Feiertag zugleich als Arbeitstag, Urlaub oder Ruhetag geplant, werden beide Farben diagonal dargestellt: Violett für den Feiertag und Blau/Grün/Orange für die gespeicherte Tagesart. Dies gilt für Monatskalender, Tagesliste, Jahresmatrix, Importvorschau, Monats-/Jahres-PDFs und Excel-Export. Die Jahresmatrix und PDFs verwenden zusätzlich F/A, F/U oder F/R; Feiertage ohne Planstatus bleiben vollständig violett (F). Die zweifarbige Markierung ändert keine Berechnung: Feiertage behalten stets 0 Sollstunden. Excel verwendet einen diagonalen Farbverlauf mit engem Übergang zwischen den beiden Farbhälften.
