# CTL-Software

## TF-Anleitungen fortlaufend pflegen

- Bei jeder Änderung, die TF bei der Bedienung sehen, die betroffenen Hilfethemen in `backend/lokzeitleiste/static/tf-help-content.js` mit aktualisieren. Das gilt auch für Fehlerbehebungen, neue Beschriftungen, Regeln und Speicherabläufe.
- Neue TF-Module mit ihrem Pfad, kurzen Erklärungstext und gegliederten Schritten im zentralen Hilfekatalog ergänzen. `test_tf_help.cjs` prüft, dass jede Modulkachel eine Hilfe hat. Keine noch nicht vorhandenen Funktionen als nutzbar beschreiben.
- Einfaches Deutsch verwenden: kurze Sätze, genaue Schaltflächenbezeichnungen, Begriffe erklären und Schritte in ihrer Reihenfolge nennen. Zwischen Zwischenspeichern und endgültigem Synchronisieren unterscheiden.
- `TfHelpRevision` auf den Bearbeitungstag setzen. Bei geänderten Hilfe-Dateien auch die Versionskennung des Hilfe-Laders in `auth-session.js` anpassen. Die bestehenden Dateien sind die gemeinsame Quelle für Modulhilfen, Hilfekatalog und Druckausgabe.
- Hilfefenster behalten X oben links, Drucker rechts, Fokus-Rückgabe und eine Druckansicht ausschließlich des Hilfetextes. Keine persönlichen Formularwerte in die Druckansicht übernehmen.
- Die Android-Assets und `PortalPolicy` bei neuen Hilfedateien oder Routen mit ergänzen. Relevante JavaScript-, Browser-/Druck- und Android-Prüfungen ausführen.
