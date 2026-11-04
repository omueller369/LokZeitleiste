# Modulsprachen

Die bearbeitbaren Quellen liegen in `modules/<modul>/de.json`, `pl.json` und
`en.json`. Jede Datei eines Moduls enthält dieselben stabilen Schlüssel.
`portal_*` gehört zum TF-Portal, `backend_*` zur Verwaltung und `server_*`
zu den API-, Dokument- und Fachmodulen. Gemeinsame und native Android-Texte
liegen in `shared_legacy`. Fachcodes, gespeicherte Enumwerte, DS100,
Protokollsyntax und Texte der Benutzer werden nicht umgeschrieben.

HTML verwendet `{{modul.text_…}}`. Der Schlüssel muss `text_` gefolgt von genau zwölf kleinen Hex-Zeichen sein (zum Beispiel `text_012345abcdef`); frei benannte Schlüssel werden vom Compiler abgelehnt. JavaScript und Python referenzieren dieselben
Schlüssel über `CtlText.source()` beziehungsweise `localization.source()`.
`source()` liefert den kanonischen Fachwert; die Darstellung übersetzt erst
an der Ausgabegrenze, damit Formwerte, Vergleiche und bestehende Daten stabil
bleiben. Für neue direkt übersetzte Ausgaben steht `CtlText.text(key, params)`
beziehungsweise `localization.text(key, language, **params)` bereit.

Nach Änderungen `python tools/build-translations.py` ausführen.
`--check` prüft, ob Browser-Bundle, Schlüsselindex, kompatibler Katalog,
Manifest und Android-Katalog reproduzierbar sind. Generierte Dateien nicht
von Hand bearbeiten. Schlüssel bei Textänderungen beibehalten. Neue UI-Texte
immer in allen drei Moduldateien ergänzen. Benutzertexte ausdrücklich mit
`data-i18n-ignore` schützen. HTML-Eingabewerte separat vom sichtbaren Label
setzen. Beispiel: `<option value="Urlaub">{{modul.text_…}}</option>`.

Der Browser lädt das fertige Schlüssel-Bundle vor den Controllern und ohne
zusätzlichen Sprachdatei-Download. Die Moduldateien sind einzeln über das
Manifest `/locales/manifest.json` erreichbar. Deutsch dient als Ausgangssprache.
Die Auswahl im Seitenkopf wird lokal und nach Anmeldung im Konto gespeichert;
TF-Portal und Backend verwenden dieselbe Einstellung des jeweiligen Kontos.
Die Android-Webansicht erhält dasselbe Bundle als mitgeliefertes Asset.
