plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

val apiBaseUrl = providers.gradleProperty("lokzeitleisteApiBaseUrl").orElse("https://ctl-software.io-goerlitz.eu").get()

android {
    namespace = "de.lokzeitleiste.app"
    compileSdk = 35
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
    defaultConfig {
        applicationId = "de.lokzeitleiste.app"
        minSdk = 26
        targetSdk = 35
        versionCode = providers.gradleProperty("lokzeitleisteVersionCode").orElse("26").get().toInt()
        versionName = providers.gradleProperty("lokzeitleisteVersionName").orElse("0.26").get()
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
val prepareTfPortal by tasks.registering(Sync::class) {
    from(rootProject.file("backend/lokzeitleiste/static")) {
        include("national-brake-sheet.*", "brake-sheet.*", "tf-shell.*", "tf-messages.*", "tf-profile.*", "tf-signature.*", "ctl-logistics-logo.jpg", "handover-protocols.js", "loco-handover.*", "tf-portal.*", "work-report.*", "work-report-feedback.js", "train-journeys.js", "gps.js", "stations.js",
            "station-sharing.js", "tf-return.js", "documents.*", "account.*", "my-worktime.*",
            "entry-form.js", "portal.css", "responsive.css", "i18n.js", "android-portal.js")
    }
    into(portalAssets.map { it.dir("tf-portal") })
}
android.sourceSets["main"].assets.srcDir(portalAssets)
tasks.named("preBuild").configure { dependsOn(prepareTfPortal) }
