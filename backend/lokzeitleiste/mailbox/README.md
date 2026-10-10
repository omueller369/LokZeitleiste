# Tf-E-Mail-Postfächer

Unter **3. Triebfahrzeugführer → 3.3 Email** einen Tf auswählen. Unterstützt werden Ordner, Betreff-/Absendersuche, Seiten mit 25 Nachrichten, Lesen ohne automatisches Gelesen-Markieren, expliziter Lesestatus, Antworten, Weiterleiten, Download/Upload von Anhängen, persönliche Entwürfe und SMTP-Versand. HTML-Nachrichten werden als Text angezeigt; externe Bilder und Skripte werden nicht geladen. Antworten/Weiterleiten übernehmen den Text. Vorhandene Anhänge bei Bedarf herunterladen und neu hinzufügen. Entwürfe speichern Empfänger, Betreff und Text, keine Anhänge. Microsoft OAuth2 ist integriert. Kalender und Kontaktverwaltung sind nicht Teil dieses Moduls.

**Rechte:** Email 1 = lesen; 2 = verfassen, Entwürfe speichern, Lesestatus ändern und senden; 3 = zusätzlich Postfachzugang verwalten. Die Freigabe gilt für alle Tf-Postfächer im Backend. Ohne diese Freigabe bleiben Endpunkte gesperrt. IMAP verwendet TLS, SMTP SSL oder STARTTLS mit Zertifikatsprüfung. UIDVALIDITY verhindert das Öffnen falscher Nachrichten nach einer Ordner-Neuanlage. Es werden keine Nachrichten endgültig gelöscht.

## Server einrichten

Diese Werte in `backend/.env` bzw. der tatsächlich verwendeten Compose-Env-Datei ergänzen; Zugangsdaten niemals committen:

```dotenv
MAILBOX_IMAP_HOST=imap.example.com
MAILBOX_IMAP_PORT=993
MAILBOX_SMTP_HOST=smtp.example.com
MAILBOX_SMTP_PORT=465
MAILBOX_SMTP_SECURITY=ssl
MAILBOX_SENT_FOLDER=Sent
MAILBOX_ENCRYPTION_KEY=
```

Bei STARTTLS: `MAILBOX_SMTP_SECURITY=starttls` und `MAILBOX_SMTP_PORT=587`. Diese globalen Serverwerte sind nur der Fallback für bestehende Konten. Pro TF können Anbieter, IMAP-/SMTP-Server, Ports, TLS-Modus, eigener SMTP-Benutzername und Gesendet-Ordner im Modul gespeichert und geändert werden. Neue Konten benötigen eigene Serverangaben. Postfachversand ist unabhängig vom bisherigen Benachrichtigungs-SMTP (`SMTP_*`). Ohne gespeicherte Serverangaben bzw. globalen Host oder Schlüssel zeigt das Modul den Einrichtungsbedarf an und verbindet sich nicht automatisch.

Einen Fernet-Schlüssel erzeugen, etwa im bereits laufenden API-Container mit `docker compose exec api python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`. Den Wert als `MAILBOX_ENCRYPTION_KEY` in der privaten Env-Datei speichern und die API neu starten. **Schlüssel dauerhaft zusammen mit der Datenbanksicherung sicher aufbewahren.** Ein anderer Schlüssel kann bestehende Zugangsdaten nicht entschlüsseln; dann Zugangsdaten neu hinterlegen. Postfachpasswörter werden in `mailbox_accounts` verschlüsselt gespeichert und niemals über die API zurückgegeben. Entwürfe liegen je Verwaltungsbenutzer und Tf in `mail_drafts`.

Senden erfolgt erst über die Schaltfläche und die Empfängerbestätigung. Bei Versandfehlern gibt es keine automatische Wiederholung, um Duplikate zu vermeiden. Ein Versand kann bei Verbindungsabbruch bereits teilweise erfolgt sein; vor erneutem Senden das externe Postfach prüfen. Nach erfolgreichem SMTP-Versand wird eine Kopie im pro Konto gewählten Gesendet-Ordner (Fallback `MAILBOX_SENT_FOLDER`) abgelegt. Scheitert nur diese Kopie, meldet die API weiterhin `sent: true` mit Hinweis; nicht erneut senden.

Die Integration ist mit simulierten IMAP-/SMTP-Serverantworten getestet. Für echte Postfächer müssen Verbindung, Provider-Ordnernamen und ggf. App-Passwörter vor Ort geprüft werden. Nachrichten sind auf 10 MiB begrenzt, Upload auf höchstens fünf Anhänge; der Webclient beschränkt Anhänge auf insgesamt 7 MiB vor MIME-Kodierung.

## Anbieter und individuelle Kontoeinstellungen

Im Modul den Tf wählen, „Postfach einrichten“ öffnen und den Anbieter auswählen. Eine Vorlage füllt die Serverfelder; anschließend E-Mail-Adresse, IMAP-Benutzername und App-/Postfachpasswort hinterlegen. Für Apple kann der IMAP-Benutzername der lokale Adressteil sein; als SMTP-Benutzername die vollständige Adresse eintragen. Ein leerer SMTP-Benutzername übernimmt den IMAP-Benutzernamen. Speichern aktiviert die individuellen Angaben; spätere Änderungen über dasselbe Formular. Bei geänderten Servern oder Kontodaten muss das Passwort erneut eingegeben werden. Microsoft-Token werden bei Änderungen verworfen und müssen neu verbunden werden. Bereits versendete Nachrichten werden nicht erneut gesendet.

| Anbieter | IMAP (SSL/TLS) | SMTP | Anmeldung |
|---|---|---|---|
| Googlemail/Gmail | imap.gmail.com:993 | smtp.gmail.com:587 STARTTLS | App-Passwort bei Zwei-Faktor-Anmeldung; Verfügbarkeit hängt vom Konto ab |
| Apple/iCloud | imap.mail.me.com:993 | smtp.mail.me.com:587 STARTTLS | Anwendungsspezifisches Passwort |
| WEB.DE | imap.web.de:993 | smtp.web.de:587 STARTTLS | IMAP aktivieren; ggf. App-Passwort |
| Yahoo | imap.mail.yahoo.com:993 | smtp.mail.yahoo.com:465 SSL/TLS | App-Passwort |
| Microsoft/Outlook | outlook.office365.com:993 | smtp-mail.outlook.com:587 STARTTLS | OAuth2 |
| Manuell | frei einstellbar | frei einstellbar | Postfachpasswort, ausschließlich SSL/TLS oder STARTTLS |

Für Microsoft 365 kann der SMTP-Server auf `smtp.office365.com` geändert werden. Microsoft-Tokens werden ausschließlich an diese Microsoft-Server übermittelt. Mandantenrichtlinien können IMAP, SMTP AUTH oder Gerätecode-Anmeldung sperren. Gesendet-Ordnernamen sind sprachabhängig; die Vorlagen bei Bedarf anpassen. Gmail kann selbst bereits eine Gesendet-Kopie erzeugen; die zusätzliche IMAP-Kopie ist dann gegebenenfalls doppelt vorhanden.

### Microsoft-App einmalig registrieren

1. In Microsoft Entra eine eigene App registrieren. Für Outlook.com und Microsoft 365 die unterstützten Kontotypen passend auswählen (Organisationskonten und persönliche Microsoft-Konten).
2. Unter Authentifizierung den öffentlichen Clientfluss aktivieren („Allow public client flows“). Das Modul verwendet den Device-Code-Flow; kein Client-Secret und keine Redirect-URL erforderlich.
3. Delegierte Exchange-Online-Berechtigungen `IMAP.AccessAsUser.All` und `SMTP.Send` für die App vorsehen; ggf. Administratorzustimmung im Mandanten erteilen.
4. Die Anwendungs-/Client-ID in der privaten Env-Datei als `MAILBOX_MICROSOFT_CLIENT_ID` hinterlegen. `MAILBOX_MICROSOFT_TENANT=common` für beide Kontotypen, alternativ die eigene Tenant-ID/`organizations`/`consumers`. API-Container neu erstellen.
5. Im Modul Microsoft auswählen, die Daten speichern, „Microsoft-Anmeldung starten“ klicken. Den angezeigten Code unter `https://microsoft.com/devicelogin` eingeben, das vorgesehene Postfachkonto anmelden und den Zugriff bestätigen. Anschließend „Microsoft-Verbindung abschließen“ klicken. Bei noch ausstehender Anmeldung nach einigen Sekunden erneut prüfen.

Device-Code und Tokens werden mit `MAILBOX_ENCRYPTION_KEY` verschlüsselt. Die Anmeldung ist an den Verwaltungsbenutzer und den Tf gebunden und läuft nach kurzer Zeit ab. Der Browser erhält nur den Eingabecode, keine Zugriffs-/Refresh-Tokens. Abgelaufene Zugriffstokens werden mit dem Refresh-Token erneuert. Für die Kontoeinrichtung und Microsoft-Verbindung ist Email-Administration (Stufe 3) erforderlich.

Offizielle Quellen für die Vorlagen (geprüft 10.10.2026): [Google](https://support.google.com/mail/answer/7126229), [Google-Server](https://developers.google.com/workspace/gmail/imap/imap-smtp), [Apple](https://support.apple.com/en-us/102525), [WEB.DE](https://hilfe.web.de/pop-imap/imap/imap-serverdaten.html), [Yahoo](https://de.hilfe.yahoo.com/kb/SLN4075.html), [Microsoft-Server](https://support.microsoft.com/de-de/outlook/pop-imap-and-smtp-settings-for-outlook-com), [Microsoft OAuth2](https://learn.microsoft.com/en-us/exchange/client-developer/legacy-protocols/how-to-authenticate-an-imap-pop-smtp-application-by-using-oauth), [Gerätecode](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-device-code).
