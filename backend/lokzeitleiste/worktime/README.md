# Administrative Arbeitszeitkorrekturen

Unter `/admin/tf` beim Mitarbeiter **Arbeitszeiten korrigieren** wählen. Direkter Einstieg: `/admin/worktime?tf=ID`. Mitarbeiter, Jahr und Monat auswählen. Die Oberfläche zeigt erfasste Einträge, Tagesarbeitszeit, vollständige ISO-Kalenderwochen von Montag bis Sonntag und Monatsarbeitszeit. Kalenderwochen am Monatsrand enthalten auch Tage aus den Nachbarmonaten.

## Bearbeitung

Jeweils einen Eintrag bearbeiten: Arbeitsbeginn und Arbeitsende ändern, **Prüfen** wählen, die bisherigen und die neuen Uhrzeiten kontrollieren und einen Änderungsgrund angeben. **Speichern und benachrichtigen** speichert die Korrektur und den E-Mail-Auftrag in derselben Datenbanktransaktion. Unveränderte Zeiten erzeugen weder einen Änderungsdatensatz noch eine E-Mail.

Bearbeitbar sind erfasste Arbeitszeiten der Arten Zugfahrt, Bereitschaft und Sonstige Erfassung. Urlaub und Krank bleiben bei der bisherigen Acht-Stunden-Regel; Rufbereitschaft und Ausfallschicht erzeugen nach der bisherigen Berechnung keine geleistete Arbeitszeit und werden hier nicht geändert. Das Planungsmodul bleibt der separate Einstieg für Soll-Arbeitstage, Urlaub und Ruhetage.

Pausen, Gastfahrt, Datum und Eintragsart bleiben unverändert. Ungültige Zeiträume, zu lange Bereitschaft, Überschneidungen mit anderen Arbeitszeiten und Konflikte mit Abwesenheiten werden abgewiesen. Bei ausdrücklich gewähltem Enddatum wird dieser Tag verwendet; Ende muss nach Beginn liegen. Alte Einträge ohne Enddatum verwenden weiter die bisherige Mitternachtsregel. Die vorhandene Berechnung arbeitet mit lokalen Uhrzeiten und teilt Nachtschichten an Mitternacht auf; sie berechnet keine zusätzliche Sommer-/Winterzeitkorrektur.

**Arbeitszeit** entspricht der geleisteten Zeit nach Pause einschließlich Gastfahrt. **Gutschrift** enthält zusätzlich die bestehende Auffüllung auf acht Stunden je Arbeitstag sowie Urlaub/Krank. Eine kürzere Schicht kann deshalb die Arbeitszeit reduzieren, während die Gutschrift unverändert bleibt. Sonntags-, Feiertags- und Nachtminuten werden ebenfalls aus den korrigierten Zeiten neu ermittelt. Auch der Monats-Saldo gegen den Arbeitszeitplan verwendet die korrigierte Gutschrift.

## Benachrichtigungen

Nach jeder tatsächlichen Änderung bekommt der Mitarbeiter an die hinterlegte E-Mail-Adresse eine Nachricht mit Datum, Art, Beginn und Ende **Vorher → Nachher**, Änderungsgrund sowie den vorherigen und neuen Tages-, Wochen- und Monatssummen. Bei Schichten über Monatsgrenzen enthält die Nachricht beide Monate. Nachrichtentext und Empfänger werden zum Änderungszeitpunkt festgehalten; spätere Änderungen verändern eine bereits vorgemerkte Nachricht nicht.

Die Versandhistorie zeigt **vorgemerkt**, **versendet** oder **fehlgeschlagen**, Versuche, Admin-ID und Änderungszeitpunkt. Der vorhandene Versandworker versucht fehlgeschlagene Nachrichten bis zu fünfmal. Nach Fehlerbehebung kann ein Admin **E-Mail erneut senden** wählen. Bereits als versendet gespeicherte Nachrichten werden nicht erneut gesendet. SMTP ist nicht mit der Datenbanktransaktion gekoppelt: Bei einem Prozessabbruch nach SMTP-Annahme und vor Statusspeicherung ist eine doppelte Zustellung möglich.

Ohne E-Mail-Adresse oder konfigurierte SMTP-Verbindung wird die Änderung abgewiesen. Ein späterer SMTP-Fehler setzt die gespeicherte Arbeitszeitkorrektur nicht zurück. In der Testumgebung nimmt **Mailpit** die E-Mail entgegen; reale Mitarbeiter erhalten dort keine Nachricht. Für echten Versand sind die SMTP-Einstellungen des Servers erforderlich.

## Gleichzeitige Bearbeitung und App-Uploads

Die Bearbeitung enthält den Zeitstempel des geladenen Eintrags. Wurde dieser inzwischen geändert, antwortet der Server mit HTTP 409 und verlangt erneutes Laden. Die Korrektur wird mit Admin, Grund und alten/neuen Zeiten dauerhaft protokolliert.

Nach einer administrativen Korrektur dürfen App-Uploads diesen Eintrag nur mit seinen aktuellen Beginn-/Endzeiten übertragen. Ein alter Offline-Stand wird vor Änderungen am Upload-Paket mit HTTP 409 abgewiesen. Die aktuellen Monatsdaten stehen über `GET /api/v1/me/months/{year}/{month}/entries` bereit. Die Android-App hat bisher keine automatische Konfliktauflösung; veraltete lokale Daten müssen vor erneutem Senden auf den aktuellen Serverstand gebracht werden.

## Installation und Update

Im bestehenden Setup-Branch den neuen Code beziehen und die Backend-Container neu bauen:

```bash
git pull --ff-only
sudo bash setup.sh
```

Die API legt beim Start die zusätzliche Tabelle `work_time_changes` an. Bestehende Tabellen und Daten bleiben erhalten; keine bestehende Spalte wird verändert. Der Versandworker muss ebenfalls mit dem neuen Code starten, was der Setup-Neubau übernimmt.

## API

- `GET /api/v1/admin/tf/{tf_id}/worktime/months/{year}/{month}`: Einträge und neu berechnete Tages-, Wochen- und Monatssummen.
- `PATCH /api/v1/admin/tf/{tf_id}/worktime/entries/{entry_id}`: `start`, `end`, `expected_updated_at`, `reason`.
- `GET /api/v1/admin/tf/{tf_id}/worktime/changes/history`: die letzten 100 Korrekturen mit Versandstatus.
- `POST /api/v1/admin/tf/{tf_id}/worktime/changes/{change_id}/retry`: fehlgeschlagene Benachrichtigung erneut vormerken.

Alle Endpunkte erfordern Admin-Anmeldung; Schreibzugriffe prüfen den konfigurierten Browser-Ursprung.

## Erweiterung ab v0.13

Das Modul bietet jetzt auch manuelle Erfassung für Tf und Verwaltungsmitarbeiter sowie serverseitige Datensatzsperren. Eigene Zeiten werden unter `/my/worktime` erfasst. [Berechtigungen, Sperren und neue API-Endpunkte](../records/README.md). Bei Verwaltungsmitarbeiter-Korrekturen und eigener Bearbeitung entstehen keine Tf-E-Mail-Aufträge; administrative Tf-Korrekturen behalten den beschriebenen Versand.

Ab v0.15 kann auch das Enddatum korrigiert werden. Die E-Mail und der Verlauf zeigen dessen Vorher-/Nachher-Werte. Monatsgrenzen und Zeiträume mit Beginn in früheren Monaten werden in den Summen berücksichtigt.
