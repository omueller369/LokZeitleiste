# Android 0.11 – aktuelles TF-Portal

Die App öffnet nach der nativen Anmeldung das vollständige TF-Portal. Die gemeinsamen HTML-/CSS-/JavaScript-Dateien werden beim Android-Build aus `backend/lokzeitleiste/static` in die APK übernommen. Geschäftsregeln, Tabellen, Eingaben und Berechtigungen entsprechen damit dem Portalstand dieses Builds. Neue Portalversionen erfordern einen neuen APK-Build. Der Server muss mindestens zum selben Projektstand aktualisiert sein.

Enthalten sind Arbeitsberichte mit Dienstarten, Pausen, Ausbleibe, Gastfahrten und optionalen Selbstzahlerbelegen; Zugfahrten und Ereignisse mit dynamischen Grundwerten; Monatslisten und Synchronisation; GPS mit Standzeiten, ZMS-Vorschlägen und Gründen; Arbeitsplan; Dokumentenverwaltung mit Upload/Download; Bahnhofsverzeichnis einschließlich Kontaktdaten, Plänen, Teilen und Zwischenablage; Konto, Passwortwechsel und die fünf vorhandenen Sprachen. Lokübergabebuch und Leuna-Übergabeprotokoll behalten wie im Browser ihren Platzhalterstatus.

## Vorhandene Daten

**Bisherige Erfassungen** öffnet die vorherige native Monats-/LokZeit-Erfassung. Ihre Daten werden nicht gelöscht oder automatisch als neue Arbeitsberichte doppelt übertragen. **zurück TF-Portal** führt zurück. Browserentwürfe auf einem anderen Gerät werden nicht automatisch übernommen; synchronisierte Berichte erscheinen über den Server.

## Offline und Synchronisation

Nach einer erfolgreichen Online-Anmeldung kann das gebündelte Portal ohne Netz erneut geöffnet werden. Arbeitsberichte und Quittungen verwenden wie im Browser LocalStorage bzw. IndexedDB. Zuletzt abgerufene Pläne und Suchergebnisse sind in einem begrenzten, kontogetrennten Zwischenspeicher verfügbar; Berichtslisten nutzen zusätzlich den vorhandenen Monatscache. Nicht die gesamte Serverhistorie ist offline verfügbar. Neue Bahnhofssuchen und serverseitige Änderungen benötigen eine Verbindung. Lokale Arbeitsberichte über **Synchronisieren** übertragen; es gibt keinen unbeaufsichtigten automatischen Versand aller Dokumente. Uploadfehler löschen keine lokalen Belege. HTTP 401/403 wird nicht durch einen Offline-Cache übergangen. Eine Offline-Abmeldung entfernt die Sitzung auf dem Gerät; eine serverseitige Sperrung kann offline erst beim nächsten Kontakt erkannt werden.

## GPS unter Android

1. Arbeitsbericht öffnen, Zugfahrt hinzufügen und Zugnummer eintragen.
2. **Zugfahrt per GPS aufzeichnen** antippen, präzisen Standort erlauben und Android-GPS einschalten.
3. Die dauerhafte Systembenachrichtigung zeigt die laufende Aufzeichnung. Der Standortdienst läuft unabhängig vom WebView, auch bei Bildschirmsperre.
4. In derselben Zugfahrt **GPS-Aufzeichnung beenden** wählen und bei Netzverbindung synchronisieren. Standzeiten/ZMS/Gründe werden mit der vorhandenen Serverauswertung bearbeitet.
5. **GPX herunterladen** öffnet die Android-Dateiauswahl.

Standortpunkte werden zusätzlich im privaten App-Verzeichnis protokolliert und beim Wiederöffnen der Zugfahrt übernommen. Prozessabbruch, „Stopp erzwingen“, entzogene Berechtigungen, Stromsparregeln oder fehlender Satellitenempfang können die Aufzeichnung unterbrechen. Nach einem solchen Abbruch die betroffene Zugfahrt öffnen und ausdrücklich fortsetzen oder beenden. Es wird kein lückenloser Verlauf erfunden. Kein automatischer Start bei Geräte-Neustart. Keine Hintergrundstandortberechtigung und kein kostenpflichtiger Kartenanbieter erforderlich; die bestehende kostenlose OSM/ZMS-Abfrage läuft über den Server.

## Dateien und Anmeldung

Uploads verwenden die Android-Dokumentenauswahl; die vorhandenen 10-MB-Grenzen werden weiter geprüft. Downloads werden nur vom konfigurierten Server mit der eigenen Sitzung abgerufen und am gewählten Ort gespeichert. GPX-Dateien werden in kleinen Blöcken an die native Dateiauswahl übergeben. Fremde Webseiten öffnen außerhalb der Portal-WebView. TLS-Fehler werden nicht übergangen. Die native Bridge ist auf den exakten Serverursprung und das Hauptfenster beschränkt.

## APK bauen und installieren

Voraussetzungen: JDK 17, Android SDK Plattform 35/Build Tools 35.0.0 und Gradle 8.9 (oder Android Studio mit passender Gradle-Konfiguration). Im Projektverzeichnis:

```bash
gradle :app:testDebugUnitTest :app:assembleDebug :app:lintDebug \
  -PlokzeitleisteApiBaseUrl=https://ctl-software.io-goerlitz.eu
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Bei einer APK mit anderer bisheriger Signatur kann Android kein direktes Update installieren. Vor einer Deinstallation unübertragene lokale Daten sichern/synchronisieren. Keine Deinstallation ohne Datensicherung empfehlen.

Die GitHub Action **Android TF Portal APK** führt Tests, Build und Lint aus und stellt bei Erfolg das Artefakt **LokZeitleiste-TF-Portal-debug** bereit. Die Debug-APK dient Tests/Demonstrationen. Für eine spätere Veröffentlichung separat mit eigenem dauerhaftem Signierschlüssel signieren.

Der externe Server benötigt für App/GPS eine gültige HTTPS-Konfiguration. Falls er weiterhin nur HTTP anbietet, zuerst die vorhandene Routine `sudo bash setup-https.sh` gemäß Serveranleitung ausführen; keine Anmeldedaten über öffentliches HTTP verwenden. Die Domain muss vom Android-Gerät erreichbar sein. Zum lokalen Emulator-Test:

```bash
gradle :app:assembleDebug -PlokzeitleisteApiBaseUrl=http://10.0.2.2:8080
```

Das HTTP-Ausnahmeziel gilt nur für den Debug-Emulator. Release-Builds benötigen HTTPS.

## Prüfstatus

Die gemeinsame Portal-/GPS-Logik und Android-Adapter sind durch automatisierte Simulationen und Backendtests abgesichert. Die GitHub Action ergänzt Android-Kompilierung, Unit-Tests und Lint. Reale GPS-Qualität, Bildschirmsperre, Dateiauswahl und Verhalten bei Energiesparregeln müssen auf einem echten Android-Gerät geprüft werden.
