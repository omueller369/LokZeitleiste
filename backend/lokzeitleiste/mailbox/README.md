# Tf-E-Mail-Postfächer

Unter **3. Triebfahrzeugführer → 3.3 Email** einen Tf auswählen. Unterstützt werden Ordner, Betreff-/Absendersuche, Seiten mit 25 Nachrichten, Lesen ohne automatisches Gelesen-Markieren, expliziter Lesestatus, Antworten, Weiterleiten, Download/Upload von Anhängen, persönliche Entwürfe und SMTP-Versand. HTML-Nachrichten werden als Text angezeigt; externe Bilder und Skripte werden nicht geladen. Antworten/Weiterleiten übernehmen den Text. Vorhandene Anhänge bei Bedarf herunterladen und neu hinzufügen. Entwürfe speichern Empfänger, Betreff und Text, keine Anhänge. Microsoft OAuth2 und die Google-OAuth/API-Kontoanbindung sind integriert. Kalender und Kontaktverwaltung sind nicht Teil dieses Moduls.

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
| Googlemail/Gmail | imap.gmail.com:993 | smtp.gmail.com:587 STARTTLS | „Mit Google verbinden“ per OAuth2/API; alternativ App-Passwort |
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

## Googlemail per Button verbinden

Der Button **Mit Google verbinden** startet ohne vorherige Servereingaben eine Anmeldung bei Google. Google fragt das gewünschte Konto und die Zustimmung ab. Nach der Rückkehr werden die bestätigte Gmail-Adresse über die Gmail-API und die OAuth-Zugangstokens übernommen. Tokens sind verschlüsselt, werden bei Ablauf erneuert und nicht im Browser angezeigt. Anmeldung ist an Verwaltungsbenutzer, aktive Sitzung und den gewählten Tf gebunden; PKCE, ein nur einmal verwendbarer State und ein kurzlebiges HttpOnly-Cookie schützen die Rückkehr. Während der Anmeldung geänderte Postfacheinstellungen werden nicht überschrieben. Der Nachrichtenabruf/-versand nutzt anschließend IMAP/SMTP mit XOAUTH2, keine Google-Kontopasswörter. App-Passwort-Zugänge bleiben als manuelle Alternative möglich.

Einmalige Servereinrichtung:

1. Im eigenen Google-Cloud-Projekt die Gmail API aktivieren und OAuth-Zustimmungsbildschirm konfigurieren. Im Testbetrieb die vorgesehenen Google-Konten als Testnutzer aufnehmen.
2. Einen OAuth-Client vom Typ **Webanwendung** erstellen. Als autorisierte Redirect-URI exakt `https://DEIN-SERVER/api/v1/mailbox/google/callback` eintragen. Sie muss zu `PUBLIC_ORIGIN` passen. Für lokale Tests ist `http://localhost` bzw. `http://127.0.0.1` zulässig.
3. `MAILBOX_GOOGLE_CLIENT_ID` und `MAILBOX_GOOGLE_CLIENT_SECRET` privat in der Env-Datei hinterlegen; API-Container neu erstellen. Wie bei anderen Postfächern muss `MAILBOX_ENCRYPTION_KEY` eingerichtet sein.
4. Im E-Mail-Modul den Tf wählen und **Mit Google verbinden** klicken, das richtige Postfachkonto auswählen und die Zustimmung bestätigen.

Der für IMAP/SMTP benötigte Scope ist `https://mail.google.com/`. Für eine öffentliche produktive Google-App muss die dafür erforderliche Google-Verifizierung abgeschlossen sein. Ablehnung oder abgelaufene Anmeldung führt zurück ins Modul und lässt bestehende Kontoeinstellungen bestehen.

## Apple/iCloud vereinfachte Einrichtung

**iCloud verbinden** öffnet einen Dialog mit iCloud-Adresse und anwendungsspezifischem Apple-Passwort. Die bekannten Serverwerte werden automatisch gesetzt und über die Projekt-API gespeichert. Es sind keine manuellen IMAP-/SMTP-Eingaben nötig. Das App-Passwort muss vorher bei Apple erstellt werden; es wird beim Schließen aus dem Formular entfernt.

Dies ist keine passwortlose Apple-Mail-API-Anmeldung: Die öffentliche „Sign in with Apple“-API stellt Identität und ggf. die E-Mail-Adresse bereit, aber keine Freigabe für den iCloud-Postfachinhalt. Apple dokumentiert Apple-Account-Autorisierung für unterstützte Partner-Apps; für diese eigene Anwendung liegt keine öffentlich dokumentierte iCloud-Mail-OAuth-Schnittstelle vor. Deshalb verwendet die implementierte Anbindung den dokumentierten IMAP-/SMTP-Weg mit App-Passwort.

Quellen: [Google OAuth-Webanwendung](https://developers.google.com/identity/protocols/oauth2/web-server), [Gmail XOAUTH2](https://developers.google.com/workspace/gmail/imap/xoauth2-protocol), [Apple App-Passwörter](https://support.apple.com/en-us/102654), [Apple iCloud-Mailserver](https://support.apple.com/en-us/102525), [Apple Sign-in Scopes](https://developer.apple.com/documentation/signinwithapplejs/clientconfigi/scope).
