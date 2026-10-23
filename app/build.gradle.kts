plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

val apiBaseUrl = providers.gradleProperty("lokzeitleisteApiBaseUrl").orElse("https://ctl-software.io-goerlitz.eu").get()

android {
    namespace = "de.lokzeitleiste.app"
    compileSdk = 35
    defaultConfig {
        applicationId = "de.lokzeitleiste.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 11
        versionName = "0.11"
        buildConfigField("String", "API_BASE_URL", "\"${apiBaseUrl}\"")
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
        include("tf-portal.*", "work-report.*", "train-journeys.js", "gps.js", "stations.js",
            "station-sharing.js", "tf-return.js", "documents.*", "account.*", "my-worktime.*",
            "entry-form.js", "portal.css", "responsive.css", "i18n.js", "android-portal.js")
    }
    into(portalAssets.map { it.dir("tf-portal") })
}
android.sourceSets["main"].assets.srcDir(portalAssets)
tasks.named("preBuild").configure { dependsOn(prepareTfPortal) }
