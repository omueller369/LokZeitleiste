# Triebfahrzeuge: Stilllegung und Kopieren

Die Verwaltungsmaske bietet bei bestehenden Fahrzeugen „Außer Betrieb setzen“ bzw. „Wieder in Betrieb nehmen“. Dies ist unabhängig vom technischen Einsatzstatus. Stillgelegte Fahrzeuge bleiben in den Stammdaten sichtbar (grauer Kreis), verschwinden jedoch aus beiden Lokübergabebuch-Listen. Neue Übergabeprotokolle für diese Fahrzeuge werden abgewiesen. Vorhandene Protokolle und Anhänge bleiben gespeichert und sind nach Wiederinbetriebnahme wieder über die Fahrzeugliste erreichbar.

Stilllegung benötigt Schreibrechte für Triebfahrzeuge und die aktuelle Datensatzrevision. Die neue Tabelle `vehicle_retirements` wird bei Neuinstallation und Update über `init_db` automatisch angelegt. Bestehende Fahrzeuge bleiben aktiv.

„Kopieren“ öffnet einen ungespeicherten neuen Fahrzeugentwurf. Übernommen werden Baureihe, Leasing-Zuordnung, Bremswerte und die ersten beiden Nummernfelder. Die letzten drei Nummernfelder, Name, Revisionstermin, Kilometerstand und Hinweistext werden geleert; Status ist „Einsatzbereit“. Protokolle, IDs und Stilllegung werden nicht kopiert. Erst Speichern legt das neue Fahrzeug an; die vollständige Fahrzeugnummer muss eindeutig sein.

Leistung (kW) wurde aus Eingabemaske und API entfernt. Die bisherige interne Datenbankspalte bleibt aus Gründen der Updatekompatibilität ungenutzt erhalten; vorhandene Daten werden nicht destruktiv migriert.
