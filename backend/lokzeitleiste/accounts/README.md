# Verwaltungsmitarbeiter, Modulrechte und Passwörter

In der Administration **Verwaltungsmitarbeiter und Rechte** öffnen (`/admin/staff`). Globale Administratoren können neue Verwaltungsmitarbeiter anlegen und deren Stammdaten und Modulfreigaben später bearbeiten. Diese Konten erhalten die Rolle `staff`; die bestehenden globalen Administratoren behalten sämtliche Rechte.

Erfasst werden Vorname, Nachname, Benutzername, Initialpasswort, Nationalität, Geburtsdatum, Kostenstelle sowie eine bis zehn Adressen mit Straße, Hausnummer, PLZ und Ort. PLZ und Kostenstelle sind Textfelder, damit führende Nullen und internationale Angaben erhalten bleiben. Benutzernamen sind eindeutig und verwenden 3–64 Kleinbuchstaben, Ziffern, Punkte, Unterstriche oder Bindestriche. Das Initialpasswort muss mindestens zwölf Zeichen enthalten und wird nur als gesalzener Hash gespeichert; Listen und Detailansichten liefern niemals Passwort oder Passwort-Hash zurück.

## Module und Freigaben

Die Checkboxen bilden eine Hierarchie: Administration enthält Lesen und Schreiben; Lesen und Schreiben enthält Lesen. Ohne Auswahl ist das Modul gesperrt. Die Datenbank speichert pro Modul eine Stufe von 0 bis 3. APIs prüfen diese Freigaben unabhängig davon, ob Bedienelemente im Browser sichtbar sind.

| Modul | Lesen | Lesen und Schreiben | Administration |
|---|---|---|---|
| Mitarbeiter-Stammdaten | Tf-Stammdaten ansehen | E-Mail und Bundesland ändern | Zusätzlich Tf anlegen und deren Passwort zurücksetzen |
| Ruhetags- und Urlaubsplanung | Pläne, Verlauf und PDF ansehen | Zusätzlich Pläne bearbeiten und Excel importieren | Umfasst die bisherigen Planungsfunktionen mit Schreibrecht |
| Arbeitszeitkorrekturen | Einträge, Summen und Korrekturverlauf ansehen | Zusätzlich Zeiten korrigieren und fehlgeschlagene Benachrichtigungen erneut starten | Umfasst die bisherigen Korrekturfunktionen mit Schreibrecht |
| Monatsabrechnung und PDF-Versand | Monatswerte und Versandstatus ansehen | Derzeit dieselben Funktionen, da dieses Modul noch keine eigenen Schreibaktionen besitzt | Derzeit dieselben Funktionen |
| Verwaltungsmitarbeiter und Berechtigungen | Stammdaten und Freigaben ansehen | Stammdaten anderer verwaltbarer Konten ändern, ohne Rechte zu ändern | Zusätzlich Konten anlegen, Freigaben ändern und Passwörter zurücksetzen |

Die Auswahl eines Mitarbeiters in Planung, Arbeitszeit oder Abrechnung liefert ohne Stammdaten-Freigabe nur ID, Name und Personalnummer. Ohne Planungsfreigabe enthalten Abrechnungsansichten die Plansummen und Vollständigkeit, aber keine einzelnen Planungszeilen oder Notizen. Eine Verwaltungskraft darf nur Rechte bis zur Höhe ihrer eigenen Modulfreigaben vergeben. Konten mit höheren Rechten, globale Administratoren und die eigenen Freigaben kann sie nicht verwalten. Globale Administratoren können alle Verwaltungsmitarbeiter verwalten. Neue API-Endpunkte benötigen eine ausdrückliche Zuordnung zur Rechteprüfung.

## Initialpasswort und eigener Passwortwechsel

Nach dem ersten Login eines neu angelegten Verwaltungsmitarbeiters erfolgt der Wechsel zu `/account`. Solange das Initialpasswort nicht geändert wurde, blockiert das Backend sämtliche Modulzugriffe. Zulässig bleiben nur Kontoidentität, Passwortwechsel und Abmeldung. Dasselbe gilt nach einem administrativen Passwort-Reset. Initialpasswörter persönlich übergeben; sie werden nicht per E-Mail verschickt.

Auf der Seite **Mein Passwort ändern** geben Mitarbeiter und Administratoren ihr aktuelles Passwort und zweimal das neue Passwort ein. Das neue Passwort muss mindestens zwölf Zeichen enthalten und sich vom bisherigen unterscheiden. Nach erfolgreicher Änderung werden alle Sitzungen des Kontos beendet; die Anmeldung erfolgt mit dem neuen Passwort. Die Datei `/var/lib/lokzeitleiste/admin-initial-password` enthält weiterhin das ursprünglich vom Setup erzeugte Passwort und wird nicht aktualisiert.

Neu angelegte Tf-Konten müssen ihr Initialpasswort ebenfalls ändern. Die Android-App ab Version **0.7** zeigt dafür vor der Monatsansicht einen Passwortwechsel an und bietet später **Passwort ändern** in der Monatsansicht. Alternativ können Tf die Browserseite `/account` verwenden. Ältere App-Versionen können den erzwungenen Passwortwechsel nicht anzeigen und müssen aktualisiert werden beziehungsweise den Wechsel zunächst über die Browserseite durchführen. Bestehende Konten werden beim Update nicht pauschal auf Initialpasswort zurückgesetzt.

## Administrativer Reset

Bei Verwaltungsmitarbeitern **Passwort zurücksetzen** auswählen und ein neues Initialpasswort vergeben. Bei Tf befindet sich diese Aktion in deren Zeile der Administration. Dafür ist die jeweilige Modulstufe Administration erforderlich. Alte Sitzungen werden beendet und das Konto muss beim nächsten Login das Initialpasswort ersetzen. Das eigene Konto verwendet stattdessen die Seite **Mein Passwort ändern**; ein Reset des eigenen Kontos über die Verwaltungsaktion wird abgewiesen.

Änderungen an Stammdaten und Freigaben beenden ebenfalls die Sitzungen des betroffenen Verwaltungsmitarbeiters. Die folgenden Login-Anfragen prüfen die aktualisierten Berechtigungen. Kontoanlage, Stammdaten-/Rechteänderung, eigener Passwortwechsel und Reset werden mit handelndem Konto, Zielkonto und Zeitpunkt in `account_audits` protokolliert; Passwörter werden dort nicht gespeichert.

## Update und Prüfung

Im bestehenden Setup-Branch:

```bash
git pull --ff-only
sudo bash setup.sh
```

Beim Start legt die API zusätzliche Tabellen für Verwaltungsprofile, Adressen, Modulrechte, Passwortwechselpflicht und Kontoaktionen an. Bestehende Tabellen brauchen für diese Erweiterung keine Spaltenänderung. Die Android-App separat neu bauen und installieren.

Die Tests prüfen Initiallogin-Sperre, eigenen Passwortwechsel, Reset mit Sitzungsende, lesende und schreibende Freigaben, fehlende Freigaben, unzulässige Rechteweitergabe, fremde Module, Profilvalidierung und Ursprungsprüfung. Ein Containerlauf gegen MySQL auf der VM und ein Android-Build stehen hier noch aus.

## API

- `POST /api/v1/admin/staff`, `GET /api/v1/admin/staff`, `PUT /api/v1/admin/staff/{id}`: Verwaltungsmitarbeiter.
- `GET /api/v1/admin/modules`, `GET /api/v1/admin/me`: Modulliste und aktuelle Freigaben.
- `POST /api/v1/admin/accounts/{id}/reset-password`: neues Initialpasswort und erneute Wechselpflicht.
- `POST /api/v1/account/login`, `GET /api/v1/account/me`, `POST /api/v1/account/logout`: eigenes Konto im Browser.
- `POST /api/v1/account/password`: aktuelles und neues Passwort mit Bestätigung; Cookie oder Tf-Bearer-Token.

Cookie-basierte Schreibzugriffe und Browser-Logins prüfen `PUBLIC_ORIGIN`. Tf-Bearer-Token berechtigen ausschließlich das eigene Konto und niemals zu Verwaltungsmodulen.
