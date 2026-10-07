# Administrativer Arbeitszeit-, Urlaubs- und Ruhetagsplan

Admins öffnen beim jeweiligen Tf den Link **Arbeitszeitplan** oder `/admin/planning`. Der Plan kann für jeden Tf und jeden Monat/Jahr zwischen 2000 und 2100 angelegt und jederzeit geändert werden. Einzelne Tagesarten und Notizen sind bearbeitbar; markierte Tage können gemeinsam umgestellt werden. Speichern aktualisiert Berechnung und Änderungsverlauf.

## Verbindliche Planregel

Nur ausdrücklich geplante Tage werden berücksichtigt:

| Tagesart | Erforderlicher Arbeitstag | Stunden im Plansoll |
|---|---:|---:|
| Arbeitstag | 1 | 8 |
| Urlaub | 0 | 8 |
| Ruhetag | 0 | 0 |
| Ungeplant | offen | noch unberechnet |

Monatliches Arbeitssoll = Anzahl Arbeitstage × 8 Stunden. Soll inklusive Urlaub = Arbeitssoll + Anzahl Urlaubstage × 8 Stunden. Die Jahreswerte addieren die zwölf Monate, inklusive Schaltjahr. Wochenenden und Feiertage werden nicht automatisch zu Ruhetagen. **Ungeplant** hebt eine vorhandene Tagesplanung samt Notiz auf; ausgelassene Datumszeilen bleiben unverändert.

Die tatsächliche Monatsabrechnung aus App-Einträgen erhält `planning`, `target_minutes` und `balance_minutes`. Der Saldo wird nur bei vollständig geplantem Monat berechnet: tatsächlich gutgeschriebene Minuten minus Plansoll inklusive Urlaub. Solange Tage ungeplant sind, bleibt der Saldo leer. Der allgemeine Sollstundenwert in den Tf-Stammdaten wird nicht überschrieben. Die Monatssollberechnung nutzt den datumsbezogenen Plan.

Ein geplanter Urlaubstag erhält acht Stunden **im Plan**. Er erzeugt keinen tatsächlichen App-Arbeitszeiteintrag. In der bisherigen Ist-Abrechnung werden die aus der App übermittelten Urlaubs- und Krankheitstage weiter mit jeweils acht Stunden berücksichtigt. So wird Urlaub nicht doppelt gutgeschrieben; zukünftige Planungen verändern keine empfangenen Tagesbelege.

## Excel

Die Verwaltung exportiert eine aktuelle XLSX-Vorlage für das gewählte Jahr und den ausgewählten Tf. Die Datei enthält für jeden Kalendertag eine Zeile, Farben, Tagesart-Auswahl, Text-Personalnummern und einen Tabellenfilter. Importierte XLSX-Dateien müssen folgendes Format haben:

- Blattname: `Plan`.
- Spalte A `Datum`: echtes Excel-Datum, `YYYY-MM-DD` oder `DD.MM.YYYY`.
- Spalte B `Art`: `Arbeitstag`, `Urlaub`, `Ruhetag` oder `Ungeplant`.
- Optional Spalte C `Notiz`: höchstens 500 Zeichen.
- Optional Spalte D `Personalnummer`: als Text, passend zum ausgewählten Tf. Führende Nullen erhalten.

Vor dem Import zeigt die Oberfläche Datum, bisherige und neue Tagesart sowie die neue Notiz. Erst **Import übernehmen** speichert die Änderungen. Es werden nur die enthaltenen Datumszeilen geändert; „Ungeplant“ entfernt die Planung dieses Tages. Doppelte Daten, fremde Personalnummern, falsches Jahr, ungültige Tagesarten, Formeln, Makros und übergroße Dateien werden abgelehnt. Maximal 2 MB Datei, 20 MB entpackt und 366 Tageszeilen. Alte `.xls`-Dateien bitte zuerst als `.xlsx` speichern. Abweichende bestehende Excel-Layouts müssen in dieses Format gebracht werden.

Alle Änderungen eines Imports erfolgen gemeinsam. Wird zwischen Vorschau und Übernahme ein betroffener Monat geändert, wird der gesamte Import mit HTTP 409 zurückgewiesen. Auch manuelle Änderungen prüfen die geladene Monatsrevision. Danach den Plan neu laden und erneut prüfen. Der Verlauf protokolliert Datum, vorherige/neue Tagesart und Notiz, Admin, Zeitpunkt und Quelle. Die Oberfläche zeigt die letzten 100 Änderungen des Jahres.

## PDFs

- Monatsplan: farbiger Kalender auf A4, Kennzahlen und gegebenenfalls Notizen auf Folgeseiten.
- Jahresplan: Jahresmatrix auf A3 quer, 12 Monate mit Tageskennzeichen und Monatssummen.
- Blau = Arbeitstag, Grün = Urlaub, Orange = Ruhetag, Grau = ungeplant. Kennzeichen A/U/R/? und Legende erlauben auch einen Schwarzweiß-Ausdruck.

Die Exporte zeigen den aktuellen gespeicherten Stand; noch nicht gespeicherte Änderungen erscheinen nicht im PDF. Die Pläne werden heruntergeladen, nicht automatisch per E-Mail versandt. Muster mit fiktiven Daten liegen unter `design/Plan-Monat-Muster.pdf` und `design/Plan-Jahr-Muster.pdf`.

## Installation und Datenbank

Das Modul gehört zum vorhandenen Debian-Setup-Branch. Beim neuen Containerstart führt `init_db` `create_all` aus und legt die neuen Tabellen `plan_months`, `plan_days` und `plan_changes` an. Bestehende Tabellen/Einträge werden dafür nicht verändert. Die hinzugefügten Python-Abhängigkeiten werden beim Containerbuild installiert.

Bei einer laufenden Testumgebung im aktuellen Branch:

```bash
sudo bash backend/testenv/control.sh backup
git pull --ff-only
sudo bash backend/testenv/control.sh start
```

Alternativ die Setup-Routine erneut ausführen. Danach bei `/admin` anmelden und beim Tf **Arbeitszeitplan** öffnen. Der MySQL-Betrieb des neuen Moduls ist noch auf der Debian-VM zu prüfen. Automatisierte Tests verwenden SQLite; sie prüfen Rechte, Berechnung, Revisionen, atomaren Import, fehlerhafte Dateien, Excel-Rundlauf und PDF-Endpunkte.

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
