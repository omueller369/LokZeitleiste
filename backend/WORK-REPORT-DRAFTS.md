# Arbeitsbericht-Entwürfe auf mehreren Geräten

Nach dem Update werden mit **Arbeitszeit speichern** lokal gespeicherte Arbeitsberichte zusätzlich als private Entwürfe auf dem Server gesichert, sobald eine Verbindung besteht. Bestehende lokale Berichte werden beim nächsten Aufruf des Arbeitsberichts nachträglich gesichert. Dafür muss das ursprüngliche Gerät einmal verbunden sein.

Auf einem zweiten Gerät mit demselben TF anmelden und den Arbeitsbericht öffnen. Die Monatsliste enthält auch die auf dem Server gesicherten Entwürfe. Monat auswählen, Berichtszeile anklicken, weiterbearbeiten und erneut speichern. Der Entwurf bleibt bearbeitbar, auch wenn er bereits auf dem Server gesichert ist.

Der Abgleich erfolgt beim Öffnen, über **Aktualisieren**, beim erneuten Verbinden sowie im geöffneten Modul alle zehn Sekunden. Nicht gespeicherte Eingaben im Formular werden nicht automatisch als neue Entwurfsversion übertragen; zum Übernehmen der Bearbeitung weiterhin **Arbeitszeit speichern** verwenden.

Der Hinweis über der Monatsliste zeigt den Sicherungsstand. **Nur auf diesem Gerät** bedeutet, dass der Bericht noch nicht erfolgreich gesichert wurde. **Entwurf gesichert** bedeutet, dass die gespeicherte Fassung auf dem Server verfügbar ist. **Belege ausstehend** weist auf noch nicht vollständig übertragene Belege hin.

## Abschluss und Belege

Die Entwurfsablage ist vom endgültigen **Synchronisieren** getrennt. Ein Entwurf erzeugt keine abrechenbare Arbeitszeit, kein PDF und keinen E-Mail-Versand. Erst Synchronisieren schließt ihn ab; anschließend gelten die bisherigen Regeln für abgeschlossene Berichte.

PDF-, JPEG- und PNG-Quittungsbelege werden ebenfalls im Entwurf gesichert (maximal 20, je höchstens 10 MB). Beim Laden einer Entwurfszeile werden ihre Belege auf das aktuelle Gerät übernommen. Beim Abschluss übernimmt der Server die gesicherten Belege in den fertigen Bericht und startet den vorgesehenen Versand. Unvollständig gesicherte Belege verhindern den Abschluss, damit keine Belege verloren gehen.

## Gleichzeitige Bearbeitung

Jede Serverfassung hat eine Revisionsnummer. Eine veraltete Fassung kann eine neuere Fassung eines anderen Geräts nicht überschreiben. Die Zeile zeigt dann **Entwurfskonflikt**. Über **Serverstand laden** kann der TF nach Bestätigung die aktuelle Serverfassung übernehmen. Die bisherige lokale Fassung wird zusätzlich unter dem benutzerspezifischen Browser-Schlüssel `.draft-recovery.<client_id>` gesichert; sie wird nicht still verworfen. Ungespeicherte Eingaben des gerade geöffneten Berichts werden dabei ebenfalls gesichert.

Wird der Bericht auf einem anderen Gerät abgeschlossen, verschwindet er beim nächsten Abgleich aus den bearbeitbaren Entwürfen. Er kann anschließend über die Monatsliste als abgeschlossener Bericht geöffnet werden.

## Update und Technik

```bash
sudo bash install-ctlsoftware-test.sh --update
```

`init_db` legt `duty_report_drafts` und `duty_report_draft_files` automatisch an. Die bestehenden Tabellen müssen nicht geändert werden. Zugriff ausschließlich über den angemeldeten, freigeschalteten TF; Entwürfe und Belege anderer TF sind nicht abrufbar. Die Entwurfs-API verwendet Eigentümerfilter, Benutzerzeilensperren und Revisionsprüfungen. Die endgültige Übernahme von Bericht und Belegen erfolgt gemeinsam in einer Datenbanktransaktion. Alte Clients ohne Entwurfssicherung bleiben für Berichte ohne Serverentwurf kompatibel; ein bereits gesicherter Entwurf erfordert die passende Revision beim Abschluss.
