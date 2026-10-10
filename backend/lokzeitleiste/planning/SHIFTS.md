# Schichtmodelle

**2. Personalplanung → 2.2 Schichtplan** verwaltet benannte Modelle aus aufeinanderfolgenden Blöcken von Arbeits- und Ruhetagen. Beispiel: 5 Arbeitstage, 2 Ruhetage. Ein Zyklus ist maximal 366 Tage lang. Modelländerungen benötigen die aktuelle Revision und ändern bereits erzeugte Pläne nicht automatisch.

Zur Zuweisung Tf, Zeitraum (beide Grenztage inklusive) und Zyklusbeginn auswählen. Der Zyklusbeginn ist der erste Tag des ersten Blocks und kann vor dem Zuweisungszeitraum liegen. So bleibt der Rhythmus bei Folgezuweisungen erhalten. Die Vorschau zeigt jede geplante Änderung und bestehende Tage. Standardmäßig werden nur ungeplante Tage gefüllt; ein expliziter Überschreibmodus ersetzt auch Urlaub und Notizen im Zeitraum. Der Webclient bestätigt diesen Modus zusätzlich. Änderungen werden erst beim Übernehmen in einer gemeinsamen Transaktion gespeichert.

Die Zuweisung darf bis zu fünf Jahre umfassen und über Monats-/Jahresgrenzen laufen. Berliner Feiertage bleiben mit 0 Sollstunden markiert, unabhängig vom Modellstatus. Die erzeugten Tage sind anschließend im normalen Jahres-/Monatsplan editierbar. Modell und Zeitraum werden als Snapshot in `shift_assignments` protokolliert; der Tagesverlauf trägt die Quelle `shift`.

Neue Rechte: `shifts` lesen zeigt Modelle und Zuweisungen; schreiben erlaubt Modellpflege. Vorschau benötigt zusätzlich Planung lesen, Übernahme zusätzlich Planung schreiben. Neue Tabellen: `shift_models`, `shift_assignments`; die API legt sie beim Start an. Gleichzeitige Änderungen werden über Modell- und Monatsrevisionen abgefangen.
