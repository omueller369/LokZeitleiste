# Version 0.26 – GPS und Arbeitsbericht

Ausgangspunkt ist Version 0.25 auf `setup/debian-testumgebung`. RC1 wird nicht vorausgesetzt. Vorhandene Arbeitsberichte, GPS-Punkte und Stammdaten bleiben erhalten; auch ältere gespeicherte Standortzuordnungen werden weiterhin gelesen. Es ist keine Datenbankmigration erforderlich. Ältere Standort- und Grundzuordnungen werden anhand ihres ursprünglichen Haltbeginns gelesen, damit zusätzliche Vier-Minuten-Halte keine Angaben auf andere Zeilen verschieben.

1. **GPS-Lücken:** Zwischen Signalverlust und nächstem gültigen Punkt erscheint eine gestrichelte Verbindung. Im GPX wird ein separates Verbindungssegment mit `lzt:estimated=true` exportiert. Es werden keine gemessenen Positionen erfunden. Eine Lücke über 30 Sekunden und ungenaue Punkte zählen nicht als Standzeit.
2. **Internet:** Bei Verbindungsunterbrechung gibt es keine Internet-Warnmeldung. Die GPS-Punkte werden weiter lokal gespeichert. Kartenkacheln und neue DS100-Suchtreffer benötigen eine Verbindung; zuvor gewählte Bahnhöfe stehen im lokalen Zugfahrtcache zur Verfügung. GPS-Signal- und HTTPS-Warnhinweise schließen nach drei Sekunden automatisch; Okay kann sie vorher schließen. Die entsprechenden Android-Hinweise blenden sich ebenfalls automatisch aus. Fehlende Standortfreigaben und eine fehlende HTTPS-Verbindung verhindern den Start weiterhin. Speicherfehler und tatsächliche Datenkonflikte werden weiterhin zur Bestätigung angezeigt.
3. **Startbahnhof:** Aufzeichnung starten, DS100 oder Bahnhofsname selbst eingeben und einen Treffer wählen. Angezeigt wird `DS100 · Bahnhofsname`. Es wird kein Standort automatisch gesucht.
4. **Endbahnhof:** Beim Beenden wird ebenfalls ausschließlich die eigene Eingabe verlangt. Bei Abbruch dieses Dialogs bleiben die GPS-Daten gesichert; den Endbahnhof später in den Zugdaten ergänzen.
5. **Standzeiten:** Ab vier Minuten erscheint ein Halt sofort in der Liste. Er beginnt beim ersten Punkt unter 3 km/h. Bewegungen innerhalb von 100 Metern um diesen ersten Punkt werden zu einer Standzeit zusammengefasst, auch bei kurzzeitig höheren GPS-Geschwindigkeiten. Eine Abfahrt wird erst außerhalb dieses Kreises mit mehr als 5 km/h erkannt; das Ende ist der letzte Punkt im Kreis. Genau 5 km/h beendet den Halt noch nicht. Auch ältere und früher bearbeitete GPS-Verläufe werden mit diesen Regeln neu ausgewertet und bei passendem Verlauf zusammengefasst. Bisherige Standort- und Grundangaben bleiben über ihre ursprünglichen Kennungen gespeichert; mehrere Angaben lassen sich im zusammengefassten Halt unter „Bisherige Angaben“ aufklappen. Bereits übernommene Zugfahrtdetails werden nicht umgeschrieben und nicht doppelt angelegt. Standort per DS100/Bahnhofsname wählen. Grund auswählen oder als Freitext eingeben (wird als „Sonstiges“ gespeichert). Bei Weiterfahrt wird „Bis“ ergänzt; fehlt ein Ende, kann es manuell in Berliner Zeit eingegeben werden. `↑ Übernehmen` fügt den Halt nach Bestätigung den Zugfahrtdetails hinzu. Er verschwindet aus der GPS-Liste und bleibt in den Details bearbeitbar. Die Punktfolge bleibt zur Nachvollziehbarkeit erhalten. Eine feste Kennung verhindert doppelte Übernahmen. Blau-rote Kartenpunkte führen beim Anklicken zum passenden Standortfeld. Erhält die Standzeitenzeile oder ein zugehöriger Zugfahrtdetail-Eintrag den Fokus, wird sein Kartenpunkt doppelt so groß und in der Kartenmitte auf mindestens Zoomstufe 16 herangezoomt; beim Verlassen wird die Punktgröße wieder normal. Die ausgewählte Kartenansicht bleibt bestehen, bis „Position folgen“ oder eine andere Ansicht gewählt wird.
6. **Wiederherstellung:** Offene Dienst-, Gastfahrt- und Zugfahrtereignis-Eingaben werden auf diesem Gerät automatisch gesichert. Beim erneuten Öffnen des Arbeitsberichts wird der letzte Bearbeitungsstand wieder angezeigt. Browserdaten nicht löschen und keinen privaten Modus verwenden. Browser-GPS kann beim Schließen der Seite unterbrochen werden; Android verwendet den Standortdienst.
7. **Löschen:** Solange der Bericht noch nicht endgültig synchronisiert ist, kann er über „Arbeitsbericht löschen“ oder in der Monatsliste gelöscht werden. Laufendes GPS wird gestoppt. Zugehörige lokale GPS-Daten und Belege werden entfernt; bei fehlender Verbindung wird die Serverlöschung nachgeholt. Bereits endgültig synchronisierte Berichte sind geschützt. Andere Berichte bleiben erhalten.
8. **Zwischenspeichern:** Sichert zugleich die vorhandenen GPS-Aufzeichnungen, ohne die Aufzeichnung zu beenden. Ein laufender Android-Journalstand wird vorher eingelesen. Bei Verbindung werden die GPS-Daten zusätzlich serverseitig gesichert. Während dieses Abgleichs eingehende GPS-Punkte bleiben erhalten. Unvollständige Formulare bleiben als lokaler Bearbeitungsstand gesichert; für die endgültige Synchronisation müssen die Pflichtangaben vollständig sein.

## Manuelle Standzeit ohne GPS

Wenn keine GPS-Aufzeichnung läuft, startet der **grüne Button „Start Stand“** eine manuelle Standzeit. Die laufenden Minuten erscheinen in **roter Fettschrift**, der Button wird rot und heißt **„Ende Stand“**. Die Anzeige läuft aus dem gespeicherten Startzeitpunkt weiter und wird nach einem Neuladen wiederhergestellt. Dafür sind weder GPS-Freigabe noch HTTPS erforderlich. Während einer manuellen Standzeit kann GPS nicht zusätzlich gestartet werden.

Nach „Ende Stand“ erscheint der Halt mit Beginn und Ende in derselben Standzeitenliste, auch bei einer Dauer unter vier Minuten. DS100 oder Bahnhofsname ergänzen/auswählen, Grund auswählen oder als Text eingeben, anschließend „↑ Übernehmen“. Manuelle Halte enthalten keine erfundenen Kartenpunkte. Ihre Zeitstempel und Angaben werden beim Zwischenspeichern zusammen mit vorhandenen GPS-Daten gesichert und beim Löschen des Berichts mit entfernt. Die Zugfahrtdetails arbeiten weiterhin minutengenau; wenn Beginn und Ende innerhalb derselben Minute liegen, bleibt der Halt in der Standzeitenliste und kann dort bearbeitet werden; die ursprünglichen Zeitstempel bleiben intern erhalten.

## Uhrzeiten, Löschen und Kartenfokus

Beginn und Ende einer Standzeit erscheinen immer als **HH:MM ohne Sekunden**, einschließlich alter Aufzeichnungen, Kartenbeschriftungen und bisheriger Angaben. Auch das manuelle Ende wird in diesem Format eingegeben. Das zugehörige Datum bleibt intern erhalten; bei einem fehlenden Ende vor der Startuhrzeit wird der folgende Tag verwendet. Standort- oder Grundänderungen kürzen keine ursprünglich gemessenen Zeitstempel.

Jede offene Standzeit hat einen **„Löschen“**-Button. Nach Bestätigung verschwindet der Halt aus der Liste und sein Marker aus der Karte. Die Löschmarkierung bleibt beim Neuladen und nach Zwischenspeichern/Synchronisieren erhalten, auch wenn die GPS-Punkte später erneut ausgewertet werden. Messpunkte und bereits übernommene Zugfahrtdetails bleiben erhalten. Übernommene Einträge können in den Zugfahrtdetails entfernt werden.

Ein Klick auf die Standzeitenzeile, eines ihrer Eingabefelder oder den Kartenpunkt wählt den Halt aus: Sein Punkt wird doppelt so groß, auf die Kartenmitte gesetzt und auf mindestens Zoomstufe 16 herangezoomt. Das funktioniert auch für ältere GPS-Halte und deren übernommene Einträge. Manuelle Halte ohne GPS-Punkt erzeugen weiterhin keinen erfundenen Marker. **„Position folgen“** aktiviert wieder die Live-Nachführung.

## Ältere Aufzeichnungen und chronologische Zugfahrtdetails

Die aktuellen GPS-Regeln gelten automatisch beim Laden aller älteren Aufzeichnungen mit erhaltenen GPS-Punkten. Rohpunkte, vorhandene Standort-/Grundangaben und übernommene Zugfahrtereignisse bleiben erhalten; ein erneut zusammengefasster Halt wird nicht nochmals zur Übernahme angeboten, wenn er bereits übernommene Teile enthält. Alle Zeilen in den Zugfahrtdetails werden nach Beginn, Ende und Kennung chronologisch sortiert: beim Laden alter Berichte und Entwürfe, beim Eintragen, nach Änderungen, beim Speichern und für neu erstellte Dokumente. Vorhandene archivierte PDFs bleiben unverändert.

## Kompakter Dienstblock und GPS-Bereich

Im Dienstblock steht links oben die umrahmte Dienstart-Gruppe: **DS** Dienstschicht, **BS** Bereitschaft, **RBS** Rufbereitschaft, **AS** Ausfallschicht, **U** Urlaub, **K** Krank. Die gespeicherten Dienstartwerte und Berechnungsregeln bleiben unverändert; vollständige Bezeichnungen sind als Tooltip und für Screenreader verfügbar.

Links darunter stehen die vier Kennzahlen in einer gemeinsamen Gruppe. Die Beschriftungen lauten **Σ- AZ**, **Min. ☕**, **AZ inkl. ☕**, **Bisher-☕**. Passend unter jeder Beschriftung steht nur der Wert in **h:mm**, ohne Einheiten oder weiteren Text. Die Hinweise zu verpflichtenden bzw. empfohlenen Pausen bleiben verfügbar.

Dienstbeginn steht rechts oben, Dienstende direkt darunter. Darunter folgt die umrahmte Ausbleibe-Gruppe. Der rechte Bereich nutzt auf großen Bildschirmen etwa ein Drittel des Dienstblocks. Auf schmalen Bildschirmen werden die Gruppen untereinander angeordnet.

Die Zugfahrtdetails stehen über dem GPS-Bereich. Dieser ist beim Öffnen zunächst geschlossen. **+** oben rechts öffnet Bedienung, Standzeitenliste und Karte; **−** schließt sie wieder. Laufendes GPS und manuelle Standzeiten werden dadurch nicht beendet. Beim Auswählen eines GPS-Halts in den Zugfahrtdetails wird die Karte bei Bedarf automatisch eingeblendet.

## Anleitung und Hilfe für das gesamte TF-Portal

Die Kachel **Anleitung und Hilfe** öffnet eine nach Modulen und Themen gegliederte Übersicht mit kurzen Beschreibungstexten. Die Themenliste steht links, auf kleinen Bildschirmen oben. Eine Suche findet Themen auch über Wörter im Erklärungstext. Die Anleitung erklärt die Bedienung in einfachem Deutsch und in geordneten Schritten.

**? Hilfe** im Kopfbereich öffnet die Erklärung zum aktuellen Modul. Die bisherigen Hilfe-Schaltflächen im Arbeitsbericht und bei GPS führen ebenfalls in diese gemeinsame Hilfe. **X oben links** schließt das Hilfefenster und bringt den Eingabefokus zurück. Das **Drucker-Symbol oben rechts** öffnet den Druckdialog für die ausgewählte Anleitung. Persönliche Formularwerte und andere Portalbereiche werden dabei nicht gedruckt. In Android öffnet sich der System-Druckdialog mit einem eigenen, vom eigentlichen Portal getrennten Druckdokument. Eine aktuelle APK enthält auch die Hilfedateien.

Der gemeinsame Katalog liegt in `backend/lokzeitleiste/static/tf-help-content.js`. Neue Module und Bedienungsänderungen müssen dort mit erklärt werden; die Hilfepflege ist in `AGENTS.md` festgelegt und die vollständige Abdeckung der Modulkacheln wird automatisch geprüft. Noch nicht freigeschaltete Funktionen werden ausdrücklich als nicht verfügbar erklärt.

## Testserver aktualisieren

Für den eigenständigen, mit `install-ctlsoftware-test.sh` eingerichteten Testserver:

```bash
curl -fL https://raw.githubusercontent.com/omueller369/LokZeitleiste/setup/debian-testumgebung/install-ctlsoftware-test.sh -o install-ctlsoftware-test.sh
sudo bash install-ctlsoftware-test.sh --update
```

Die Update-Routine aktualisiert den normalen Testbranch und sichert zuvor Datenbank, Konfiguration und bisherigen Backend-Code unter `/etc/ctlsoftware-test-setup/backups/`. Dies gilt auch, wenn die Anwendung zuletzt aus dem festen RC1-Quellpaket installiert wurde, sofern der ursprüngliche Testserver-Checkout noch vorhanden ist. Für diesen Wechsel nicht den alten RC1-Pfad mit `--source` angeben.

Danach Portal neu laden; die Softwareinformation zeigt `0.26`. Docker/ISPConfig verwenden ihre jeweils eigene Update-Anleitung. Eine vorhandene APK enthält gegebenenfalls zusätzlich eine gebündelte Offline-Oberfläche; für deren Stand 0.26 die neu gebaute Tablet-Test-APK mit demselben Signierschlüssel verwenden.


### Persönliche TF-Notizen und Du-Anrede

Im TF-Portal ergänzt das Modul **Notizen** persönliche, serverseitig zum TF-Konto gespeicherte Notizen. **Neu hinzufügen** öffnet Titel (bis 120 Zeichen) und Text (bis 1000 Unicode-Zeichen) mit Restzeichenzähler. Die Liste zeigt Titel und Erstelldatum als **dd.mm.yy HH:MM** (Europe/Berlin), neueste zuerst. Ein Klick öffnet den vollständigen Text; **Bearbeiten** ermöglicht Änderungen. Der Papierkorb pro Zeile löscht nach ausdrücklicher Rückfrage die ganze Notiz. Abbrechen erhält sie. Erstelldaten bleiben bei Bearbeitung unverändert; Revisionsprüfungen schützen vor dem Überschreiben oder Löschen zwischenzeitlich geänderter Notizen. Für Speichern und Laden ist eine Serververbindung nötig; bei Fehlern bleibt die laufende Eingabe erhalten.

Sämtliche zentralen Hilfetexte und die Bedienhinweise im Hilfeleser verwenden die Du-Anrede. Eine eigene gruppierte Notiz-Anleitung sowie eine Prüfung gegen förmliche Anrede sind ergänzt. Android bündelt das Notizmodul zusammen mit dem Portal. Die neue Datenbanktabelle wird durch den bestehenden idempotenten `init_db`-Ablauf angelegt.


### Tagmodus und Nachtmodus

Ein Sonne-/Mond-Symbol im Kopf schaltet die Darstellung für Startseite, TF-Module, gemeinsame Seiten, Verwaltung und Dialoge um. Die Browser-/Geräteauswahl bleibt über Seitenwechsel und Neuladen erhalten; andere Tabs übernehmen Änderungen. Ohne Speicherzugriff funktioniert die aktuelle Seite weiterhin. Der Standard bleibt der Tagmodus. Warnungen, Plan- und Berichtsstatus erhalten eigene dunkle Farben. Originalbilder, Dokumentvorschauen, Unterschriften und Druckausgaben werden nicht invertiert. Die Android-App bündelt dieselben Darstellungsdateien. Die zentrale Du-Hilfe erklärt den Umschalter.
