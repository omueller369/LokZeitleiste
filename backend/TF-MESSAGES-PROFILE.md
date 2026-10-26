# TF-Nachrichten, persönliche Daten und Portalrahmen

Nach dem normalen Update ist die zusätzliche Dashboard-Kachel **Kurznachrichten** verfügbar:

```bash
sudo bash install-ctlsoftware-test.sh --update
```

## Nachrichten

`/tf/nachrichten` bietet ein privates systeminternes Postfach. **neue Nachricht schreiben** öffnet ein Overlay mit Mehrfachauswahl der TF, „Alle TF's“, Betreff, Nachricht (maximal 1000 Zeichen mit Restzähler) und optional einem Dateianhang bis 10 MB. Die Empfängerliste zeigt ausschließlich Namen. Bei „Alle TF's“ erhalten alle aktuell aktiven TF einschließlich des Absenders eine Zustellung. Ausgeschiedene oder gesperrte TF stehen nicht zur Auswahl.

**Gesendete** wechselt zur eigenen Versandliste mit Datum, Uhrzeit, Empfängernamen und Betreff. Ein Zeilenklick öffnet Text und Anhang schreibgeschützt. **Posteingang** wechselt zurück. Die Versandansicht verändert keine Lesestatus der Empfänger; das Löschen einer Empfängerkopie entfernt die Nachricht nicht aus der Versandansicht.

Nachrichten sind nach Datum/Uhrzeit absteigend sortiert; bei mehr als 50 Einträgen kann geblättert werden. Ein Zeilenklick öffnet die Nachricht schreibgeschützt und markiert sie als gelesen. Die Icons erlauben Löschen und Wechsel zwischen gelesen/ungelesen. Ungelesene Nachrichten tragen zusätzlich eine Neu-Markierung. Löschen entfernt nur die eigene Zustellung, nicht die Nachricht aus anderen Postfächern. Das Weiterleitungs-Overlay unterstützt wiederum mehrere TF oder alle TF und übernimmt Text und Anhang. Es versendet keine SMTP-E-Mail.

Bilder werden als anklickbare Speichervorschau angezeigt. PDFs erhalten eine eingebettete Vorschau mit zusätzlichem Speicherlink. Andere Dateitypen erscheinen als speicherbare Dateikarte. Die Dateivorschau wird als authentifiziert geladenes Blob erzeugt; Namen und Text werden ausschließlich als Text dargestellt.

## Kopf- und Fußbereich

Der gemeinsame Portalrahmen enthält links das bereitgestellte Logo der CTL Logistics GmbH und **Abmelden**. Daneben stehen **TF-Portal**, der eigene Name, die eigene TF-Nummer und **Letztes Login:** mit Datum/Uhrzeit in Berliner Zeit. Ab dem Update werden erfolgreiche Anmeldungen in einer eigenen Tabelle protokolliert. Für ältere Sitzungen wird der letzte bekannte Zeitpunkt aus den vorhandenen Sitzungslaufzeiten hergeleitet.

Bei ungelesenen Nachrichten von anderen TF erscheint die Glocke mit Anzahl und Link zum Nachrichtenmodul. Der Zähler wird nach Lesen/Löschen sowie regelmäßig und beim erneuten Fokussieren aktualisiert. Eigene Nachrichten lösen keine Glockenbenachrichtigung aus.

Im Footer stehen Softwaretitel und der zentral hinterlegte Versionsstand. **Mein Konto / Passwort** ist als eigene Dashboard-Kachel verfügbar und verweist auf **Meine Daten**. Der Footer enthält ausschließlich Softwaretitel und Versionsstand. Das separate Modul **Meine Arbeitszeiten** entfällt für TF; alte Direktaufrufe werden zum TF-Portal umgeleitet. Die Zeiterfassung der Verwaltung und der TF-Arbeitsbericht bleiben verfügbar. **Meine Dokumente** entfällt als Headerlink; die Dokumentenverwaltung bleibt über ihre Dashboard-Kachel erreichbar. Die bestehenden Rückkehrbuttons zum TF-Portal bleiben bestehen.

## Persönliche Übersicht

`/tf/me` zeigt die eigenen gespeicherten Personal- und Vertragsdaten, alle hinterlegten Adressen und das Foto. Dazu gehören unter anderem TF- und Personalnummer, Geburtsdatum, Geschlecht, Staatsangehörigkeit, E-Mail, Dienstart, Wochenarbeitszeit, Urlaub, BahnCard und Gültigkeit, Ein-/Austrittsdatum, Heimatbahnhof und Sperrstatus. **Passwort ändern** führt zum bestehenden Passwortwechsel. Zugangsdaten, Passwort-Hashes und Sitzungstoken werden nicht ausgegeben. Dies ist eine persönliche Stammdatenübersicht; vorhandene Arbeitsberichte, Dokumente und Pläne bleiben in ihren jeweiligen Modulen.

## Technik und Logo

`init_db` legt `account_login_stamps`, `tf_messages`, `tf_message_deliveries` und `tf_message_attachments` automatisch an. Der Zugriff auf Nachricht, Lesestatus und Anhang ist an die eigene Zustellung gebunden. Die TF-Nummer wird ausschließlich im eigenen Portalrahmen und in der eigenen Datenübersicht ausgegeben, nicht in Empfängerlisten oder Nachrichten-Metadaten.

Die unverändert im Repository abgelegte Datei `static/ctl-logistics-logo.jpg` stammt aus dem vom Benutzer bereitgestellten Upload. Das TF-Web-App-Symbol wird daraus mit weißem Rand erzeugt. Die Manifest-URLs enthalten eine neue Symbolversion, sodass unterstützende Browser eine Aktualisierung erkennen können; bereits installierte Web-App-Symbole werden nach den Regeln des jeweiligen Betriebssystems aktualisiert.

## Kurznachrichten zwischen TF und Verwaltung

Das Backend bietet `/admin/messages` über Dashboard und Menü Sonstiges. Alle angemeldeten Sachbearbeiter und Administratoren mit geändertem Initialpasswort können ihr eigenes Postfach nutzen. Die Empfänger sind in TF und Sachbearbeiter gegliedert; angezeigt werden nur Namen. „Alle TF's“ umfasst weiterhin ausschließlich TF. Antworten gehen ausschließlich an den ursprünglichen Absender und unterstützen optionale Anhänge bis 10 MB. Posteingang, Gesendete, Weiterleiten und Löschen funktionieren in beiden Bereichen gleich. Vorhandene Nachrichten bleiben erhalten; es ist keine Datenmigration nötig.
