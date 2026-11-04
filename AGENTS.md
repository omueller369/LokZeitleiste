# CTL-Software

## TF-Anleitungen fortlaufend pflegen

- Bei jeder Änderung, die TF bei der Bedienung sehen, die betroffenen Hilfethemen in `backend/lokzeitleiste/static/tf-help-content.js` mit aktualisieren. Das gilt auch für Fehlerbehebungen, neue Beschriftungen, Regeln und Speicherabläufe.
- Neue TF-Module mit ihrem Pfad, kurzen Erklärungstext und gegliederten Schritten im zentralen Hilfekatalog ergänzen. `test_tf_help.cjs` prüft, dass jede Modulkachel eine Hilfe hat. Keine noch nicht vorhandenen Funktionen als nutzbar beschreiben.
- In sämtlichen Hilfetexten ausschließlich die persönliche Du-Anrede verwenden (Du, Dich, Dir, Dein). Keine Sie-Anrede. Einfaches Deutsch verwenden: kurze Sätze, genaue Schaltflächenbezeichnungen, Begriffe erklären und Schritte in ihrer Reihenfolge nennen. Zwischen Zwischenspeichern und endgültigem Synchronisieren unterscheiden.
- `TfHelpRevision` auf den Bearbeitungstag setzen. Bei geänderten Hilfe-Dateien auch die Versionskennung des Hilfe-Laders in `auth-session.js` anpassen. Die bestehenden Dateien sind die gemeinsame Quelle für Modulhilfen, Hilfekatalog und Druckausgabe.
- Hilfefenster behalten X oben links, Drucker rechts, Fokus-Rückgabe und eine Druckansicht ausschließlich des Hilfetextes. Keine persönlichen Formularwerte in die Druckansicht übernehmen.
- Die Android-Assets und `PortalPolicy` bei neuen Hilfedateien oder Routen mit ergänzen. Relevante JavaScript-, Browser-/Druck- und Android-Prüfungen ausführen.

## Modulsprachen fortlaufend pflegen

- Neue und geänderte Bedien-, Hilfe- und Systemtexte über stabile Sprachschlüssel in `backend/lokzeitleiste/locales/modules/<modul>/{de,pl,en}.json` pflegen. In allen drei Sprachen vollständige Einträge bereitstellen; keine neuen deutschen Texte direkt in die Oberfläche schreiben.
- Gespeicherte Fachwerte, DS100-Kürzel, technische Protokolle und persönliche Texte unverändert lassen. Übersetzung erst bei der Darstellung vornehmen. Serverseitige Anpassungen gemeinsam genutzter HTML-Seiten müssen die Platzhalter vor textabhängigen Anpassungen auflösen.
- Nach Katalogänderungen `python tools/build-translations.py` ausführen und die erzeugten Browser-, Backend- und Android-Dateien mit übernehmen. `--check` sowie die relevanten Sprach- und Browserprüfungen müssen erfolgreich sein.
