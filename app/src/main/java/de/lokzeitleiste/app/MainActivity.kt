package de.lokzeitleiste.app

import android.os.Bundle
import android.app.DatePickerDialog
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
import androidx.compose.ui.unit.dp
import java.time.*
import java.time.format.DateTimeFormatter
import de.lokzeitleiste.app.data.*
import de.lokzeitleiste.app.network.ApiClient
import de.lokzeitleiste.app.network.TokenVault
import kotlinx.coroutines.launch

private val kinds = listOf("Rufbereitschaft", "Bereitschaft", "Zugfahrt", "Ausfallschicht", "Krank", "Urlaub", "Sonstige Erfassung")
private val dateFormat = DateTimeFormatter.ofPattern("dd.MM.yyyy")

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { MaterialTheme { LanguageShell { App() } } }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun App() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var user by remember { mutableStateOf(TokenVault.username(context)) }
    var trainScreen by remember { mutableStateOf(false) }
    var passwordScreen by remember { mutableStateOf(false) }
    if (user.isBlank()) LoginScreen { name, token -> TokenVault.save(context, name, token); user = name }
    else if (passwordScreen) PasswordChangeScreen(user, TokenVault.token(context) ?: "",
        onSuccess = { name, token -> TokenVault.save(context, name, token); user = name; passwordScreen = false },
        onCancel = { passwordScreen = false })
    else if (trainScreen) Column {
        FlowRow(Modifier.padding(16.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Button(onClick = { trainScreen = false }) { LocalizedText("← Monatsübersicht") }
            LocalizedText("Zugfahrten · $user", modifier = Modifier.padding(10.dp))
        }
        Box(Modifier.weight(1f)) { LokZeitApp(user) }
    } else MonthScreen(user, onTrain = { trainScreen = true }, onPassword = { passwordScreen = true }, onLogout = {
        TokenVault.token(context)?.let { token -> scope.launch { runCatching { ApiClient.logout(token) } } }
        TokenVault.clear(context); user = ""
    })
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun MonthScreen(username: String, onTrain: () -> Unit, onPassword: () -> Unit, onLogout: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var month by remember { mutableStateOf(YearMonth.now()) }
    var entries by remember(username) { mutableStateOf(loadEntries(context, username)) }
    var kind by remember { mutableStateOf(kinds[2]) }
    var date by remember { mutableStateOf(LocalDate.now().toString()) }
    var endDate by remember { mutableStateOf(LocalDate.now().toString()) }
    var start by remember { mutableStateOf("06:00") }
    var end by remember { mutableStateOf("14:00") }
    var pause by remember { mutableStateOf("0") }
    var guest by remember { mutableStateOf("0") }
    var note by remember { mutableStateOf("") }
    var away by remember { mutableStateOf(false) }
    var accommodation by remember { mutableStateOf("") }
    var hotelName by remember { mutableStateOf("") }
    var accommodationExpanded by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf("") }
    var expanded by remember { mutableStateOf(false) }
    var transitionEntry by remember { mutableStateOf<Entry?>(null) }
    var transitionDate by remember { mutableStateOf(LocalDate.now().toString()) }
    var transitionTime by remember { mutableStateOf("12:00") }
    var trainEnd by remember { mutableStateOf("14:00") }
    var transitionError by remember { mutableStateOf("") }
    var sending by remember { mutableStateOf(false) }
    var sendMessage by remember { mutableStateOf("") }
    val selected = entries.filter { runCatching { YearMonth.from(LocalDate.parse(it.date)) == month }.getOrDefault(false) }.sortedBy { it.date + it.start }
    val calculationEntries = entries.filter { it.kind in listOf("Bereitschaft", "Zugfahrt", "Sonstige Erfassung") }
    val work = calculationEntries.sumOf { monthMinutes(it, month) }
    val guests = calculationEntries.sumOf { monthMinutes(it, month, guestOnly = true) }
    val holidays = selected.count { it.kind == "Urlaub" }
    val night = calculationEntries.sumOf {
        monthOverlap(it, month) { t -> t.hour >= 22 || t.hour < 6 }
    }
    val sunday = calculationEntries.sumOf {
        monthOverlap(it, month) { t -> t.dayOfWeek == DayOfWeek.SUNDAY }
    }
    Column(Modifier.fillMaxSize()) {
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(24.dp)) {
            FlowRow(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                LocalizedText("LokZeitleiste", style = MaterialTheme.typography.headlineMedium)
                OutlinedButton(onClick = onTrain) { LocalizedText("Zugfahrt · LokZeit") }
                Button(enabled = !sending, onClick = {
                    val token = TokenVault.token(context)
                    if (token == null) { onLogout(); return@Button }
                    saveEntries(context, username, entries)
                    sending = true; sendMessage = ""
                    scope.launch {
                        try {
                            val result = ApiClient.upload(month, selected, token)
                            sendMessage = "${result.accepted} Einträge für ${month.monthValue}/${month.year} übertragen." +
                                (if (result.emailQueued) " PDF-Bestätigung per E-Mail beauftragt." else "")
                        } catch (error: Exception) {
                            sendMessage = error.message ?: "Senden fehlgeschlagen."
                            if (sendMessage.startsWith("Anmeldung abgelaufen")) onLogout()
                        } finally { sending = false }
                    }
                }) { LocalizedText(if (sending) "Sende …" else "Monat senden") }
                TextButton(onClick = onLogout) { LocalizedText("Abmelden · $username") }
                TextButton(onClick = onPassword) { LocalizedText("Passwort ändern") }
            }
            if (sendMessage.isNotBlank()) LocalizedText(sendMessage, style = MaterialTheme.typography.bodySmall)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { month = month.minusMonths(1) }) { LocalizedText("‹") }
                LocalizedText(month.month.getDisplayName(java.time.format.TextStyle.FULL, LanguageRuntime.locale()) + " " + month.year,
                    style = MaterialTheme.typography.headlineSmall, modifier = Modifier.padding(10.dp))
                OutlinedButton(onClick = { month = month.plusMonths(1) }) { LocalizedText("›") }
            }
            FlowRow(horizontalArrangement = Arrangement.spacedBy(24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                Card(Modifier.widthIn(max = 310.dp).fillMaxWidth()) { Column(Modifier.padding(16.dp)) {
                    LocalizedText("Neue Erfassung", style = MaterialTheme.typography.titleLarge)
                    Box {
                        OutlinedButton(onClick = { expanded = true }) { LocalizedText(kind + " ▾") }
                        DropdownMenu(expanded, onDismissRequest = { expanded = false }) {
                            kinds.forEach { option -> DropdownMenuItem(text = { LocalizedText(option) }, onClick = { kind = option; expanded = false }) }
                        }
                    }
                    OutlinedTextField(date, { if (endDate == date) endDate = it; date = it }, label = { LocalizedText("Datum (JJJJ-MM-TT)") })
                    OutlinedTextField(start, { start = it }, label = { LocalizedText("Beginn (HH:MM)") })
                    OutlinedTextField(endDate, {}, readOnly = true, label = { LocalizedText("Datum Arbeitsende") }, trailingIcon = {
                        TextButton(onClick = {
                            val chosen = runCatching { LocalDate.parse(endDate) }.getOrDefault(LocalDate.now())
                            val picker = DatePickerDialog(context, { _, y, m, d -> endDate = LocalDate.of(y, m + 1, d).toString() }, chosen.year, chosen.monthValue - 1, chosen.dayOfMonth)
                            runCatching { LocalDate.parse(date).atStartOfDay(ZoneId.systemDefault()).toInstant().toEpochMilli() }.getOrNull()?.let { picker.datePicker.minDate = it }
                            picker.show()
                        }) { LocalizedText("Datum") }
                    })
                    OutlinedTextField(end, { end = it }, label = { LocalizedText("Ende (HH:MM)") })
                    if (kind == "Rufbereitschaft" || kind == "Bereitschaft") {
                        LocalizedText(if (kind == "Rufbereitschaft")
                            "Tarifgrenze: nur 08:00–20:00 Uhr, höchstens 8 Stunden."
                            else "Zeiten laut Personalplanung; vorläufig höchstens 8 Stunden, auch über Mitternacht.",
                            style = MaterialTheme.typography.bodySmall)
                        Row { Switch(checked = away, onCheckedChange = { away = it })
                            LocalizedText("Auswärts verbracht", modifier = Modifier.padding(12.dp)) }
                        if (away) {
                            Box {
                                OutlinedButton(onClick = { accommodationExpanded = true }) {
                                    LocalizedText((accommodation.ifBlank { "Unterkunft wählen" }) + " ▾")
                                }
                                DropdownMenu(accommodationExpanded, onDismissRequest = { accommodationExpanded = false }) {
                                    listOf("Dienstwohnung", "Hotel").forEach { option ->
                                        DropdownMenuItem(text = { LocalizedText(option) }, onClick = {
                                            accommodation = option; accommodationExpanded = false
                                            if (option != "Hotel") hotelName = ""
                                        })
                                    }
                                }
                            }
                            if (accommodation == "Hotel") OutlinedTextField(hotelName, { hotelName = it },
                                label = { LocalizedText("Name des Hotels") })
                        }
                        LocalizedText("Ausbleibe wird später berechnet: voller Kalendertag oder sonstiger Zeitraum.",
                            style = MaterialTheme.typography.bodySmall)
                    } else {
                        OutlinedTextField(pause, { pause = it }, label = { LocalizedText("Pause (Minuten)") })
                        OutlinedTextField(guest, { guest = it }, label = { LocalizedText("Gastfahrt (Minuten)") })
                        OutlinedTextField(note, { note = it }, label = { LocalizedText("Notiz") })
                    }
                    if (error.isNotBlank()) LocalizedText(error, color = MaterialTheme.colorScheme.error)
                    Button(onClick = {
                        val isStandby = kind == "Rufbereitschaft" || kind == "Bereitschaft"
                        val p = if (isStandby) 0 else pause.toIntOrNull()
                        val g = if (isStandby) 0 else guest.toIntOrNull()
                        val candidate = runCatching { Entry(kind, LocalDate.parse(date).toString(),
                            LocalTime.parse(start).toString(), LocalTime.parse(end).toString(), p!!, g!!,
                            if (isStandby) "" else note, isStandby && away,
                            if (isStandby && away) accommodation else "",
                            if (isStandby && away && accommodation == "Hotel") hotelName.trim() else "",endDate=LocalDate.parse(endDate).toString()) }.getOrNull()
                        error = when {
                            candidate == null || p == null || g == null || p < 0 || g < 0 -> "Datum, Zeiten und Minuten prüfen."
                            !endAt(candidate).isAfter(startAt(candidate)) -> "Arbeitsende muss nach dem Arbeitsbeginn liegen. Späteres Enddatum wählen."
                            kind in listOf("Urlaub", "Krank") && candidate.endDate != candidate.date -> "Urlaub/Krank werden je Tag einzeln erfasst."
                            kind == "Rufbereitschaft" && (minutes(candidate.start) < 8 * 60 ||
                                minutes(candidate.end) > 20 * 60 ||
                                minutes(candidate.end) <= minutes(candidate.start) ||
                                length(candidate) > 8 * 60) ->
                                "Rufbereitschaft: 08:00–20:00 Uhr, höchstens 8 Stunden am selben Tag."
                            kind == "Bereitschaft" && length(candidate) > 8 * 60 ->
                                "Bereitschaft darf vorläufig höchstens 8 Stunden dauern."
                            isStandby && away && accommodation !in listOf("Dienstwohnung", "Hotel") -> "Bitte Unterkunft wählen."
                            isStandby && away && accommodation == "Hotel" && hotelName.isBlank() -> "Bitte Hotelnamen angeben."
                            kind == "Urlaub" && entries.any { it.date == candidate.date && it.kind == "Urlaub" } -> "Urlaub ist für diesen Tag bereits erfasst."
                            kind != "Urlaub" && (length(candidate) <= 0 || g > length(candidate)) -> "Dauer muss positiv sein; Gastfahrt darf Dauer nicht übersteigen."
                            else -> ""
                        }
                        if (error.isEmpty() && candidate != null) {
                            entries = entries + candidate; saveEntries(context, username, entries)
                            month = YearMonth.from(LocalDate.parse(candidate.date))
                            note = ""; away = false; accommodation = ""; hotelName = ""
                        }
                    }) { LocalizedText("Eintrag speichern") }
                } }
                Card(Modifier.widthIn(max = 900.dp).fillMaxWidth()) { Column(Modifier.padding(16.dp)) {
                    LocalizedText("Erfassungen · ${selected.size}", style = MaterialTheme.typography.titleLarge)
                    val scroll = rememberScrollState()
                    Column(Modifier.horizontalScroll(scroll)) {
                        Row { listOf("Datum", "Art / Unterkunft", "Zeitraum", "Pause", "Gastfahrt", "Dauer", "").forEach {
                            LocalizedText(it, Modifier.width(if (it == "Art / Unterkunft") 220.dp else 105.dp), style = MaterialTheme.typography.labelMedium)
                        } }
                        HorizontalDivider()
                        selected.forEach { entry ->
                            Row {
                                LocalizedText(runCatching { LocalDate.parse(entry.date).format(dateFormat) }.getOrDefault(entry.date), Modifier.width(105.dp))
                                LocalizedText(if (entry.kind in listOf("Rufbereitschaft", "Bereitschaft") && entry.away)
                                    entry.kind + " · " + entry.accommodation +
                                        (if (entry.hotelName.isBlank()) "" else " · " + entry.hotelName)
                                    else entry.kind, Modifier.width(220.dp))
                                LocalizedText(if (entry.kind == "Urlaub") "Ganzer Tag" else "${entry.start}–${endAt(entry).toLocalDate()} ${entry.end}", Modifier.width(105.dp))
                                LocalizedText(if (entry.kind in listOf("Rufbereitschaft", "Bereitschaft")) "—" else "${entry.pause} min", Modifier.width(105.dp))
                                LocalizedText(if (entry.kind in listOf("Rufbereitschaft", "Bereitschaft")) "—" else "${entry.guest} min", Modifier.width(105.dp))
                                LocalizedText(if (entry.kind == "Urlaub") "1 Tag" else displayTime(length(entry)), Modifier.width(105.dp))
                                if (entry.kind in listOf("Rufbereitschaft", "Bereitschaft"))
                                    TextButton(onClick = {
                                        transitionEntry = entry; transitionDate = entry.date
                                        transitionTime = entry.start; transitionError = ""
                                    }) { LocalizedText("→ Zugfahrt") }
                                TextButton(onClick = { entries = entries.toMutableList().also { it.remove(entry) }; saveEntries(context, username, entries) }) { LocalizedText("Löschen") }
                            }
                            HorizontalDivider()
                        }
                    }
                } }
            }
        }
        Surface(color = MaterialTheme.colorScheme.primaryContainer) {
            FlowRow(Modifier.fillMaxWidth().heightIn(max = 170.dp).verticalScroll(rememberScrollState()).padding(12.dp), horizontalArrangement = Arrangement.spacedBy(20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf("Arbeitszeit" to displayTime(work), "Gastfahrt" to displayTime(guests),
                    "Urlaub" to "$holidays Tage", "Nachtstunden*" to displayTime(night),
                    "Sonntagsstunden*" to displayTime(sunday)).forEach { (label, value) ->
                    Column { LocalizedText(value, style = MaterialTheme.typography.titleLarge); LocalizedText(label) }
                }
            }
        }
    }
    transitionEntry?.let { original ->
        AlertDialog(onDismissRequest = { transitionEntry = null },
            title = { LocalizedText("In Zugfahrt übergehen") },
            text = { Column {
                LocalizedText("${original.kind}: ${original.date}, ${original.start}–${original.end}. Die Bereitschaft endet am Übergangszeitpunkt.")
                OutlinedTextField(transitionDate, { transitionDate = it }, label = { LocalizedText("Übergangsdatum (JJJJ-MM-TT)") })
                OutlinedTextField(transitionTime, { transitionTime = it }, label = { LocalizedText("Beginn Zugfahrt (HH:MM)") })
                OutlinedTextField(trainEnd, { trainEnd = it }, label = { LocalizedText("Ende Zugfahrt (HH:MM)") })
                if (transitionError.isNotBlank()) LocalizedText(transitionError, color = MaterialTheme.colorScheme.error)
            } },
            confirmButton = { Button(onClick = {
                val at = runCatching { LocalDate.parse(transitionDate).atTime(LocalTime.parse(transitionTime)) }.getOrNull()
                val finish = runCatching { LocalTime.parse(trainEnd) }.getOrNull()
                val index = entries.indexOfFirst { it === original }
                transitionError = when {
                    at == null || finish == null -> "Datum und Uhrzeiten prüfen."
                    index < 0 -> "Eintrag wurde inzwischen geändert."
                    at.isBefore(startAt(original)) || !at.isBefore(endAt(original)) ->
                        "Übergang muss zwischen Beginn (einschließlich) und Ende liegen."
                    finish == at.toLocalTime() -> "Bitte ein anderes Ende der Zugfahrt angeben."
                    else -> ""
                }
                if (transitionError.isEmpty() && at != null && finish != null && index >= 0) {
                    val shortened = original.copy(end = at.toLocalTime().toString(), endDate = at.toLocalDate().toString())
                    val trip = Entry("Zugfahrt", at.toLocalDate().toString(),
                        at.toLocalTime().toString(), finish.toString(), 0, 0,
                        "Übergang aus ${original.kind}",endDate=at.toLocalDate().plusDays(if (finish <= at.toLocalTime()) 1L else 0L).toString())
                    entries = entries.toMutableList().also {
                        if (at == startAt(original)) it.removeAt(index) else it[index] = shortened
                        it.add(trip)
                    }
                    saveEntries(context, username, entries); month = YearMonth.from(at)
                    transitionEntry = null
                }
            }) { LocalizedText("Übergang speichern") } },
            dismissButton = { TextButton(onClick = { transitionEntry = null }) { LocalizedText("Abbrechen") } })
    }
}
