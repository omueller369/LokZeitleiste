import groovy.json.JsonSlurper

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

val apiBaseUrl = providers.gradleProperty("lokzeitleisteApiBaseUrl").orElse("https://ctl-software.io-goerlitz.eu").get()

// Read the visible application version from the shared backend version source.
val softwareVersion = Regex("""SOFTWARE_VERSION\s*=\s*['"]([^'"]+)['"]""")
    .find(rootProject.file("backend/lokzeitleiste/version.py").readText())
    ?.groupValues?.get(1) ?: error("Shared software version is missing")

android {
    namespace = "de.lokzeitleiste.app"
    compileSdk = 35
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
    defaultConfig {
        applicationId = "de.lokzeitleiste.app"
        minSdk = 26
        targetSdk = 35
        versionCode = providers.gradleProperty("lokzeitleisteVersionCode").orElse("56").get().toInt()
        versionName = providers.gradleProperty("lokzeitleisteVersionName").orElse(softwareVersion).get()
        buildConfigField("String", "API_BASE_URL", "\"${apiBaseUrl}\"")
    }
    val signingPath = providers.gradleProperty("lokzeitleisteSigningStoreFile").orElse(providers.environmentVariable("ANDROID_KEYSTORE_PATH")).orNull
    if (signingPath != null && file(signingPath).exists()) {
        signingConfigs.getByName("debug") {
            storeFile = file(signingPath)
            storePassword = providers.gradleProperty("lokzeitleisteSigningStorePassword").orElse(providers.environmentVariable("ANDROID_KEYSTORE_PASSWORD")).get()
            keyAlias = providers.gradleProperty("lokzeitleisteSigningKeyAlias").orElse(providers.environmentVariable("ANDROID_KEY_ALIAS")).get()
            keyPassword = providers.gradleProperty("lokzeitleisteSigningKeyPassword").orElse(providers.environmentVariable("ANDROID_KEY_PASSWORD")).get()
        }
    }
    buildFeatures { compose = true; buildConfig = true }
}

dependencies {
    implementation("androidx.webkit:webkit:1.12.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    testImplementation("junit:junit:4.13.2")
    implementation(platform("androidx.compose:compose-bom:2024.12.01"))
    implementation("androidx.activity:activity-compose:1.10.0")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    debugImplementation("androidx.compose.ui:ui-tooling")
}

// Package the actual shared portal sources on every build; no second UI implementation.
val portalAssets = layout.buildDirectory.dir("generated/portalAssets")
val portalMessageFile = rootProject.file("backend/lokzeitleiste/locales/keys.json")
val portalSourceMessages = (JsonSlurper().parse(portalMessageFile) as Map<*, *>)["de"] as Map<*, *>
val portalMessageToken = Regex("""\{\{([a-z][a-z0-9_]*\.text_[a-f0-9]{12})\}\}""")
val prepareTfPortal by tasks.registering(Sync::class) {
    inputs.file(portalMessageFile)
    filteringCharset = "UTF-8"
    from(rootProject.file("backend/lokzeitleiste/static")) {
        include("messages.js", "national-brake-sheet.*", "brake-sheet.*", "tf-shell.*", "portal-theme.*", "plan-colors.js", "auth-session.js", "tf-help*", "tf-notes.*", "tf-messages.*", "tf-profile.*", "tf-signature.*", "ctl-logistics-logo.jpg", "rail-software-*.png", "handover-protocols.js", "loco-handover.*", "tf-portal.*", "work-report.*", "work-report-feedback.js", "train-journeys.js", "gps.js", "stations.js",
            "station-sharing.js", "tf-return.js", "documents.*", "account.*", "my-worktime.*",
            "entry-form.js", "portal.css", "responsive.css", "i18n.js", "android-portal.js")
    }
    // Match the server's template rendering before WebView sees the page. Static
    // labels inside data-i18n-ignore must be resolved too; user values are untouched.
    filesMatching("*.html") {
        filter { line: String ->
            portalMessageToken.replace(line) { match ->
                portalSourceMessages[match.groupValues[1]] as? String
                    ?: error("Unknown Android portal translation: ${match.groupValues[1]}")
            }
        }
    }
    into(portalAssets.map { it.dir("tf-portal") })
    doLast {
        destinationDir.walkTopDown().filter { it.extension == "html" }.forEach { page ->
            check(!Regex("""\{\{[a-z][a-z0-9_]*\.[a-z0-9_]+\}\}""").containsMatchIn(page.readText(Charsets.UTF_8))) {
                "Unresolved Android portal translation in ${page.name}"
            }
        }
    }
}
android.sourceSets["main"].assets.srcDir(portalAssets)
tasks.named("preBuild").configure { dependsOn(prepareTfPortal) }
