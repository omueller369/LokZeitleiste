# Persönliche TF-Unterschrift

Unter `/tf/me` („Mein Konto“) gibt es die kleine Vorschau und „Unterschrift hinzufügen“. Das Overlay öffnet eine leere hellgraue Canvas-Fläche; Hintergrund wird nicht in die PNG gezeichnet. Finger, Stift und Maus verwenden Pointer Events mit Koordinatenumrechnung und Pointer Capture. Die Seite scrollt während des Zeichnens innerhalb der Fläche nicht.

- Speichern ersetzt die eigene gespeicherte Unterschrift; die alte bleibt bei Abbruch/Fehler erhalten.
- Löschen leert die aktuelle Zeichenfläche. Es löscht nicht die bislang gespeicherte Unterschrift.
- Abbrechen, X links oben und Escape verhalten sich gleich. Bei ungespeicherter Zeichnung erscheint das zweite Overlay mit „Nicht verwerfen“ / „Verwerfen“.
- Leere Zeichnungen werden abgewiesen. Fehlgeschlagene Übertragung erhält die Zeichnung zum erneuten Speichern.

Private TF-Endpunkte: GET/PUT `/api/v1/tf/me/signature`. Keine Benutzer-ID im Request, ausschließlich eigene Daten nach abgeschlossenem Initialpasswortwechsel. Maximal 1 MiB PNG und 2 Mio. Pixel; Reencoding entfernt Metadaten, weiße Bildteile werden transparent. Schwarz/Alpha-PNG wird eng zugeschnitten und mit transparentem Rand gespeichert. Neue Tabelle `user_signatures` wird durch normales `init_db` bei Update/Neuinstallation angelegt. Kein Dateiupload in öffentliches Verzeichnis, keine lokale persistente Browserkopie; Cache-Control no-store, Android-API-Cache ausgeschlossen.

Internationaler Bremszettel: Bei Vorschau, reiner PDF-Ablage und Mailvorbereitung wird die aktuelle eigene Unterschrift mitgegeben. Feld 40: gedruckter TF-Name links, Unterschrift rechts proportional skaliert, Abstand oben/unten ca. 2 und rechts ca. 3 Formularpixel. Ohne Unterschrift bleibt die bisherige Namensdarstellung. Bereits archivierte PDFs/Versand-Snapshots werden nicht nachträglich verändert; neue Speichern-Aktion erzeugt den aktuellen Stand. Nationaler Bremszettel unverändert.

Automatisierte API-Tests prüfen Zugriff, PNG-Transparenz, Ersetzen, fehlerhafte/leere Dateien und Beschränkung der Bildänderungen auf Feld 40. UI-Test prüft Pointer-Eingaben, Verwerfen-Warnung, Fortsetzen, Leeren und explizites Speichern. Die tatsächliche Bedienung auf einem Mobilgerät nach dem Serverupdate noch prüfen. Android-Quellen/Asset-Zuordnung ergänzt; keine APK erstellt.

## Größere Signatur in Feld 40
PNG wird ohne zusätzlichen Rand exakt auf die Alpha-Zeichnungsgrenzen zugeschnitten. Auch ältere gespeicherte PNGs werden beim Rendern erneut zugeschnitten. Proportionale Skalierung vergrößert kleine Bilder ebenfalls, bis Breite oder Höhe des verfügbaren Bereichs erreicht ist. Rechte Hälfte von Feld 40 wird nahezu über die gesamte Feldhöhe (Formularkoordinaten 1732–1773) genutzt; die Feldbeschriftung ist auf die linke Hälfte begrenzt, um Überschneidungen zu vermeiden. Name bleibt links. Bereits gespeicherte Unterschriften müssen nicht neu gezeichnet werden; PDF erneut speichern.

## Positionsgetreue Formular-Zeichenfläche
Neu angelegte Unterschriften nutzen den festen Ausschnitt (640,1680)–(940,1830) in Formular-Koordinaten, vergrößert auf 1000×500 Pixel. Private Hintergrund-API `/api/v1/tf/me/signature/background` zeigt Formularränder und die letzten drei Buchstaben des eigenen Namens. Hintergrund liegt ausschließlich als CSS-Bild hinter der transparenten Canvas und wird niemals mitgespeichert.

Upload `capture_mode=field40-v1` erfordert die feste Canvas-Größe. Server berechnet aus den tatsächlichen Alpha-Grenzen die unveränderliche Position und Größe im Formular, speichert nur die zugeschnittene PNG und separat die Geometrie in `user_signature_placements`. Die neue Tabelle wird im üblichen Update angelegt, keine Änderung vorhandener Tabellen nötig. Renderer platziert diese Unterschrift exakt an der erfassten Position, auch außerhalb von Feld 40, ohne automatische Anpassung. Ältere Unterschriften ohne Positionsdaten behalten die bisherige Einpassung, bis sie neu gezeichnet werden.
