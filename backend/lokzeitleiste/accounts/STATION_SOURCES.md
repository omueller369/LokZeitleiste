# Bahnhofsdaten und Länder

Die mitgelieferte Bahnhofsliste ist ein auf Code und Name reduzierter Auszug der offenen DB-Netz-Betriebsstellenliste **Stand April 2018**. Berücksichtigt sind aktive Bahnhöfe, Haltepunkte und Bahnhofsteile laut damaligem Betriebszustand. Diese Liste ist keine aktuelle betriebliche Referenz.

- Urheber: **Deutsche Bahn AG**, Datenlizenz **CC BY 4.0**, <https://creativecommons.org/licenses/by/4.0/>
- Ursprüngliche Quelle: <https://download-data.deutschebahn.com/static/datasets/betriebsstellen/DBNetz-Betriebsstellenverzeichnis-Stand2018-04.csv>
- Abgerufene unveränderte Kopie: <https://github.com/fourplusone/ds100/blob/master/DBNetz-Betriebsstellenverzeichnis-Stand2018-04.csv>
- Änderungen: Auswahl von Bahnhofstypen und aktivem Betriebszustand, Reduktion auf Code/Name, Normalisierung von Leerzeichen, Zusammenführung gleicher Codes.
- Aktuelle offizielle Liste: <https://www.dbinfrago.com/web/schienennetz/betrieb/allgemeine-betriebsinformationen/betriebsstellen-12592996> (bei Prüfung am 11.10.2026: XLSX Stand 31.08.2026). Die Datei konnte in der Entwicklungsumgebung nicht heruntergeladen werden.

Aktualisierung im Container nach Bereitstellung der offiziellen CSV/XLSX-Datei:

```sh
python -m lokzeitleiste.accounts.import_stations /srv/data/betriebsstellen.xlsx --code-column 'Abk' --name-column 'Name'
```

Spaltennamen an die tatsächlichen Überschriften anpassen; optional `--sheet`. Vor dem Commit werden Datensätze validiert. Bestehende Codes werden aktualisiert, neue angelegt. Bereits zugewiesene Codes bleiben erhalten, damit ältere Profile nicht ungültig werden. Die aktuelle Liste und ihre Nutzungshinweise werden vom Administrator bereitgestellt; es werden keine erfundenen aktuellen Codes verwendet.

`countries.json` umfasst die 249 ISO-3166-Länder und Gebiete aus der IANA-tzdata-Länderliste, mit lokalisierten Namen aus Unicode CLDR/ICU (`Intl.DisplayNames`) für Deutsch, Englisch, Polnisch, Russisch, Türkisch, Arabisch und Spanisch. Die Auswahl speichert den zweistelligen ISO-Code.
