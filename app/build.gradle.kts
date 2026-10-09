plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

val apiBaseUrl = providers.gradleProperty("lokzeitleisteApiBaseUrl").orElse("").get()

android {
    namespace = "de.lokzeitleiste.app"
    compileSdk = 35
    defaultConfig {
        applicationId = "de.lokzeitleiste.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 9
        versionName = "0.9"
        buildConfigField("String", "API_BASE_URL", "\"${apiBaseUrl}\"")
    }
    buildFeatures { compose = true; buildConfig = true }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2024.12.01"))
    implementation("androidx.activity:activity-compose:1.10.0")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    debugImplementation("androidx.compose.ui:ui-tooling")
}
