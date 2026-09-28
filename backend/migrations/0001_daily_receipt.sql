-- Einmalig bei vorhandener MySQL-Datenbank ausführen, bevor das neue Backend startet.
-- Zuvor eine Datenbanksicherung erstellen. Neue Tf erhalten beide Werte im Admin-Formular.
ALTER TABLE tf_profiles ADD COLUMN email VARCHAR(320) NULL;
ALTER TABLE tf_profiles ADD COLUMN federal_state VARCHAR(2) NULL;
-- Die neue Tabelle report_dispatches wird danach mit init_db/create_all erzeugt.
