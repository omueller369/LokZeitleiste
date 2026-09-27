# LokZeitleiste v0.4

Android-Studio-Projekt für eine monatliche Arbeitszeiterfassung auf einem 10-Zoll-Tablet.

## Funktionen

- Lokale Anmeldung mit Benutzername und Passwort; die Sitzung bleibt auf demselben Gerät erhalten. Benutzerkonten können auf dem Gerät angelegt werden. Passwortprüfwerte werden mit PBKDF2 und zufälligem Salt gespeichert.
- Monat wechseln, Erfassung anlegen und löschen, Einträge als Tabelle anzeigen.
- Erfassungsarten: Rufbereitschaft, Bereitschaft, Zugfahrt, Ausfallschicht, Krank, Urlaub und Sonstige Erfassung.
- Footer mit Arbeitszeit, Gastfahrtzeit, Urlaubstagen, Nachtstunden und Sonntagsstunden.
- Separater Zugfahrtbereich aus LokZeit v0.3: Dienst und Zugnummer, manuelle Standzeiten, GPS-Vorschläge für Ankunft und Abfahrt, OSM-Betriebsstellen mit DS100-Suche, Gründe, Notizen, Korrektur und Löschung. LokZeit selbst bleibt unverändert.
- Rufbereitschaft erfasst Datum, Beginn und Ende. Bei auswärtigem Aufenthalt werden Dienstwohnung oder Hotel mit Hotelnamen erfasst. Für Rufbereitschaft werden keine Pause, Gastfahrt und Notiz abgefragt.
- Nach der derzeit vorgegebenen Tarifregel darf Rufbereitschaft nur am selben Tag zwischen 08:00 und 20:00 Uhr liegen und höchstens acht Stunden dauern. Die Eingabe wird beim Speichern dagegen geprüft.
- Bereitschaft wird wie Rufbereitschaft mit Zeitraum und optionaler Auswärtigkeit samt Unterkunft erfasst. Sie kann zu beliebiger Tageszeit und über Mitternacht liegen. Bis zur Bestätigung der Fachregel gilt in v0.4 auch hier eine Höchstdauer von acht Stunden. Die Vorgaben der Personalplanung werden manuell eingetragen; es gibt noch keine Schnittstelle zu einem Planungssystem.
- Eine gespeicherte Rufbereitschaft oder Bereitschaft kann innerhalb ihres Zeitraums in eine Zugfahrt übergehen. Der Tf trägt Übergangsdatum, Übergangszeit und Ende der Zugfahrt ein. Der ursprüngliche Eintrag wird am Übergang beendet, und eine Zugfahrt mit dem Vermerk über den Ursprung wird angelegt. Erfolgt der Übergang sofort zu Beginn, entfällt der ursprüngliche Eintrag. Der Wechsel erzeugt noch keinen automatischen Dienst oder Standzeitdatensatz im separaten LokZeit-Zugfahrtbereich.

## Vorläufige Berechnung in v0.1

- Zugfahrt, Bereitschaft und Sonstige Erfassung zählen als Arbeitszeit; Pause wird abgezogen.
- Rufbereitschaft, Ausfallschicht, Krank und Urlaub zählen vorerst nicht als Arbeitszeit. Urlaub wird in Tagen gezählt.
- Nachtzeit gilt vorläufig von 22:00 bis 06:00. Sonntag gilt 00:00 bis 24:00. Zeiträume über Mitternacht werden erkannt.
- Da die Lage der Pause noch nicht erfasst wird, ziehen Nacht- und Sonntagsberechnung die Pause pauschal vom jeweiligen Überlapp ab. Monatssummen ordnen einen Dienst derzeit dem Startdatum zu.
- Gastfahrtzeit wird als Teil eines Eintrags erfasst und separat summiert; sie wird nicht zusätzlich zur Arbeitszeit addiert.
- Ausbleibe ist als künftige Vergütung für den Tf außerhalb seiner Wohnung vorgesehen. Angaben zur Auswärtigkeit und Unterkunft werden bereits gespeichert; die 24-Stunden-Regel für einen vollen Kalendertag von 00:00 bis 23:59 und die 8-Stunden-Regel für andere Zeiträume werden noch nicht in eine Vergütung umgerechnet. Schichten über Mitternacht benötigen dafür eine fachliche Festlegung zur Aufteilung.

Diese Regeln müssen vor einer produktiven Verwendung mit den tatsächlichen Tarif- und Betriebsregeln abgeglichen werden.

## Grenzen dieser ersten Version

Konten und Daten liegen ausschließlich auf dem jeweiligen Gerät. Es gibt keinen Server, keine Synchronisierung, keine zentrale Benutzerverwaltung und keine Passwortwiederherstellung. Ein selbst angelegtes lokales Konto ist keine verifizierte Mitarbeiteridentität. Die Anmeldung bleibt bis zum manuellen Abmelden aktiv.

Die Zugfahrt-Standzeiten aus LokZeit sind pro lokalem Benutzer getrennt gespeichert, aber noch nicht mit Monatseinträgen verknüpft. Für die Monatsübersicht wird eine Zugfahrt derzeit separat angelegt. Das alte LokZeit-Repository wird nicht verändert.

## Öffnen

Den Ordner in Android Studio öffnen und Gradle synchronisieren. Android SDK 35 wird benötigt. Ein Android-Build konnte in der Arbeitsumgebung ohne SDK und Gradle nicht ausgeführt werden.
