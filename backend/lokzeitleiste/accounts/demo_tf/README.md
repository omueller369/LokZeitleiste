# 20 fiktive TF für die Testumgebung

Alle Personen, Adressen und Profilbilder sind fiktiv. Die individuellen Porträts wurden mit der eingebauten Bildgenerierung erstellt; keine realen Mitarbeiterbilder wurden verwendet. Die Prompt-Angaben stehen in `people.json` (Name, Alter und Erscheinungsbild), der gemeinsame Prompt steht unten. Die für die Anwendung bestimmten JPEG-Dateien sind in `portraits/01.jpg` bis `20.jpg` gespeichert. Sie wurden durch die reguläre Foto-Upload-Normalisierung der Anwendung verarbeitet; beim Import wird diese Validierung erneut verwendet.

## Datensätze

- 14 männlich, 4 weiblich, 1 divers, 1 keine Angabe.
- 3 Grenz-TF, 2 Grenz- und Strecken-TF, 15 Strecken-TF.
- Zufällige eindeutige sechsstellige TF-Nummern aus 787000–787999. Bereits vorhandene Loginnamen werden bei der Auswahl nicht erneut verwendet; fehlen 20 freie Nummern, wird ohne Löschung abgebrochen.
- Login-Initialpasswort für alle: `tomcom123456` (12 Zeichen). Speicherung ausschließlich als individuell gesalzener PBKDF2-Prüfwert; beim ersten Login muss das Passwort geändert werden.
- 40 Wochenstunden und 30 Urlaubstage für alle.
- Geburtstage ergeben am Ausführungstag ein Alter von 28–64 Jahren.
- Beitrittsdatum zufällig zwischen 01.01.1995 beziehungsweise dem 18. Geburtstag und dem Ausführungstag.
- 18 BahnCard 100, 1 BahnCard 50, 1 keine BahnCard. Die 19 Ablaufdaten sind unterschiedlich und liegen 120–365 Tage nach dem Berliner Ausführungstag.
- Alle 16 Bundesländer sind vertreten, Berlin genau viermal. Sachsen ist zusätzlich zweimal vertreten, damit genau 20 Personen entstehen.
- Eindeutige fünfstellige Personalnummern als Text, einschließlich `00001` als Beispiel für eine führende Null.
- E-Mail für alle: `omueller369@gmail.com`. Das ist nur ein Stammdatenfeld; die Routine versendet keine E-Mails und verbindet keine Postfächer.
- Je eine fiktive Adresse als Postanschrift mit dem jeweiligen Bundesland; Staatsangehörigkeit DE; kein Austrittsdatum und keine sofortige Sperre.

## Auf dem Server ausführen

Die Repository-Aktualisierung allein löscht keine Daten. Die Routine läuft ausschließlich bei ausdrücklichem Aufruf. Sie ist nicht Teil des normalen Containerstarts oder `init_db`.

Im Repository-Verzeichnis:

```sh
cd backend
bash testenv/control.sh start
bash testenv/control.sh backup
bash testenv/control.sh demo-tf
```

`demo-tf` löscht **alle vorhandenen TF und die über Fremdschlüssel zugehörigen Daten** und legt genau 20 neue TF an. Dazu gehören Arbeitszeiten, Planungen, Belege/PDFs, Änderungsprotokolle, Sessions, Fotos, BahnCard-/Stammdaten und lokale Postfachkonfigurationen, Tokens und Entwürfe. Admin-/Verwaltungskonten und deren eigenständige Arbeitszeitdaten bleiben erhalten, ebenso wiederverwendbare Schichtmodelle und die Bahnhofsdatenbank. Externe E-Mail-Postfächer oder Daten auf einzelnen Endgeräten werden nicht gelöscht.

Für andere Compose-Konfigurationen, im API-Container:

```sh
python -m lokzeitleiste.accounts.seed_demo_tf --replace-all-tf
```

Ohne `--replace-all-tf` wird nur eine JSON-Vorschau erzeugt; dabei werden weder eine Datenbankverbindung hergestellt noch Daten verändert. Optional `--seed 23` für reproduzierbare Testfälle. Auch mit Seed werden Datumsspannen am tatsächlichen Ausführungstag berechnet.

Vor dem Löschen werden alle Daten und alle 20 Fotos validiert. Löschen und Neuanlage erfolgen in **einer Transaktion** mit aktivierten Fremdschlüsselprüfungen. Bei Fehlern wird zurückgerollt. Für neue Benutzer-IDs werden bereits verwendete IDs nicht erneut benutzt. Die Routine gibt anschließend eine Übersicht der neuen Personen und TF-Nummern aus, keine Passwortprüfwerte.

## Gemeinsamer Bildprompt

Built-in `image_gen`, `photorealistic-natural`: einzelnes quadratisches Mitarbeiterporträt einer vollständig fiktiven erwachsenen Person, Name und Alter aus `people.json`, individuelles Erscheinungsbild aus `appearance`, Kopf und Schultern frontal, zentriertes Gesicht, neutraler warmgrauer Studiohintergrund, natürliche weiche Beleuchtung, freundlicher professioneller Ausdruck, realistische Haut, Alltagskleidung ohne Bahnlogos. Kein Text, kein Wasserzeichen, keine weiteren Personen, kein Kontaktbogen.

Die Altersangabe im Bildprompt beschreibt den Erstellungszeitpunkt; die importierten Geburtsdaten werden bei einer späteren Ausführung erneut passend zur vorgegebenen Altersspanne erzeugt.
