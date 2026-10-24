# Mitarbeiterpostfächer, Anmeldung und Oberfläche

Die vollständige Neuinstallation für Ubuntu 26.04 bleibt `install-ctlsoftware-test.sh`. Für den bereits eingerichteten eigenständigen CTL-Testserver unterstützt die Datei jetzt zusätzlich `--update`.

## Bestehenden Testserver aktualisieren

```bash
curl -fL https://raw.githubusercontent.com/omueller369/LokZeitleiste/setup/debian-testumgebung/install-ctlsoftware-test.sh -o install-ctlsoftware-test.sh
sudo bash install-ctlsoftware-test.sh --update
```

Das Update ist ausschließlich für den mit diesem Script eingerichteten Server bestimmt. Es aktualisiert den Checkout per Fast-Forward, sichert die Datenbank, Konfiguration und den bisherigen Backend-Code unter `/etc/ctlsoftware-test-setup/backups/`, aktualisiert Anwendung und Tabellen und richtet die automatische Postfachanlage ein. Bestehende Arbeitsberichte, Bilder und Postfachnachrichten werden erhalten. Bei Fehlern die ausgegebene Fehlermeldung prüfen; Sicherung vor einem erneuten Versuch aufbewahren. Ein fehlgeschlagenes Update führt nicht automatisch einen Restore durch.

## Persönliche E-Mail-Adressen

Die 20 importierten Demo-TF erhalten einmalig persönliche Adressen unter `ctl-software.io-goerlitz.eu`. Ihre bisherige gemeinsame Profiladresse wird ersetzt; Portalpasswörter werden nicht zurückgesetzt. Das anfängliche Postfachpasswort ist `tomcom123456`. Die Demo-Postfächer werden bei späteren Updates nicht erneut zurückgesetzt.

Neue TF und Verwaltungsmitarbeiter erhalten bei Auswahl einer verwalteten Domain ein Postfach mit demselben Initialpasswort wie im Portal. Das Postfachpasswort und das Portalpasswort sind anschließend eigenständige Zugangsdaten; eine spätere Portalpasswortänderung ändert das Mailpasswort nicht.

In App Grundwerte werden die Maildomains gepflegt. Die Vorschläge haben das Muster `vorname.nachname`; Umlaute werden als ae/oe/ue und ß als ss geschrieben. Bei Kollision folgt das zweistellige Geburtsjahr, bei weiteren Kollisionen eine laufende Zahl. Der Server prüft die Eindeutigkeit erneut. Bereits angelegte lokale Postfächer können durch eine reine Profiländerung nicht umbenannt werden, damit Nachrichten und Zugangsdaten nicht verloren gehen.

„Eigene Domain“ erlaubt eine vollständige externe Adresse mit Formatprüfung. Ein externes Postfach wird dadurch nicht bei STRATO, Gmail oder einem anderen Anbieter angelegt und erhält keine lokalen Zugangsdaten. Versand aus dieser Adresse benötigt eine separat eingerichtete Mailverbindung.

Zusätzliche verwaltete Domains müssen dem Betreiber gehören und beim Provider passend eingerichtet werden: A/MX auf diesen Server, SPF, DKIM mit dem bestehenden ctl-Schlüssel für die zusätzliche Domain und DMARC. Der Mailclient verwendet weiterhin den zertifizierten Servernamen `ctl-software.io-goerlitz.eu`. Domainauswahl allein ändert keine Provider-DNS-Einträge.

Die vier bisherigen Funktionspostfächer info/diso/vkplanung/railpool bleiben erhalten und leiten weiterhin zusätzlich an Gmail weiter. Persönliche Mitarbeiterpostfächer werden nicht an die frühere Gmail-Defaultadresse weitergeleitet.

## Technische Postfachanlage

Die Webanwendung schreibt verschlüsselte Aufträge in `mailbox_provisions`. Der root-eigene, nicht durch die Anwendung veränderbare Dienst `ctl-mailboxes.service` verarbeitet sie ungefähr alle 15 Sekunden über `ctl-mailboxes.timer`. Er validiert Domain und Adresse, erstellt Maildir und Dovecot-Passworthash und aktualisiert die Postfix-Maps. Die Webanwendung erhält weder sudo noch Root-Rechte. Der Status „Wird angelegt“ bleibt bis zum erfolgreichen Abschluss sichtbar.

```bash
sudo systemctl status ctl-mailboxes.timer
sudo journalctl -u ctl-mailboxes.service -n 60 --no-pager
```

Der Backend-E-Mail-Bereich listet alle TF und Verwaltungsmitarbeiter. Auswahl öffnet den Versand mit der jeweiligen Mitarbeiteradresse als Absender, An, CC, BCC und maximal fünf Anhängen (zusammen 7 MiB, kodierte Gesamtnachricht maximal 10 MiB). BCC-Adressen werden als SMTP-Empfänger übermittelt und nicht im gespeicherten Nachrichtenkopf abgelegt. Lesen/Schreiben im E-Mail-Modul erlaubt den Versand mit den dort verwalteten Mitarbeiterkonten.

## Oberflächen und Anmeldung

- `/`: zwei Kacheln für TF-Portal und Verwaltung.
- Administratoren sehen auf `/admin/start` außerdem phpMyAdmin und Webmailer.
- Nach Login erfolgt die Weiterleitung auf das Dashboard des jeweiligen Bereichs; ein erforderlicher Initialpasswortwechsel hat Vorrang.
- Portal und Verwaltung verwenden getrennte Cookie-Namen und pro Browser-Tab gespeicherte Tokens. Ein TF-Tab und ein Verwaltungs-/Administrator-Tab können gleichzeitig angemeldet bleiben. Neue Tabs mit `/tf` beziehungsweise `/admin` öffnen.
- Fahrzeugnummern beginnen bei neuen Fahrzeugen mit 91 und 80, beide Werte sind änderbar. Nach vollständiger Eingabe eines Nummernblocks springt der Fokus zum nächsten Feld.
- App-Grundwerte für Grund/Art zeigen kompakte Auswahllisten. Bearbeitungsaktionen erscheinen erst nach Auswahl.

## Prüfung

Automatisierte API-Tests prüfen Adressbildung, Kollisionen, verschlüsselte Anlageaufträge, Domainvalidierung und gleichzeitige TF-/Admin-Identitäten. SMTP-/IMAP-Komponenten werden in den Tests simuliert. Die zusätzliche echte Postfachanlage und der Versand aus neuen TF-Adressen müssen auf dem Server abschließend geprüft werden; eine bestätigte frühere Zustellung belegt nicht die neuen Funktionen.
