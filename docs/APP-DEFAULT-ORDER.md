# Sortierung der App Grundwerte

Für Listen mit mindestens drei Einträgen erscheint bei Schreibfreigabe der Button „Sortieren“. Unterstützt werden Standzeit Grund, Zugfahrt Art, Meldung an, PZB Gründe, Kategorie Störung, Schadstellen jeweils innerhalb der gewählten Kategorie sowie E-Mail-Domains.

Der Button öffnet eine Tabelle unterhalb der Eingabemaske. Zeilen werden am Griff per Maus/Finger verschoben. Alternativ stehen Auf-/Ab-Schaltflächen und die Pfeiltasten am Griff zur Verfügung. „Widerrufen“ verwirft die lokale Reihenfolge und schließt die Tabelle ohne Serveränderung. „Speichern“ übernimmt die Reihenfolge dauerhaft. Die Felder der Eingabemaske bleiben während des Sortierens unverändert und vor paralleler Bedienung geschützt.

Die Sortierung gilt für die Anzeige im Backend und die zugehörigen Auswahlfelder, darunter Zugfahrten/GPS-Gründe, Meldungsempfänger im Lokübergabebuch und die Domainauswahl bei Mitarbeitern. Bereits verwendete Schlüssel und historische Berichtsdaten ändern sich nicht. Inaktive Werte behalten ihren Platz; bei aktiven Auswahllisten werden sie weiterhin ausgeblendet. Neu angelegte Werte werden nach den bereits sortierten Werten angehängt.

Die neue Tabelle `app_default_orders` wird durch das normale Update beziehungsweise die Neuinstallation mit `init_db` angelegt. Bestehende Listen behalten ihre bisherige Reihenfolge, bis ausdrücklich eine Sortierung gespeichert wird. Jede Liste und jede Schadstellenkategorie hat eine eigene Sortierung mit Versionsnummer. Veraltete Sortierungen oder inzwischen geänderte Listen werden beim Speichern abgewiesen. Die bestehende zentrale Änderungsprotokollierung zeichnet das Speichern auf.

Berechtigungen: App Grundwerte Stufe 1 liest sortierte Werte; ab Stufe 2 kann die Reihenfolge gespeichert werden. Rechte zum Anlegen/Löschen von Domains oder zum Löschen bereits verwendeter Werte ändern sich dadurch nicht.
