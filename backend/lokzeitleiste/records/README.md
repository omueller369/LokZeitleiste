# Manuelle Arbeitszeiten und Datensatzsperren

Tf und Verwaltungsmitarbeiter melden sich unter `/account` an und öffnen **Meine Arbeitszeiten** (`/my/worktime`). Erst nach dem vorgeschriebenen Initialpasswortwechsel ist die Erfassung zugänglich. Benutzer können ausschließlich ihre eigenen Daten sehen und erfassen; ein frei übergebener Mitarbeiterbezug wird nicht verwendet.

Beginn-Datum, Enddatum, Erfassungsart, Beginn, Ende, Pause, Gastfahrt, Notiz und gegebenenfalls Bereitschaftsunterkunft werden manuell erfasst. Jede Speicherung berechnet Tages-, vollständige ISO-Wochen- und Monatswerte aus den Serverdaten neu. Bei neuen Erfassungen ist das Enddatum zunächst das Beginn-Datum. Für Arbeit über Mitternacht ein späteres Datum wählen; Ende muss zeitlich nach Beginn liegen. Tages-, Wochen- und Monatswerte werden über den vollständigen Zeitraum aufgeteilt. Die bisherigen Regeln für Acht-Stunden-Gutschrift, Urlaub/Krank und Bereitschaft gelten weiter. Urlaub/Krank werden je Datum separat erfasst. Arbeitszeiten der Arten Zugfahrt, Bereitschaft und Sonstige Erfassung können mit Änderungsgrund nachträglich in Beginn/Ende bearbeitet werden, sofern sie offen sind. Ein bereits administrativ korrigierter Tf-Eintrag wird ausschließlich durch die Verwaltung geändert.

Unter **Arbeitszeiterfassung und Korrekturen** (`/admin/worktime`) werden Tf und Verwaltungsmitarbeiter gemeinsam angeboten. Lesen erlaubt Ansichten; Lesen und Schreiben erlaubt zusätzlich manuelle Erfassung für Mitarbeiter und Zeitkorrekturen. Administrative Tf-Zeitkorrekturen verwenden weiterhin den bestehenden E-Mail-Versand mit Vorher-/Nachher-Werten. Eine manuelle Tf-Neuerfassung erstellt die bestehende PDF-Eingangsbestätigung und setzt konfigurierte SMTP-Einstellungen voraus. In der Testumgebung landen Nachrichten in Mailpit. Verwaltungsprofile enthalten derzeit weder E-Mail noch Bundesland: Ihre Zeiterfassung erzeugt keine E-Mail; Feiertagsinformationen berücksichtigen ausschließlich deutschlandweit geltende Feiertage. Es gibt für Verwaltungsmitarbeiter keinen Tf-Sollplan oder Plansaldo.

## Sperren und Entsperren

Mit **Datensatz sperren** und Begründung wird ein einzelner Eintrag gesperrt. Dafür ist im Arbeitszeitmodul mindestens Lesen und Schreiben erforderlich. Eine Sperre gilt serverseitig für eigene Bearbeitung, administrative Korrekturen und ältere App-Uploads. Eine identische erneute Übermittlung bleibt zulässig; ein abweichendes Upload-Paket wird vollständig mit HTTP 409 zurückgewiesen. Andere offene Einträge können weiterhin bearbeitet werden.

**Entsperren** erfordert Administration im Arbeitszeitmodul. Auch Administratoren bearbeiten einen gesperrten Datensatz erst nach dessen Entsperrung. Erfassung, eigene/Verwaltungs-Zeitänderungen, Sperren und Entsperren werden mit Konto, Zeit und Änderungsgrund protokolliert. Tf-Korrekturen haben zusätzlich ihren bisherigen Vorher-/Nachher-Versandverlauf. Jede Bearbeitung und Sperraktion prüft den geladenen Zeitstempel; veraltete Daten verlangen erneutes Laden.

## API

- `GET /api/v1/account/worktime/months/{year}/{month}`: eigene Einträge und Summen.
- `POST /api/v1/account/worktime/entries`: eigener neuer `EntryIn` mit stabiler `client_id` für Wiederholungsversuche.
- `PATCH /api/v1/account/worktime/entries/{entry_id}`: eigener Beginn/Ende, `reason`, `expected_updated_at`.
- `GET /api/v1/admin/worktime/users`: Mitarbeiter für die Arbeitszeitverwaltung.
- `GET /api/v1/admin/worktime/users/{id}/months/{year}/{month}`: Mitarbeiterübersicht.
- `POST /api/v1/admin/worktime/users/{id}/entries`: manuelle Erfassung für einen Mitarbeiter.
- `PATCH /api/v1/admin/worktime/entries/{entry_id}`: Verwaltungsmitarbeiter korrigieren; Tf-Korrekturen nutzen den bisherigen E-Mail-Endpunkt.
- `PUT /api/v1/admin/worktime/entries/{entry_id}/lock`: `locked`, `reason`, `expected_updated_at`.
- `GET /api/v1/admin/worktime/users/{id}/audit`: letzte 100 Erfassungs- und Sperraktionen.

## Update und Prüfung

Im Branch `setup/debian-testumgebung`: `git pull --ff-only`, danach `sudo bash setup.sh`. Die API legt `work_entry_locks`, `work_entry_audits` und `profile_photos` zusätzlich an. Bestehende Spalten werden nicht verändert. Daten und Fotos gehören zur MySQL-Sicherung.

Die Webansichten verwenden Formulare mit Umbruch, 44-Pixel-Schaltflächen und lokal scrollbare Tabellen, Kalender und Jahresmatrix. Android 0.8 ergänzt Umbruch und Scrollen in schmalen Ansichten. Backendtests und DOM/API-Integration werden lokal geprüft. MySQL-Integration auf dem Zielserver, ein Android-Build sowie visuelle und praktische Tests auf echten Mobilgeräten stehen noch aus.

## Enddatum ab v0.15

`EntryIn` und Zeitkorrekturen unterstützen `end_date` als ISO-Datum. Ein ausdrückliches Enddatum am selben Tag verlangt eine spätere Enduhrzeit; der Folgetag wird nicht automatisch angenommen. Ein späteres Datum ermöglicht mehrtägige Zeiträume und Monats-/Jahresgrenzen. Die bestehenden Grenzen für Bereitschaft (acht Stunden) und Rufbereitschaft bleiben erhalten. Pause wird wie bisher am Ende, Gastfahrt am Beginn des Arbeitszeitraums berücksichtigt. Einträge bleiben organisatorisch dem Monat ihres Beginns zugeordnet; die Summen enthalten auch überlappende Schichten aus früheren Monaten.

Bei alten Einträgen und Clients ohne Enddatum bleibt die bisherige Mitternachtsregel bestehen. Alte App-Uploads löschen ein bereits explizit gespeichertes Enddatum nicht. Datensatzsperren und Schutz administrativer Korrekturen gelten auch für Enddaten. Administrative Tf-Korrekturen nur am Enddatum erzeugen ebenfalls eine E-Mail mit Vorher-/Nachher-Enddatum und neu berechneten Summen.

Die API legt zusätzlich `work_entry_dates` an. Dadurch werden bestehende Arbeitszeittabellen nicht geändert. Update: im Branch `setup/debian-testumgebung` `git pull --ff-only`, dann `sudo bash setup.sh`. Android separat als Version 0.9 neu bauen/installieren. MySQL-Integration und Android-Build stehen hier noch aus.
