# Lok-Leasing

Unter Sonstiges → Stammdaten → Lok-Leasing werden Leasingunternehmen gepflegt. Die Auswahl zeigt Firma, Ansprechpartner und E-Mail. „Neu hinzufügen“ öffnet eine leere Maske mit Deutschland als Vorgabe. Auswahl einer Firma lädt ihre Daten zum Bearbeiten. „abbrechen“ schließt die Maske ohne Speicherung; bei ungespeicherten Änderungen wird nachgefragt.

Die Firma ist Pflicht. E-Mail-Adressen werden bei Eingabe im Browser und auf dem Server geprüft. PLZ bleibt Text (bis sieben Zeichen, führende Nullen bleiben erhalten). Bemerkungen sind auf 1000 Zeichen begrenzt, mit Anzeige der verwendeten und verbleibenden Zeichen. Der Länderbestand entspricht der vorhandenen Länderliste der Mitarbeiterverwaltung. Gleichzeitige Änderungen sind durch eine Versionsprüfung geschützt.

Das Modul besitzt eine eigene Freigabe „Lok-Leasing“ (Lesen / Lesen und Schreiben / Administration). Die Triebfahrzeugfreigabe erlaubt zusätzlich das Lesen der Firmenauswahl, jedoch keine Änderungen an den Leasingunternehmen.

Beim Triebfahrzeug ersetzen Firmenauswahl und Zuordnung die bisherigen Eingabefelder Leasing-Geber und Hotline. Nach Auswahl wird der Firmenname im frei bearbeitbaren Feld Name vorgeschlagen (begrenzt auf dessen bisherige 120 Zeichen). Hotline und E-Mail werden aus der zugeordneten Firma gelesen; Änderungen an der Firma sind somit auch für zugeordnete Fahrzeuge wirksam. Die Fahrzeugdetails des Lokübergabebuchs liefern diese Kontaktdaten ebenfalls. Kategorie Störung besitzt keine Hotline-/E-Mail-Eingaben mehr. Historische Kategorien und die alten Fahrzeugfelder bleiben zur Kompatibilität erhalten.

## Installation und Update

Die normale Setup-Routine ruft `lokzeitleiste.init_db` auf. Dabei werden die neuen Tabellen angelegt, bestehende Leasing-Geber einschließlich Hotline in Unternehmen überführt und Fahrzeuge zugeordnet. Der Railpool-Testdatensatz wird nur angelegt, falls noch keine Firma dieses Namens existiert. Wiederholte Updates überschreiben weder bearbeitete Firmendaten noch bestehende Fahrzeugzuordnungen. Bestehende Fahrzeugnamen bleiben unverändert. Frühere Hotline-Angaben an Störungskategorien bleiben historisch gespeichert und werden keiner Firma automatisch zugewiesen.

Ein bereits vorhandener Leasing-Geber „Railpool“ wird dem angelegten Railpool-Datensatz zugeordnet; der gewünschte Demo-Datensatz enthält die Telefonnummern und Adresse aus der Vorgabe.
