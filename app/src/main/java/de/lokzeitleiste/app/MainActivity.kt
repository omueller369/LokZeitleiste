package de.lokzeitleiste.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import org.json.JSONArray
import org.json.JSONObject
import java.security.SecureRandom
import java.time.*
import java.time.format.DateTimeFormatter
import java.util.Base64
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.PBEKeySpec

private val kinds = listOf("Rufbereitschaft", "Bereitschaft", "Zugfahrt", "Ausfallschicht", "Krank", "Urlaub", "Sonstige Erfassung")
private val dateFormat = DateTimeFormatter.ofPattern("dd.MM.yyyy")
private data class Entry(val kind: String, val date: String, val start: String, val end: String, val pause: Int, val guest: Int, val note: String)
private fun minutes(time: String): Int = LocalTime.parse(time).let { it.hour * 60 + it.minute }
private fun length(e: Entry): Int {
    val start = minutes(e.start); var end = minutes(e.end)
    if (end <= start) end += 1440
    return (end - start - e.pause).coerceAtLeast(0)
}
private fun overlap(e: Entry, condition: (LocalDateTime) -> Boolean): Int {
    val date = LocalDate.parse(e.date)
    val from = date.atTime(LocalTime.parse(e.start))
    val until = from.plusMinutes(length(e).toLong() + e.pause)
    // Break placement is unknown. Allocate break minutes against the overlap.
    var count = 0
    var time = from
    while (time < until) { if (condition(time)) count++; time = time.plusMinutes(1) }
    return (count - e.pause.coerceAtMost(count)).coerceAtLeast(0)
}
private fun displayTime(n: Int) = "%d:%02d h".format(n / 60, n % 60)
private fun load(context: android.content.Context, username: String): List<Entry> = runCatching {
    val raw = context.getSharedPreferences("entries_$username", 0).getString("data", "[]")
    val a = JSONArray(raw)
    (0 until a.length()).map { i -> a.getJSONObject(i).let {
        Entry(it.getString("kind"), it.getString("date"), it.getString("start"), it.getString("end"), it.getInt("pause"), it.getInt("guest"), it.optString("note"))
    } }
}.getOrDefault(emptyList())
private fun save(context: android.content.Context, username: String, entries: List<Entry>) {
    val a = JSONArray()
    entries.forEach { a.put(JSONObject().put("kind", it.kind).put("date", it.date).put("start", it.start).put("end", it.end).put("pause", it.pause).put("guest", it.guest).put("note", it.note)) }
    context.getSharedPreferences("entries_$username", 0).edit().putString("data", a.toString()).apply()
}
private fun hash(password: String, salt: ByteArray): String {
    val spec = PBEKeySpec(password.toCharArray(), salt, 150000, 256)
    return try { Base64.getEncoder().encodeToString(SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(spec).encoded) }
    finally { spec.clearPassword() }
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { MaterialTheme { App() } }
    }
}

@Composable
private fun App() {
    val context = LocalContext.current
    val auth = remember { context.getSharedPreferences("auth", 0) }
    var user by remember { mutableStateOf(auth.getString("session", "") ?: "") }
    var trainScreen by remember { mutableStateOf(false) }
    if (user.isBlank()) Login { name -> user = name; auth.edit().putString("session", name).apply() }
    else if (trainScreen) Column {
        Row(Modifier.padding(16.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Button(onClick = { trainScreen = false }) { Text("← Monatsübersicht") }
            Text("Zugfahrten · $user", modifier = Modifier.padding(10.dp))
        }
        Box(Modifier.weight(1f)) { LokZeitApp(user) }
    } else MonthScreen(user, onTrain = { trainScreen = true }, onLogout = {
        auth.edit().remove("session").apply(); user = ""
    })
}

@Composable
private fun Login(onSuccess: (String) -> Unit) {
    val context = LocalContext.current
    val auth = remember { context.getSharedPreferences("auth", 0) }
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var message by remember { mutableStateOf("") }
    Column(Modifier.fillMaxSize().padding(32.dp), verticalArrangement = Arrangement.Center) {
        Text("LokZeitleiste", style = MaterialTheme.typography.headlineLarge)
        Text("Lokales Konto auf diesem Gerät anmelden oder anlegen")
        Spacer(Modifier.height(24.dp))
        OutlinedTextField(username, { username = it.trim().lowercase() }, label = { Text("Benutzername") })
        OutlinedTextField(password, { password = it }, label = { Text("Passwort") }, visualTransformation = PasswordVisualTransformation())
        Text(message, color = MaterialTheme.colorScheme.error)
        Button(onClick = {
            val name = username
            if (!Regex("[a-z0-9._-]{3,32}").matches(name) || password.length < 8) {
                message = "Benutzername: 3–32 Zeichen (a–z, 0–9, ._-); Passwort: mindestens 8 Zeichen."
            } else {
                val stored = auth.getString("account_$name", null)
                if (stored == null) {
                    val salt = ByteArray(16).also { SecureRandom().nextBytes(it) }
                    auth.edit().putString("account_$name", Base64.getEncoder().encodeToString(salt) + ":" + hash(password, salt)).apply()
                    onSuccess(name)
                } else {
                    val parts = stored.split(":")
                    val actual = runCatching { hash(password, Base64.getDecoder().decode(parts[0])) }.getOrNull()
                    if (parts.size == 2 && java.security.MessageDigest.isEqual((actual ?: "").toByteArray(), parts[1].toByteArray())) onSuccess(name)
                    else message = "Benutzername oder Passwort stimmt nicht."
                }
            }
        }) { Text("Anmelden / lokales Konto anlegen") }
        Text("Die Anmeldung bleibt auf diesem Gerät gespeichert. Keine Synchronisierung.", style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun MonthScreen(username: String, onTrain: () -> Unit, onLogout: () -> Unit) {
    val context = LocalContext.current
    var month by remember { mutableStateOf(YearMonth.now()) }
    var entries by remember(username) { mutableStateOf(load(context, username)) }
    var kind by remember { mutableStateOf(kinds[2]) }
    var date by remember { mutableStateOf(LocalDate.now().toString()) }
    var start by remember { mutableStateOf("06:00") }
    var end by remember { mutableStateOf("14:00") }
    var pause by remember { mutableStateOf("0") }
    var guest by remember { mutableStateOf("0") }
    var note by remember { mutableStateOf("") }
    var error by remember { mutableStateOf("") }
    var expanded by remember { mutableStateOf(false) }
    val selected = entries.filter { runCatching { YearMonth.from(LocalDate.parse(it.date)) == month }.getOrDefault(false) }.sortedBy { it.date + it.start }
    val work = selected.filter { it.kind in listOf("Bereitschaft", "Zugfahrt", "Sonstige Erfassung") }.sumOf { length(it) }
    val guests = selected.sumOf { it.guest }
    val holidays = selected.count { it.kind == "Urlaub" }
    val night = selected.filter { it.kind in listOf("Bereitschaft", "Zugfahrt", "Sonstige Erfassung") }.sumOf {
        overlap(it) { t -> t.hour >= 22 || t.hour < 6 }
    }
    val sunday = selected.filter { it.kind in listOf("Bereitschaft", "Zugfahrt", "Sonstige Erfassung") }.sumOf {
        overlap(it) { t -> t.dayOfWeek == DayOfWeek.SUNDAY }
    }
    Column(Modifier.fillMaxSize()) {
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(24.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("LokZeitleiste", style = MaterialTheme.typography.headlineMedium)
                OutlinedButton(onClick = onTrain) { Text("Zugfahrt · LokZeit") }
                TextButton(onClick = onLogout) { Text("Abmelden · $username") }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedButton(onClick = { month = month.minusMonths(1) }) { Text("‹") }
                Text(month.month.getDisplayName(java.time.format.TextStyle.FULL, java.util.Locale.GERMAN) + " " + month.year,
                    style = MaterialTheme.typography.headlineSmall, modifier = Modifier.padding(10.dp))
                OutlinedButton(onClick = { month = month.plusMonths(1) }) { Text("›") }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(24.dp)) {
                Card(Modifier.width(310.dp)) { Column(Modifier.padding(16.dp)) {
                    Text("Neue Erfassung", style = MaterialTheme.typography.titleLarge)
                    Box {
                        OutlinedButton(onClick = { expanded = true }) { Text(kind + " ▾") }
                        DropdownMenu(expanded, onDismissRequest = { expanded = false }) {
                            kinds.forEach { option -> DropdownMenuItem(text = { Text(option) }, onClick = { kind = option; expanded = false }) }
                        }
                    }
                    OutlinedTextField(date, { date = it }, label = { Text("Datum (JJJJ-MM-TT)") })
                    OutlinedTextField(start, { start = it }, label = { Text("Beginn (HH:MM)") })
                    OutlinedTextField(end, { end = it }, label = { Text("Ende (HH:MM)") })
                    OutlinedTextField(pause, { pause = it }, label = { Text("Pause (Minuten)") })
                    OutlinedTextField(guest, { guest = it }, label = { Text("Gastfahrt (Minuten)") })
                    OutlinedTextField(note, { note = it }, label = { Text("Notiz") })
                    if (error.isNotBlank()) Text(error, color = MaterialTheme.colorScheme.error)
                    Button(onClick = {
                        val p = pause.toIntOrNull(); val g = guest.toIntOrNull()
                        val candidate = runCatching { Entry(kind, LocalDate.parse(date).toString(), LocalTime.parse(start).toString(), LocalTime.parse(end).toString(), p!!, g!!, note) }.getOrNull()
                        error = when {
                            candidate == null || p == null || g == null || p < 0 || g < 0 -> "Datum, Zeiten und Minuten prüfen."
                            kind == "Urlaub" && entries.any { it.date == candidate.date && it.kind == "Urlaub" } -> "Urlaub ist für diesen Tag bereits erfasst."
                            kind != "Urlaub" && (length(candidate) <= 0 || g > length(candidate)) -> "Dauer muss positiv sein; Gastfahrt darf Dauer nicht übersteigen."
                            else -> ""
                        }
                        if (error.isEmpty() && candidate != null) {
                            entries = entries + candidate; save(context, username, entries)
                            month = YearMonth.from(LocalDate.parse(candidate.date)); note = ""
                        }
                    }) { Text("Eintrag speichern") }
                } }
                Card(Modifier.weight(1f)) { Column(Modifier.padding(16.dp)) {
                    Text("Erfassungen · ${selected.size}", style = MaterialTheme.typography.titleLarge)
                    val scroll = rememberScrollState()
                    Column(Modifier.horizontalScroll(scroll)) {
                        Row { listOf("Datum", "Art", "Zeitraum", "Pause", "Gastfahrt", "Dauer", "").forEach {
                            Text(it, Modifier.width(if (it == "Art") 150.dp else 105.dp), style = MaterialTheme.typography.labelMedium)
                        } }
                        HorizontalDivider()
                        selected.forEach { entry ->
                            Row {
                                Text(runCatching { LocalDate.parse(entry.date).format(dateFormat) }.getOrDefault(entry.date), Modifier.width(105.dp))
                                Text(entry.kind, Modifier.width(150.dp))
                                Text(if (entry.kind == "Urlaub") "Ganzer Tag" else "${entry.start}–${entry.end}", Modifier.width(105.dp))
                                Text("${entry.pause} min", Modifier.width(105.dp))
                                Text("${entry.guest} min", Modifier.width(105.dp))
                                Text(if (entry.kind == "Urlaub") "1 Tag" else displayTime(length(entry)), Modifier.width(105.dp))
                                TextButton(onClick = { entries = entries.toMutableList().also { it.remove(entry) }; save(context, username, entries) }) { Text("Löschen") }
                            }
                            HorizontalDivider()
                        }
                    }
                } }
            }
        }
        Surface(color = MaterialTheme.colorScheme.primaryContainer) {
            Row(Modifier.fillMaxWidth().padding(20.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                listOf("Arbeitszeit" to displayTime(work), "Gastfahrt" to displayTime(guests),
                    "Urlaub" to "$holidays Tage", "Nachtstunden*" to displayTime(night),
                    "Sonntagsstunden*" to displayTime(sunday)).forEach { (label, value) ->
                    Column { Text(value, style = MaterialTheme.typography.titleLarge); Text(label) }
                }
            }
        }
    }
}
