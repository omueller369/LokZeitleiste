# Tf-E-Mail-Postfächer

Unter **3. Triebfahrzeugführer → 3.3 Email** einen Tf auswählen. Unterstützt werden Ordner, Betreff-/Absendersuche, Seiten mit 25 Nachrichten, Lesen ohne automatisches Gelesen-Markieren, expliziter Lesestatus, Antworten, Weiterleiten, Download/Upload von Anhängen, persönliche Entwürfe und SMTP-Versand. HTML-Nachrichten werden als Text angezeigt; externe Bilder und Skripte werden nicht geladen. Antworten/Weiterleiten übernehmen den Text. Vorhandene Anhänge bei Bedarf herunterladen und neu hinzufügen. Entwürfe speichern Empfänger, Betreff und Text, keine Anhänge. OAuth-Anmeldung, Kalender und Kontaktverwaltung sind nicht Teil dieses Moduls.

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

Bei STARTTLS: `MAILBOX_SMTP_SECURITY=starttls` und `MAILBOX_SMTP_PORT=587`. Die Server sind global; jeder Tf erhält eigene E-Mail-Adresse, Postfach-Benutzername und Passwort im Modul. Postfachversand ist unabhängig vom bisherigen Benachrichtigungs-SMTP (`SMTP_*`). Ohne Host/Schlüssel zeigt das Modul den Einrichtungsbedarf an und verbindet sich nicht automatisch.

Einen Fernet-Schlüssel erzeugen, etwa im bereits laufenden API-Container mit `docker compose exec api python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`. Den Wert als `MAILBOX_ENCRYPTION_KEY` in der privaten Env-Datei speichern und die API neu starten. **Schlüssel dauerhaft zusammen mit der Datenbanksicherung sicher aufbewahren.** Ein anderer Schlüssel kann bestehende Zugangsdaten nicht entschlüsseln; dann Zugangsdaten neu hinterlegen. Postfachpasswörter werden in `mailbox_accounts` verschlüsselt gespeichert und niemals über die API zurückgegeben. Entwürfe liegen je Verwaltungsbenutzer und Tf in `mail_drafts`.

Senden erfolgt erst über die Schaltfläche und die Empfängerbestätigung. Bei Versandfehlern gibt es keine automatische Wiederholung, um Duplikate zu vermeiden. Ein Versand kann bei Verbindungsabbruch bereits teilweise erfolgt sein; vor erneutem Senden das externe Postfach prüfen. Nach erfolgreichem SMTP-Versand wird eine Kopie in `MAILBOX_SENT_FOLDER` abgelegt. Scheitert nur diese Kopie, meldet die API weiterhin `sent: true` mit Hinweis; nicht erneut senden.

Die Integration ist mit simulierten IMAP-/SMTP-Serverantworten getestet. Für echte Postfächer müssen Verbindung, Provider-Ordnernamen und ggf. App-Passwörter vor Ort geprüft werden. Nachrichten sind auf 10 MiB begrenzt, Upload auf höchstens fünf Anhänge; der Webclient beschränkt Anhänge auf insgesamt 7 MiB vor MIME-Kodierung.
