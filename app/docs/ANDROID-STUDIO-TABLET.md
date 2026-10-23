# LokZeitleiste: Android Studio, Tablet-Test und Updates aus GitHub

Diese Anleitung beschreibt das vorhandene Projekt **LokZeitleiste** auf einem Mac. Es wird **kein leeres neues Android-Projekt** erstellt: Das GitHub-Projekt wird geklont und in Android Studio geöffnet.

Repository: https://github.com/omueller369/LokZeitleiste  
Arbeitsbranch: `setup/debian-testumgebung`  
Android-Paket: `de.lokzeitleiste.app`  
Server: `https://ctl-software.io-goerlitz.eu`  
Android-Mindestversion: Android 8.0 / API 26.

## 1. Was „automatisches Update“ hier bedeutet

Die App prüft beim Öffnen/Fortsetzen höchstens alle sechs Stunden auf neue freigegebene Testversionen aus diesem GitHub-Repository. **Update** in der App startet die Prüfung sofort. Eine neuere APK wird heruntergeladen und auf Prüfsumme, Paketname, Versionsnummer und denselben Signierschlüssel geprüft. Danach erscheint **Update installieren**.

Auf einem gewöhnlichen Tablet verlangt Android eine Installationsbestätigung. Die App kann diese nicht einfach umgehen. **Automatische Erkennung und Download: ja. Stille Installation ohne jede Bestätigung: nicht Bestandteil dieser normalen Testinstallation.** Dafür wäre eine gesonderte Einrichtung als verwaltetes Unternehmensgerät erforderlich. Updates werden nicht während einer laufenden GPS-Aufzeichnung installiert. Ist die App geschlossen, prüft sie beim nächsten Öffnen; es gibt keinen permanenten Update-Hintergrunddienst.

Damit Updates funktionieren, müssen Erstinstallation und spätere APKs mit **demselben privaten Signierschlüssel** gebaut werden. Ein anderer Schlüssel verhindert ein normales Update. Deshalb zuerst Abschnitt 5 erledigen, dann die dauerhafte Testinstallation vornehmen.

## 2. Voraussetzungen auf dem Mac

1. Android Studio von https://developer.android.com/studio installieren und einmal starten.
2. Im Einrichtungsassistenten Android SDK installieren lassen.
3. Git im Terminal prüfen:

   ```bash
   git --version
   ```

   Falls macOS die Installation der Command Line Tools anbietet, diese abschließen. Alternativ:

   ```bash
   xcode-select --install
   ```

4. In Android Studio **Tools → SDK Manager** öffnen. Auf dem Begrüßungsbildschirm: **More Actions → SDK Manager**.
5. Unter **SDK Platforms** die Plattform **Android API 35** installieren. Zusätzliche neuere Plattformen dürfen installiert bleiben.
6. Unter **SDK Tools** aktivieren/installieren:
   - Android SDK Platform-Tools
   - Android SDK Command-line Tools (latest)
   - Android SDK Build-Tools **35.0.0**; ggf. **Show Package Details** einschalten
   - Android Emulator, wenn zusätzlich ein Emulator verwendet werden soll.
7. Den SDK-Pfad oben im SDK Manager notieren. Auf dem Mac ist er normalerweise:

   ```text
   /Users/DEIN-MAC-BENUTZER/Library/Android/sdk
   ```

8. Für dieses Projekt **JDK 17** verwenden. In Android Studio unter **Android Studio → Settings → Build, Execution, Deployment → Build Tools → Gradle → Gradle JDK** **Download JDK** wählen und Version **17** installieren/auswählen. Ein bereits installiertes JDK 17 kann stattdessen gewählt werden.

Das Projekt verwendet Gradle 8.9, Android Gradle Plugin 8.7.3, Kotlin 2.0.21 und API 35. Nicht während der ersten Einrichtung beliebige vorgeschlagene Versions-Upgrades übernehmen; zunächst diese Kombination erfolgreich bauen.

## 3. Repository klonen

Terminal auf dem Mac öffnen:

```bash
mkdir -p "$HOME/Developer"
cd "$HOME/Developer"
git clone --branch setup/debian-testumgebung https://github.com/omueller369/LokZeitleiste.git
cd LokZeitleiste
git branch --show-current
```

Erwartete Ausgabe des letzten Befehls:

```text
setup/debian-testumgebung
```

Wenn das Projekt bereits geklont ist, keinen zweiten Ordner mit demselben Namen anlegen. Stattdessen im vorhandenen Checkout:

```bash
cd "$HOME/Developer/LokZeitleiste"
git switch setup/debian-testumgebung
git pull --ff-only origin setup/debian-testumgebung
```

Bei einem Hinweis auf lokale Änderungen diese zuerst prüfen und sichern. Keine ungespeicherten Änderungen mit einem erzwungenen Reset löschen.

## 4. Gradle 8.9 und Projekt in Android Studio öffnen

Das Repository enthielt ursprünglich keinen Gradle-Wrapper. Für eine reproduzierbare lokale Einrichtung kann dieser einmalig mit Gradle 8.9 erzeugt werden.

### 4.1 Terminal vorbereiten

Ein JDK 17 muss installiert sein. Prüfen:

```bash
/usr/libexec/java_home -V
export JAVA_HOME=$(/usr/libexec/java_home -v 17)
java -version
export ANDROID_HOME="$HOME/Library/Android/sdk"
export PATH="$ANDROID_HOME/platform-tools:$PATH"
```

Wenn Android Studio das JDK in einem anderen Verzeichnis heruntergeladen hat und `java_home -v 17` es nicht findet: Im Gradle-JDK-Auswahldialog den angezeigten JDK-Pfad kopieren und stattdessen setzen:

```bash
export JAVA_HOME="/VOLLSTAENDIGER/PFAD/ZUM/JDK-17/Contents/Home"
```

Den Beispielpfad durch den echten Pfad ersetzen. Bei einem abweichenden SDK-Verzeichnis `ANDROID_HOME` ebenfalls anpassen.

### 4.2 Gradle herunterladen und Wrapper erzeugen

```bash
mkdir -p "$HOME/Developer/tools"
curl -fL https://services.gradle.org/distributions/gradle-8.9-bin.zip \
  -o "$HOME/Downloads/gradle-8.9-bin.zip"
unzip -q "$HOME/Downloads/gradle-8.9-bin.zip" -d "$HOME/Developer/tools"
export PATH="$HOME/Developer/tools/gradle-8.9/bin:$PATH"
cd "$HOME/Developer/LokZeitleiste"
gradle --version
gradle wrapper --gradle-version 8.9
chmod +x gradlew
```

Bei bereits vorhandenem `tools/gradle-8.9` das ZIP nicht erneut darüber entpacken. Danach werden die folgenden Befehle mit `./gradlew` ausgeführt.

### 4.3 In Android Studio öffnen

1. **Open** auf dem Begrüßungsbildschirm oder **File → Open** wählen.
2. Den **gesamten Ordner `LokZeitleiste`** wählen, in dem `settings.gradle.kts`, `build.gradle.kts` und `app/` liegen. Nicht nur `app/` öffnen.
3. Das eigene Projekt als vertrauenswürdig bestätigen.
4. Warten, bis Gradle Sync und das Herunterladen der Abhängigkeiten abgeschlossen sind.
5. Unter den Gradle-Einstellungen **Gradle Wrapper** und **JDK 17** verwenden.
6. Die Run-Konfiguration oben auf **app** einstellen. Falls sie fehlt: **Run → Edit Configurations → + → Android App**, Modul **LokZeitleiste.app** wählen.

## 5. Einmalig einen dauerhaften Test-Signierschlüssel einrichten

### 5.1 Bereits vorhandene Installation beachten

Wenn schon eine LokZeitleiste-App mit lokalen, noch nicht übertragenen Daten auf dem Tablet installiert ist: **Zuerst synchronisieren bzw. Daten sichern. Nicht einfach deinstallieren.** Möglichst den ursprünglichen Signierschlüssel weiterverwenden.

Wenn bisher von diesem Mac mit dem normalen Android-Debug-Schlüssel installiert wurde, liegt dieser häufig unter `~/.android/debug.keystore` (Alias `androiddebugkey`). Er kann für denselben Testkanal weiterverwendet werden. Verwende dann dessen tatsächlichen Pfad, Alias und Passwörter in den folgenden Einstellungen. Wenn der bisherige Schlüssel unbekannt ist, ist ein datenbewahrendes Update nicht durch einen neuen Schlüssel ersetzbar.

Für eine neue dauerhafte Testinstallation:

### 5.2 Neuen Testschlüssel erzeugen

```bash
mkdir -p "$HOME/.lokzeitleiste-signing"
chmod 700 "$HOME/.lokzeitleiste-signing"
keytool -genkeypair -v \
  -keystore "$HOME/.lokzeitleiste-signing/tf-test.jks" \
  -storetype JKS \
  -alias ctl-test \
  -keyalg RSA \
  -keysize 3072 \
  -validity 10000
chmod 600 "$HOME/.lokzeitleiste-signing/tf-test.jks"
```

`keytool` fragt das Keystore-Passwort und Zertifikatsangaben ab. Das Passwort sicher aufbewahren. Bei der abschließenden Frage zum Schlüsselpasswort kann mit Eingabetaste dasselbe Passwort verwendet werden. Den Schlüssel und das Passwort außerhalb des Rechners sicher sichern: Ohne diesen Schlüssel sind spätere Updates für diese Installation nicht mehr möglich.

### 5.3 Lokalen Build auf diesen Schlüssel einstellen

Die private Gradle-Konfiguration im Benutzerverzeichnis öffnen, **nicht im Repository**:

```bash
mkdir -p "$HOME/.gradle"
touch "$HOME/.gradle/gradle.properties"
chmod 600 "$HOME/.gradle/gradle.properties"
open -e "$HOME/.gradle/gradle.properties"
```

Diese vier Zeilen ergänzen; Pfad, Benutzername und Passwort durch die tatsächlichen Werte ersetzen:

```properties
lokzeitleisteSigningStoreFile=/Users/DEIN-MAC-BENUTZER/.lokzeitleiste-signing/tf-test.jks
lokzeitleisteSigningStorePassword=DEIN_EIGENES_KEYSTORE_PASSWORT
lokzeitleisteSigningKeyAlias=ctl-test
lokzeitleisteSigningKeyPassword=DEIN_EIGENES_SCHLUESSEL_PASSWORT
```

Falls beide Passwörter gleich sind, denselben Wert in beide Passwortzeilen schreiben. Java-Properties behandelt Backslashes als Escapezeichen; ein tatsächlicher Backslash im Passwort muss als `\\` geschrieben werden. Datei speichern, schließen und in Android Studio erneut **Sync Project with Gradle Files** ausführen.

Keystore und Passwörter nicht committen. Die Konfiguration unter `~/.gradle` wird nicht mit dem Projekt hochgeladen. Vor dem ersten Tablet-Installieren den verwendeten Schlüssel prüfen:

```bash
cd "$HOME/Developer/LokZeitleiste"
./gradlew :app:signingReport
```

Für die Variante **debug** müssen der konfigurierte Keystore und der Alias erscheinen. Den angezeigten Zertifikats-Fingerabdruck notieren.

## 6. Server und Serveradresse vorbereiten

Das Tablet verbindet sich direkt mit dem Ubuntu-Server; der Mac muss später nicht eingeschaltet bleiben.

Auf dem Ubuntu-Server den passenden Projektstand einspielen:

```bash
cd /opt/LokZeitleiste
git pull --ff-only origin setup/debian-testumgebung
sudo bash setup-demo.sh
```

Falls der Server noch ausschließlich HTTP anbietet, die vorhandene kostenlose HTTPS-Routine ausführen:

```bash
sudo bash setup-https.sh --email DEINE_ZERTIFIKATS_EMAILADRESSE
```

Den Platzhalter durch eine erreichbare E-Mail-Adresse ersetzen. Ein gültiges Zertifikat, korrekte DNS-Auflösung und erreichbare Ports 80/443 sind erforderlich. Am Tablet im Browser prüfen:

```text
https://ctl-software.io-goerlitz.eu/tf
```

Die Seite muss ohne Zertifikatswarnung erreichbar sein. Nicht „trotzdem fortfahren“ als Lösung verwenden. Ist die Domain weiterhin nur über HTTP erreichbar, zuerst die Serverkonfiguration korrigieren. Öffentliche HTTP-Anmeldung ist im Android-Build nicht freigeschaltet.

Standardmäßig verwendet die App bereits diese HTTPS-Adresse. Für eine andere HTTPS-Testdomain kann lokal in `~/.gradle/gradle.properties` ergänzt werden:

```properties
lokzeitleisteApiBaseUrl=https://DEINE-TESTDOMAIN
```

Keinen abschließenden Pfad wie `/tf` oder `/api/v1` anhängen. Bei einer abweichenden Domain muss auch die Adresse im GitHub-Workflow angepasst werden, sonst würden spätere Update-APKs wieder die dort konfigurierte Serveradresse verwenden.

## 7. Projekt bauen und automatisierte Tests ausführen

Im Android-Studio-Terminal oder im Mac-Terminal:

```bash
cd "$HOME/Developer/LokZeitleiste"
./gradlew :app:testDebugUnitTest :app:assembleDebug :app:lintDebug
```

Der erste Build kann mehrere Minuten dauern, weil Abhängigkeiten geladen werden. Erfolgreich ist er erst bei **BUILD SUCCESSFUL**.

Die APK liegt anschließend hier:

```text
app/build/outputs/apk/debug/app-debug.apk
```

Die aktuelle Version ohne eigene Versionsparameter trägt lokal `0.11` / Versionscode `11`. Der GitHub-Testkanal verwendet steigende Codes ab `100001`. Nach Installation einer GitHub-Version kann eine lokale Version `11` deshalb kein normales Update mehr sein. Für spätere lokale Tests einen entsprechend höheren Code mitgeben, zum Beispiel:

```bash
./gradlew :app:assembleDebug -PlokzeitleisteVersionCode=100123
```

Den Beispielcode **nicht blind verwenden**: Er muss zum vorhandenen Tabletstand passen. Unnötig weit voraus springende lokale Codes können reguläre GitHub-Updates lange überholen. Für den täglichen Tablet-Test deshalb bevorzugt die APK aus dem GitHub-Testkanal verwenden.

## 8. Zunächst im Emulator testen (optional)

1. Android Studio: **Tools → Device Manager → + → Create Virtual Device**.
2. Ein Tablet-Profil auswählen.
3. Auf einem Mac mit Apple Silicon ein **arm64-v8a**-Systemimage wählen; auf Intel-Macs ein passendes **x86_64**-Image.
4. API 35 als Systemimage herunterladen, Gerät fertigstellen und starten.
5. Oben in Android Studio dieses virtuelle Gerät auswählen und **Run ▶** drücken.
6. Mit einer vorhandenen sechsstelligen TF-Nummer und dem zugehörigen Passwort anmelden. Einen geforderten Initialpasswortwechsel durchführen.

Bei Verbindung zum externen Server bleibt die HTTPS-Standardadresse bestehen. Nur wenn das Backend tatsächlich lokal auf dem Mac auf Port 8080 läuft, kann ein Debug-Build mit `http://10.0.2.2:8080` erstellt werden. `10.0.2.2` bedeutet im Android-Emulator den Host-Mac; auf einem echten Tablet funktioniert diese Adresse **nicht** als Serveradresse.

```bash
./gradlew :app:assembleDebug -PlokzeitleisteApiBaseUrl=http://10.0.2.2:8080
```

Für die dauerhafte Tabletinstallation wieder den HTTPS-Build verwenden.

## 9. Android-Tablet per USB verbinden

1. Tablet laden und mit einem **Datenkabel** an den Mac anschließen. Ein reines Ladekabel reicht nicht.
2. Tablet: **Einstellungen → Über das Tablet → Softwareinformationen → Buildnummer**. Die Buildnummer siebenmal antippen; ggf. Geräte-PIN eingeben. Die genauen Untermenünamen hängen vom Hersteller ab.
3. Unter **Einstellungen → Entwickleroptionen** **USB-Debugging** aktivieren.
4. Tablet entsperrt lassen und die Nachfrage **USB-Debugging zulassen?** für den eigenen Mac bestätigen.
5. Im Terminal prüfen:

   ```bash
   export ANDROID_HOME="$HOME/Library/Android/sdk"
   export PATH="$ANDROID_HOME/platform-tools:$PATH"
   adb devices
   ```

6. Erwartet wird eine Zeile mit der Seriennummer und **device**. Bei **unauthorized** auf dem Tablet die Nachfrage bestätigen. Bei einer leeren Liste Kabel, USB-Anschluss und Debugging-Einstellung prüfen.

## 10. Testversion auf dem Tablet installieren

### Weg A: Direkt aus Android Studio

1. Das Tablet oben als Zielgerät auswählen.
2. Konfiguration **app** wählen.
3. **Run ▶** drücken.
4. Android Studio baut und installiert die debug-Variante mit dem in Abschnitt 5 konfigurierten Schlüssel.
5. Auf dem Tablet öffnet sich LokZeitleiste.

### Weg B: Aus dem Terminal

```bash
cd "$HOME/Developer/LokZeitleiste"
./gradlew :app:assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb shell am start -n de.lokzeitleiste.app/.MainActivity
```

`-r` bedeutet Update unter Beibehaltung der App-Daten, sofern Paketname, Signatur und Version passen. Bei mehreren angeschlossenen Geräten `adb -s SERIENNUMMER install -r ...` verwenden.

### Weg C: APK ohne USB installieren

Die später in Abschnitt 12 veröffentlichte **signierte GitHub-Test-APK** im Tablet-Browser herunterladen, im Downloadordner antippen und die Android-Installationsabfrage bestätigen. Für den Browser bzw. Dateimanager ggf. einmal **Unbekannte Apps installieren → Aus dieser Quelle zulassen** aktivieren. Nur die APK aus dem eigenen Repository verwenden.

## 11. Funktionsprüfung auf dem Tablet

Am besten einen eigens vorgesehenen Test-TF verwenden, damit keine echten Dienstberichte verändert werden.

1. **Anmeldung:** TF-Nummer und Passwort; bei Initialkonto sofortiger Passwortwechsel.
2. **Portal:** Arbeitsbericht, Arbeitsplan, Dokumentenverwaltung und Bahnhofsverzeichnis öffnen. Im Lokübergabebuch Fahrzeugliste, Auswahl, Status und Einschränkungen prüfen. Übergabeprotokolle mit Anhängen erfassen, Tabelle und Details auch mit einem anderen TF-Konto prüfen. PZB, Störungen und das Leuna-Modul sind noch Platzhalter.
3. **Arbeitsbericht:** neuen Bericht, Beginn/Ende einschließlich Folgetag, Dienstart und berechnete Zeiten prüfen. Blöcke mit `−`/`+` ein-/ausklappen.
4. **Gastfahrt:** Von/Nach über DS100 oder Ortsname suchen, speichern. Ohne Selbstzahler keinen Beleg erzwingen; mit **Sz** einen kleinen Testbeleg auswählen.
5. **Zugfahrt:** Zugnummer, Bahnhöfe und Zeiten; Ereignis eintragen, Tabellenzeile erneut bearbeiten; **CTL Pause** prüfen.
6. **Offline:** zunächst Bericht/Plan online öffnen. Dann Flugmodus einschalten. Lokalen Bericht ergänzen und speichern. App schließen/neu öffnen und kontrollieren, dass der Entwurf erhalten ist. Danach Netz einschalten und **Synchronisieren** drücken. Im Webportal mit demselben TF prüfen, dass kein doppelter Bericht entstand.
7. **Dateien:** ein Testdokument unter 10 MB hochladen, herunterladen und über **Ansehen** öffnen. Uploadgrenze und Löschrechte prüfen.
8. **Bahnhöfe:** eigenen Eintrag mit Kontakten anlegen, ändern und an einen zweiten Test-TF senden. Dort Zwischenablage öffnen, übernehmen und manuell löschen.
9. **GPS:** präzisen Standort erlauben, GPS einschalten, Zugnummer eingeben, Aufzeichnung starten. Auf einem geeigneten Testweg einige Positionen sammeln, Bildschirm sperren, später entsperren und denselben Bericht öffnen. Beenden, synchronisieren und GPX speichern. Standzeiten entstehen erst bei weniger als 3 km/h für länger als fünf Minuten. ZMS bleiben zu prüfende Vorschläge; fehlende GPS-Fixes werden nicht erfunden.
10. **Sprache:** Flagge wechseln, Portal erneut öffnen, Sprache prüfen.
11. **Altbestand:** **Bisherige Erfassungen** öffnen; alte lokale Einträge müssen weiterhin sichtbar sein. Sie werden nicht automatisch als neue Arbeitsberichte doppelt übertragen.

Bei GPS-Sperrbildschirmtests prüfen, dass die Standortbenachrichtigung sichtbar ist. Nach „Stopp erzwingen“, entzogenem Standortrecht oder beendetem Systemdienst muss die Aufzeichnung ausdrücklich fortgesetzt werden. Hersteller-Stromsparregeln können praktische Gerätetests erforderlich machen.

## 12. Einmalig GitHub für updatefähige APKs einrichten

Die Action **Android TF Portal APK** baut und prüft Änderungen. Ohne eigenen hinterlegten Schlüssel erzeugt sie nur ein Test-Artefakt. **Für den dauerhaften Updatekanal müssen die folgenden Secrets eingerichtet werden.**

### 12.1 Signierschlüssel als GitHub-Secrets hinterlegen

1. Repository im Browser öffnen: https://github.com/omueller369/LokZeitleiste
2. **Settings → Secrets and variables → Actions → New repository secret**.
3. Auf dem Mac den privaten Keystore Base64-kodiert in die Zwischenablage kopieren:

   ```bash
   base64 -i "$HOME/.lokzeitleiste-signing/tf-test.jks" | pbcopy
   ```

   Bei Weiterverwendung eines vorhandenen Schlüssels dessen tatsächlichen Pfad einsetzen.
4. Secret mit dem Namen **ANDROID_KEYSTORE_BASE64** anlegen; den Inhalt der Zwischenablage als Wert einfügen und speichern.
5. Drei weitere Secrets anlegen:

   | Secret-Name | Inhalt |
   |---|---|
   | `ANDROID_KEYSTORE_PASSWORD` | tatsächliches Keystore-Passwort |
   | `ANDROID_KEY_ALIAS` | `ctl-test`, bzw. der tatsächlich verwendete Alias |
   | `ANDROID_KEY_PASSWORD` | tatsächliches Schlüsselpasswort |

6. Keine dieser Daten in Issues, README-Dateien, Chats oder Commits einfügen. Der Base64-Inhalt ist kein zusätzlicher Schutz; er gehört ausschließlich in das Secret-Feld.

Der Workflow hat für das Veröffentlichen im eigenen Repository `contents: write`. Wenn eine Organisationsrichtlinie GitHub Actions das Erstellen von Releases verbietet, muss der Repository-/Organisationsadministrator diese konkrete Berechtigung freigeben.

### 12.2 Ersten signierten Update-Build starten

**Im aktuellen Arbeitsbranch zuverlässig per Push:** Nach dem Einrichten der vier Secrets auf dem Mac eine kleine Dokumentationsänderung im überwachten App-Verzeichnis pushen:

```bash
cd "$HOME/Developer/LokZeitleiste"
git pull --ff-only origin setup/debian-testumgebung
printf '\nTablet-Testbuild mit dauerhaftem Signierschluessel ausgeloest.\n' >> app/docs/TF-PORTAL.md
git add app/docs/TF-PORTAL.md
git commit -m "Signierten Android-Tablet-Testbuild starten"
git push origin setup/debian-testumgebung
```

Die Action startet durch diesen Push. Unter **Actions → Android TF Portal APK** den neuen Lauf öffnen und auf erfolgreichen Abschluss warten.

**Alternativ per Schaltfläche, sofern verfügbar:** GitHub zeigt **Run workflow** normalerweise erst zuverlässig an, wenn die Workflow-Datei auch im Standardbranch vorhanden ist. Das Repository verwendet zunächst `main`, während diese Änderungen im Arbeitsbranch liegen. Fehlt die Schaltfläche, den oben beschriebenen Push verwenden; für die Erstinstallation muss deshalb nichts ungeprüft nach `main` zusammengeführt werden.

1. Auf GitHub **Actions** öffnen.
2. Links **Android TF Portal APK** wählen.
3. **Run workflow** anklicken.
4. Branch **setup/debian-testumgebung** auswählen.
5. **Run workflow** bestätigen und den Lauf öffnen.
6. Auf erfolgreichen Abschluss warten. Tests, APK-Build und Lint müssen erfolgreich sein.
7. Unter **Releases** erscheint danach eine Vorabversion mit einem Tag wie **android-test-12**. Der Zahlenwert ist ein Beispiel; verwendet wird die tatsächliche GitHub-Laufnummer.
8. In dieser Vorabversion liegen:
   - **LokZeitleiste-TF-Portal.apk** – die mit dem eigenen Schlüssel signierte Test-APK
   - **update.json** – Versionscode und SHA-256-Prüfsumme für die App.

Wenn nur ein Artefakt unter dem Action-Lauf, aber kein Release entsteht, zuerst die vier Secrets und den Schritt **Publish signed tablet test update** prüfen. Ein fehlender Schlüssel aktiviert keinen dauerhaften Updatekanal.

### 12.3 Diese signierte Version auf dem Tablet installieren

Die APK aus **Releases**, nicht irgendeine alte unsignierte/anders signierte Test-APK, herunterladen und wie in Abschnitt 10 installieren. Eine zuvor lokal mit demselben Schlüssel signierte Version kann regulär aktualisiert werden. Danach ist das Tablet im Updatekanal.

## 13. So kommen spätere Updates automatisch aufs Tablet

1. App- oder Portaländerungen in den Branch **setup/debian-testumgebung** übertragen.
2. GitHub startet die Action für Änderungen an App, Portaldateien oder relevanter Buildkonfiguration automatisch. Reine Änderungen außerhalb der überwachten Pfade lösen keinen neuen App-Build aus; bei Bedarf einen entsprechenden App-Dokumentations-Push wie in Abschnitt 12.2 auslösen oder, sofern verfügbar, **Run workflow** benutzen.
3. Bei erfolgreichen Prüfungen und eingerichteten Secrets veröffentlicht die Action eine neue signierte Testversion mit einem höheren Versionscode.
4. Beim nächsten Öffnen/Fortsetzen prüft die Tablet-App den Testkanal; spätestens eine erneute Prüfung nach dem Sechs-Stunden-Intervall erkennt die neue Version. Sofortprüfung über **Update**.
5. Die APK wird automatisch heruntergeladen und geprüft.
6. Offene Eingaben zunächst mit den jeweiligen Speichern-Schaltflächen sichern. Danach **Update installieren** antippen.
7. Falls Android fragt: für **LokZeitleiste** einmal **Aus dieser Quelle zulassen** aktivieren und zur App zurückkehren.
8. Im Android-Paketinstaller **Aktualisieren/Installieren** bestätigen.
9. App erneut öffnen und den aktuellen Stand prüfen. Bei regulärem Update bleiben lokale Berichte und die Anmeldung grundsätzlich erhalten; ein serverseitig ungültig gewordenes Konto muss sich neu anmelden.

Zum kontrollierten ersten Update-Test eine kleine nachvollziehbare Änderung an `app/docs/TF-PORTAL.md` committen/pushen oder die Action erneut manuell starten, sofern die Schaltfläche verfügbar ist. Nach dem neuen erfolgreichen Release in der App **Update** drücken. Während dieses Tests keine laufende GPS-Aufzeichnung offen lassen.

Wichtig: Eine neue Quellcode-Datei allein ist noch keine installierbare Version. Erst der erfolgreiche signierte Build mit den zwei Release-Dateien erzeugt ein Update. Die App installiert keine Rohdateien aus dem Repository.

## 14. Häufige Fehler

| Meldung/Symptom | Prüfung/Lösung |
|---|---|
| `SDK location not found` | SDK im SDK Manager installieren und `ANDROID_HOME` bzw. den lokalen SDK-Pfad in Android Studio richtig setzen. |
| Gradle/JDK inkompatibel | Gradle 8.9 und JDK 17 wählen; nicht blind auf Gradle 9 umstellen. |
| `android.useAndroidX` fehlt | Aktuellen Branch ziehen; die gemeinsame `gradle.properties` enthält die Einstellung. |
| `unauthorized` bei `adb devices` | Tablet entsperren und USB-Debugging für den Mac bestätigen. |
| Tablet wird nicht angezeigt | Datenkabel/Port, USB-Debugging und ggf. USB-Modus prüfen. |
| `INSTALL_FAILED_UPDATE_INCOMPATIBLE` | Signierschlüssel passt nicht. Mit dem ursprünglichen Schlüssel bauen. Nicht ungeprüft deinstallieren. |
| `INSTALL_FAILED_VERSION_DOWNGRADE` | APK-Version ist niedriger. Aktuelle signierte GitHub-Version verwenden; keine Daten löschende Umgehung wählen. |
| Anmeldung/Server nicht erreichbar | Tablet-Browser mit HTTPS-Domain testen; DNS, Zertifikat und Server prüfen. |
| GitHub veröffentlicht kein Update | Build/Lint erfolgreich? Vier Secrets vorhanden? Richtiger Branch? Release-Schritt ausgeführt? |
| App findet keine neuere Version | Signiertes `android-test-*`-Release samt APK und `update.json` vorhanden? Versionscode höher? Internet erreichbar? Sofortprüfung über **Update**. |
| App lehnt Update ab | Prüfsumme, Paketname oder Zertifikat passt nicht. Nicht durch Abschalten der Prüfung umgehen. |
| GitHub HTTP 403 bei der Update-Prüfung | Öffentliche GitHub-API kann vorübergehend begrenzt sein. Später erneut prüfen; kein persönliches GitHub-Passwort in die App eingeben. |
| Android blockiert die Installation | Eigene Quelle einmal zulassen; verwaltete Tablets können zusätzlich einer Geräteverwaltung unterliegen. |
| GPS-Aufzeichnung unterbrochen | Präzisen Standort, eingeschaltetes GPS und Standortdienst prüfen; betroffene Zugfahrt öffnen und fortsetzen/beenden. |

## 15. Offizielle Nachschlagequellen

- Android Studio: https://developer.android.com/studio
- Physisches Gerät verbinden: https://developer.android.com/studio/run/device
- App-Signierung: https://developer.android.com/studio/publish/app-signing
- Android-Installationsbestätigung: https://developer.android.com/reference/android/content/pm/PackageInstaller.SessionParams
- Weitere projektspezifische Funktionen/Offline-Grenzen: [TF-PORTAL.md](TF-PORTAL.md)
