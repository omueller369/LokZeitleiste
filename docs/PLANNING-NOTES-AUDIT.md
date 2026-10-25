# Arbeitszeitplanung: Notizen, Bestätigung und Änderungsprotokoll

## Planbearbeitung

Monatskalender und Jahresansicht verwenden dieselbe Tagesmaske und denselben Bestätigungsablauf. Die bisherige Schichtauswahl entfällt in der Arbeitszeitplanung. Bestehende Schichtzuordnungen und die daraus berechneten Sollstunden bleiben erhalten; Schichtmodelle werden weiterhin im Schichtplan gepflegt.

Notizen können über das Vorschlagsfeld ausgewählt oder frei eingegeben werden (maximal 500 Zeichen): AR = Ausfallruhe, ZR = Zusatzruhe, RU = Resturlaub Vorjahr, SIM = Simulatorfahrt, B = Bereitschaft. Diese Angaben sind Notizen; sie ändern nicht automatisch die Tagesart oder Arbeitszeitberechnung.

In der Tagesliste stehen Sollstunden und geleistete Stunden nebeneinander. Geleistete Stunden werden aus den vorhandenen Arbeitszeiteinträgen berechnet, einschließlich Diensten über Mitternacht. Urlaub und Krankheit sind keine geleisteten Arbeitsstunden. Pausen bleiben Dokumentation und werden nicht abgezogen.

Lokale Änderungen bleiben Entwürfe. Vor dem Speichern wird eine serverseitig ermittelte Liste mit TF, Datum und Vorher-/Nachher-Werten gezeigt. Erst nach Auswahl der Bestätigungscheckbox und „Bestätigen und speichern“ erfolgt die Speicherung. Abbrechen schreibt nichts. Dies gilt auch für Jahres- und Excel-Änderungen. Die bestehende serverseitige Bestätigung der Sammelplanung schützt zusätzlich über Revisionen und einen Digest gegen veraltete Änderungsvorschauen. Bestehende API-Endpunkte für ältere Integrationen bleiben kompatibel.

Der Monats-PDF-Button entfällt. Jahres-PDF und Excel-Export bleiben verfügbar. Das zentrale Änderungsprotokoll wird noch nicht im Backend angezeigt.

## Einmaliges Leeren vorhandener Planungsnotizen

Die normale Update-Routine sichert die Datenbank vor dem Update. `lokzeitleiste.init_db` legt zusätzlich die neuen Tabellen an und führt die einmalige Migration `clear-planning-notes-20261025-v1` aus:

- Alle aktuell gespeicherten `plan_days.note` werden für sämtliche TF und Jahre geleert.
- Die bisherigen Inhalte werden mit TF, Datum und Plan-Datensatz-ID in `planning_note_backup` gesichert.
- Änderungen werden in `system_change_log` unter „System (Update)“ protokolliert.
- Betroffene Monatsrevisionen werden erhöht, damit alte Browserentwürfe nicht unbemerkt überschreiben.
- Der Marker in `system_migrations` verhindert ein erneutes Löschen bei späteren Updates. Neue Notizen bleiben erhalten.

Andere Notizen, etwa Bahnhofshinweise, Triebfahrzeugbemerkungen oder Arbeitsberichte, werden nicht gelöscht. Historische Planänderungen werden für die Nachvollziehbarkeit erhalten.

## Zentrales Protokoll

`system_change_log` enthält Datum/Uhrzeit (UTC), Modul, Mitarbeiter-ID und Namenssnapshot sowie eine JSON-Beschreibung der Änderung. Authentifizierte Verwaltungs-, Administrator- und TF-Anfragen werden ihrer Datenbanksitzung zugeordnet. ORM-Anlagen, Änderungen, Löschungen und über die ORM-Sitzung ausgeführte Sammeländerungen werden protokolliert. Einzeländerungen enthalten geänderte Felder mit Vorher-/Nachher-Werten; Sammel-SQL wird als Sammelvorgang mit Tabellenbezug erfasst.

Protokoll und fachliche Änderungen werden in derselben Transaktion gespeichert: Ein Rollback verwirft beides. Passwort-, Token-, Geheimnis- und verschlüsselte Zugangsfelder werden maskiert; Binärdaten werden durch Größe und SHA-256-Prüfsumme beschrieben. Systemprozesse ohne angemeldeten Bearbeiter werden nicht fälschlich einem Mitarbeiter zugeordnet. Historische Bearbeiter können nicht nachträglich zuverlässig aus allen früheren Änderungen rekonstruiert werden. Die Protokollierung gilt ab diesem Update.

Es gibt noch keine Oberfläche oder API zum Abrufen oder Bearbeiten des zentralen Protokolls.
