package de.lokzeitleiste.app

import android.content.Context
import android.content.res.Configuration
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import de.lokzeitleiste.app.network.ApiClient
import de.lokzeitleiste.app.network.TokenVault
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.util.Locale

object LanguageRuntime {
    @Volatile var code = "de"
    var accountVersion by mutableStateOf(0)
    val codes = listOf("de", "en", "pl", "ru", "tr", "ar", "es")
    val labels = listOf("🇩🇪 Deutsch", "🇬🇧 English", "🇵🇱 Polski", "🇷🇺 Русский", "🇹🇷 Türkçe", "🇸🇦 العربية", "🇪🇸 Español")
    private var catalog: JSONObject? = null
    private var pattern: Regex? = null
    private val canonical = mutableMapOf<String, String>()
    fun initialize(context: Context) {
        if (catalog != null) return
        catalog = JSONObject(context.assets.open("catalog.json").bufferedReader().use { it.readText() })
        for (lang in codes) {
            val map = catalog!!.getJSONObject(lang)
            map.keys().forEach { key -> canonical.putIfAbsent(map.getString(key), key) }
        }
        val keys = catalog!!.getJSONObject("de").keys().asSequence().toList().sortedByDescending { it.length }
        pattern = Regex("(?<![\\p{L}\\p{N}_])(?:" + keys.joinToString("|") { Regex.escape(it) } + ")(?![\\p{L}\\p{N}_])")
    }
    fun translate(value: String, language: String): String {
        val original = canonical[value] ?: value
        if (language == "de") return original
        val mapping = catalog?.optJSONObject(language) ?: return value
        if (mapping.has(original)) return mapping.getString(original)
        return pattern?.replace(original) { mapping.optString(it.value, it.value) } ?: value
    }
    fun locale() = Locale.forLanguageTag(code)
}

val LocalLanguage = staticCompositionLocalOf { "de" }

@Composable
fun LocalizedText(text: String, modifier: Modifier = Modifier, color: Color = Color.Unspecified,
                  style: TextStyle = LocalTextStyle.current, localize: Boolean = true) {
    Text(if (localize) LanguageRuntime.translate(text, LocalLanguage.current) else text,
         modifier = modifier, color = color, style = style)
}

@Composable
fun LanguageShell(content: @Composable () -> Unit) {
    val context = LocalContext.current
    val prefs = remember { context.getSharedPreferences("lokzeitleiste_language", Context.MODE_PRIVATE) }
    var language by remember { mutableStateOf(prefs.getString("language", "de") ?: "de") }
    var expanded by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    LanguageRuntime.initialize(context)
    LanguageRuntime.code = language
    val accountVersion = LanguageRuntime.accountVersion
    val username = remember(accountVersion) { TokenVault.username(context) }
    LaunchedEffect(username) {
        if (username.isNotBlank()) {
            val local = prefs.getString("language.$username", null)
            if (local in LanguageRuntime.codes) language = local!!
            val token = TokenVault.token(context)
            if (token != null) runCatching { ApiClient.getLanguage(token) }.onSuccess { value ->
                if (value.optBoolean("configured") && value.optString("language") in LanguageRuntime.codes) {
                    language = value.getString("language")
                    prefs.edit().putString("language", language).putString("language.$username", language).apply()
                } else runCatching { ApiClient.setLanguage(token, language) }
            }
        }
    }
    val localizedContext = remember(language) {
        val configuration = Configuration(context.resources.configuration)
        configuration.setLocale(Locale.forLanguageTag(language))
        context.createConfigurationContext(configuration)
    }
    CompositionLocalProvider(LocalLanguage provides language, LocalContext provides localizedContext,
        LocalLayoutDirection provides if (language == "ar") LayoutDirection.Rtl else LayoutDirection.Ltr) {
        Column(Modifier.fillMaxSize()) {
            Row(Modifier.fillMaxWidth().padding(8.dp), horizontalArrangement = Arrangement.End) {
                Box {
                    OutlinedButton(onClick = { expanded = true }) {
                        Text(LanguageRuntime.labels[LanguageRuntime.codes.indexOf(language).coerceAtLeast(0)] + " ▾")
                    }
                    DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                        LanguageRuntime.codes.forEachIndexed { index, code ->
                            DropdownMenuItem(text = { Text(LanguageRuntime.labels[index]) }, onClick = {
                                language = code; LanguageRuntime.code = code; expanded = false
                                prefs.edit().putString("language", code).putString("language.$username", code).apply()
                                TokenVault.token(context)?.let { token -> scope.launch { runCatching { ApiClient.setLanguage(token, code) } } }
                            })
                        }
                    }
                }
            }
            Box(Modifier.weight(1f)) { content() }
        }
    }
}
