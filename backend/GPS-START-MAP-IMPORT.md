# GPS-Aufzeichnung: Startbahnhof, Karte und Übernahme

Im TF-Portal Arbeitsbericht → Zugfahrt nach Eingabe einer Zugnummer. Die Schaltfläche **?** öffnet dieselbe Benutzungshilfe als Overlay; **X** oben rechts schließt sie.

1. **Zugfahrt per GPS aufzeichnen** öffnet zuerst die Startbahnhof-Auswahl. GPS-Freigabe erlauben. Bei Genauigkeit bis 50 m wird der nächste benannte Ort im 5-km-Umkreis gesucht und dessen Name im lokalen DS100-Verzeichnis nachgeschlagen. Passende Betriebsstellen werden vorgeschlagen. Die OSM-Abfrage hat 6,5 km Radius um die gerundete Cachezelle, damit die wirkliche 5-km-Umgebung abgedeckt ist. Nur Treffer bis 5 km werden angezeigt; mehrere passende DS100-Einträge stehen zur Auswahl.
2. Bahnhof auswählen und **Startbahnhof bestätigen** drücken. Alternativ DS100/Bahnhofsname suchen und bestätigen. **Erneut suchen** holt eine neue Position/Suche. Bei ungenauem oder fehlendem GPS, fehlendem Internet und ohne Treffer bleibt die manuelle Eingabe möglich. Abbrechen startet keine Aufzeichnung. Eine unterbrochene Aufzeichnung mit bereits gewähltem Startbahnhof kann fortgesetzt werden.
3. Verlauf wird lokal aufgezeichnet. Karte folgt der aktuellen Position; „Gesamter Verlauf“ zeigt die ganze Strecke. Grün = Start, Rot = Ende; rote Linien = aufgezeichnete Segmente. Ungenaue Positionen und Zeitlücken werden nicht verbunden. Hintergrund: OpenStreetMap-Standardkacheln, nur sichtbarer aktueller Kartenausschnitt, Browser-HTTP-Cache, sichtbare Attribution, kein Offline-Prefetch. Ohne Kartenverbindung bleibt der Verlauf als Linie sichtbar. Hintergrund kann mit `window.GpsTileUrl` ersetzt werden. OSM-Kacheldienst ohne Verfügbarkeitsgarantie; Richtlinie: https://operations.osmfoundation.org/policies/tiles/.
4. **GPS-Aufzeichnung beenden** sichert zuerst lokal, versucht dann den Serverabgleich und lädt Standortvorschläge. Fehler beim Abgleich löschen die lokalen Punkte nicht. **GPS synchronisieren** wiederholt die Übertragung. Im Browser muss der Tab sichtbar bleiben; Betriebssystem/Bildschirmsperre können die Standortabfrage anhalten. Android verwendet weiterhin den vorhandenen nativen Standortdienst.
5. Analyse enthält Start, Halte und Ende. Ein Halt benötigt Geschwindigkeit unter 3 km/h und länger als 5 Minuten, ohne GPS-Lücke. Tabelle: **Checkbox + Standort, Von, Bis, Grund**. Bahnhof/Vorschläge prüfen, bei Bedarf manuell auswählen und Grund aus App-Grundwerten wählen. „sonstiges“ benötigt Beschreibung. **Standorte und Gründe speichern** sichert diese Zuordnungen.
6. **Übernehmen** speichert die Zuordnungen der per Checkbox markierten Zeilen, prüft nur die ausgewählten Halte und fragt vor dem Kopieren. Nur ausgewählte positive Halt-Zeiträume werden als zusätzliche bearbeitbare Zugfahrt-Ereignisse kopiert. Sie benötigen ZMS/Grund; Art zunächst CTL. Vorhandene Einträge bleiben bestehen, identische Zeit/Ort/Grund-Kombinationen werden nicht doppelt angelegt. Pausenüberschneidungen, ungültige Zeiten, deaktivierte Gründe und >500 Einträge werden vor Änderungen abgefangen. Die Dienstzeit muss alle übernommenen Zeiträume umfassen. Fehlende Start-/Zielbahnhöfe werden aus ausgewählten GPS-Start-/Endzeilen ergänzt; keine Ereignisse mit Dauer 0. Den Arbeitsbericht anschließend separat speichern. GPS-Daten bleiben erhalten.
7. **GPS-Serverstand laden** lädt gespeicherte Daten; vorher Warnung bei lokalen Änderungen. **Standortvorschläge laden** gleicht OSM-Ortsnamen mit dem DS100-Katalog ab. **GPX herunterladen** exportiert den Verlauf. **GPS-Aufzeichnung löschen** löscht nach Bestätigung lokal/serverseitig. Für vergangene Diensttage bleibt nur Laden/Ansicht vorhandener Serverdaten möglich.

Keine neue Datenbanktabelle oder kostenpflichtige API. Neue API `/api/v1/tf/gps/nearby?lat=…&lon=…` ist TF-geschützt. Bestätigter Startbahnhof wird innerhalb des vorhandenen GPS-Payloads serverseitig validiert und gespeichert. Name kommt aus dem eigenen Bahnhofskatalog, nicht aus fremden OSM-Texten.

Automatisierte Tests: 5-km-Abdeckung, Cache-Radius, Startzuordnung, Zugriffsschutz, Browser-/Android-Lebenszyklus, tatsächlicher Auswahl- und Hilfe-Dialog im DOM-Harness, Kartenlayer/Verlauf, Ereignisübernahme mit Berlin-Zeit, Deduplizierung und Validierung. Keine reale GPS-Fahrt und kein Mobilgerät getestet; nach Update mit freigegebenem Standort prüfen. Android-Quellen verwenden dieselben Portaldateien; kein APK gebaut.

## Mitlaufende Karte und Zoom
Aktive Aufzeichnung: Nachführung bei jedem neuen ausreichend genauen GPS-Punkt (Browser/Android), gewählter Zoom bleibt erhalten. +/− zoomen, Zwei-Finger-Geste zoomt um den Gestenmittelpunkt, ein Finger verschiebt. Verschieben/Pinch schalten in freie Ansicht; „Position folgen“ reaktiviert die Nachführung. „Gesamter Verlauf“ passt die Ansicht an alle Punkte an. Zoomstufen 2–19.

OpenRailwayMap-Standardebene ist über der OSM-Grundkarte eingeblendet und mit „Bahnkarte“ schaltbar. Bei Ladefehlern wird sie bis zur erneuten manuellen Aktivierung deaktiviert, Grundkarte und Verlauf bleiben erhalten. Attribution sichtbar, Browsercache und nur sichtbarer Kartenausschnitt; kein Prefetch. Alternative eigene Bahnkacheln mit `window.GpsRailTileUrl`. Öffentlicher ORM-Dienst nur für kleine Entwicklungstests: gewerbliche/zugangsbeschränkte Daueranwendungen benötigen eine eigene bzw. entsprechend freigegebene Instanz. Bedingungen: https://wiki.openstreetmap.org/wiki/OpenRailwayMap/API. Keine Serverinstallation oder API-Schlüssel für den Test erforderlich.

Pointer-/DOM-Tests prüfen Nachführung, Zoomerhalt, Pinch, freie Ansicht, Gesamtansicht, Zoomgrenzen, Layerausfall und Vermeidung von Kachelanfragen bei unsichtbarem Tab. Tatsächliche Touchbedienung und externe Kachelverfügbarkeit auf Mobilgeräten nach dem Update prüfen.

## Änderung 30.10.2026: Ortsnamen und gezielte Übernahme

Die Suche verwendet benannte OSM-Orte (place), keine nächstgelegenen
Eisenbahnbetriebsstellen oder railway:ref-Tags. Innerhalb von exakt 5 km wird der
nächste Ortsmittelpunkt bestimmt. Dessen Name wird mit dem lokalen DS100-Katalog
verglichen (Groß-/Kleinschreibung und Satzzeichen normalisiert; gleicher Ortsname
oder Ortsname mit Bahnhofs-Zusatz). Mehrere passende Betriebsstellen stehen als
Vorschläge zur Verfügung. Die Entfernungsangabe bezieht sich auf den Ortspunkt,
nicht auf den Bahnhof. Gibt es für diesen Ort keinen Treffer, wird kein anderer
Ort als Ersatz gewählt. Die Standzeiten bleiben erhalten; das Standortfeld bleibt
leer und kann über DS100 oder Bahnhofsname manuell ergänzt werden. Ortsmittelpunkte
sind keine Gemeindegrenzen; der TF muss den Vorschlag prüfen.

Vor jedem Standort steht eine Checkbox. Erst markieren, dann oben „Übernehmen“
drücken. Nur ausgewählte Halte werden nach Bestätigung an die Zugfahrtdetails
angehängt; ausgewählte Start-/Endpunkte ergänzen nur leere Bahnhofsfelder.
Unmarkierte Zeilen müssen nicht vollständig ausgefüllt sein und bleiben erhalten,
inklusive lokal angefangener Standort- und Grund-Eingaben. Leere Standorte müssen
vor der Übernahme eines Halts manuell einem gültigen DS100-Eintrag zugeordnet
werden. Bestehende Ereignisse werden nicht überschrieben, Dubletten bleiben
unterdrückt. Den Arbeitsbericht anschließend speichern.

Die Auswahl wird lokal und beim Speichern der Zuordnungen serverseitig abgelegt.
Bestehende GPS-Punkte, Zuordnungen, Gründe und Zugfahrtdetails werden beim Update
nicht gelöscht oder migriert. Ortsabfragen nutzen einen eigenen `place:`-Cache;
bisherige Cacheeinträge bleiben bestehen, werden für neue Vorschläge aber nicht
mehr verwendet. Keine neue Datenbanktabelle erforderlich.
