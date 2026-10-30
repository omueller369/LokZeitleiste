package de.lokzeitleiste.app

import de.lokzeitleiste.app.data.*
import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private const val MIN_PAUSE = 900L
private val STOP_REASONS = listOf("Zugfolge", "Warten auf Fahrplan", "Störung auf der Strecke", "Umleitung", "Fahrt im Blockabstand", "Pause")
private fun validReason(reason: String, seconds: Long) = reason in STOP_REASONS && (reason != "Pause" || seconds >= MIN_PAUSE)
private val fmt = DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm:ss").withZone(ZoneId.systemDefault())
private fun stamp(value: Long) = fmt.format(Instant.ofEpochMilli(value))
private fun duration(a: Long, b: Long) = ((b - a) / 1000).coerceAtLeast(0)
private fun Long.clock() = "%02d:%02d:%02d".format(this / 3600, (this % 3600) / 60, this % 60)

data class Station(val id: String, val name: String, val lat: Double, val lon: Double, val ref: String = "")

private fun loadEntries(context: Context, username: String): List<StopEntry> = runCatching {
    val array = JSONArray(context.getSharedPreferences("lokzeit_" + username, 0).getString("entries", "[]"))
    stopsFromJson(array)
}.getOrDefault(emptyList())
private fun saveEntries(context: Context, username: String, entries: List<StopEntry>) {
    val data = stopsToJson(entries)
    context.getSharedPreferences("lokzeit_" + username, 0).edit().putString("entries", data.toString()).apply()
}
private fun fetchPlaces(lat: Double, lon: Double): List<Station> {
    val query = "[out:json][timeout:25];nwr[place~\"^(city|town|village|hamlet|suburb|quarter)$\"](around:5000,$lat,$lon);out center;"
    return fetchQuery(query).filter { place -> distanceMeters(lat, lon, place.lat, place.lon) <= 5000f }
}

private fun distanceMeters(lat: Double, lon: Double, otherLat: Double, otherLon: Double): Float {
    val result = FloatArray(1)
    Location.distanceBetween(lat, lon, otherLat, otherLon, result)
    return result[0]
}

private fun fetchQuery(query: String): List<Station> {
    val connection = URL("https://overpass-api.de/api/interpreter").openConnection() as HttpURLConnection
    connection.requestMethod = "POST"
    connection.connectTimeout = 15000
    connection.readTimeout = 35000
    connection.doOutput = true
    connection.setRequestProperty("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8")
    connection.setRequestProperty("User-Agent", "LokZeitleiste (place lookup)")
    try {
        connection.outputStream.use { it.write("data=${java.net.URLEncoder.encode(query, "UTF-8")}".toByteArray()) }
        if (connection.responseCode !in 200..299) error("OSM-Datenserver: HTTP ${connection.responseCode}")
        val elements = JSONObject(connection.inputStream.bufferedReader().use { it.readText() }).getJSONArray("elements")
        return (0 until elements.length()).mapNotNull { i ->
            val e = elements.getJSONObject(i)
            val tags = e.optJSONObject("tags") ?: return@mapNotNull null
            val name = tags.optString("name").ifBlank { tags.optString("railway:ref") }
            val center = e.optJSONObject("center") ?: e
            if (name.isBlank() || !center.has("lat") || !center.has("lon")) null
            else Station("${e.getString("type")}/${e.getLong("id")}", name, center.getDouble("lat"), center.getDouble("lon"), tags.optString("railway:ref"))
        }.distinctBy { it.id }
    } finally { connection.disconnect() }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LokZeitApp(username: String) {
    val context = LocalContext.current
    val prefs = remember { context.getSharedPreferences("lokzeit_" + username, 0) }
    var dutyStarted by remember { mutableStateOf(prefs.getBoolean("duty", false)) }
    var trainNumber by remember { mutableStateOf(prefs.getString("train", "") ?: "") }
    var entries by remember { mutableStateOf(loadEntries(context, username)) }
    var currentLocation by remember { mutableStateOf<Location?>(null) }
    var gpsEnabled by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf("GPS ist ausgeschaltet") }
    var station by remember { mutableStateOf("") }
    var ds100 by remember { mutableStateOf("") }
    val detector = remember { GpsStopDetector() }
    var gpsTrackingStop by remember { mutableStateOf(false) }
    var stopLocation by remember { mutableStateOf<Location?>(null) }
    var suggestions by remember { mutableStateOf(emptyList<Ds100Station>()) }
    var selectedIds by remember { mutableStateOf(emptySet<String>()) }
    var transferOpen by remember { mutableStateOf(false) }
    var lookupVersion by remember { mutableIntStateOf(0) }
    var lookupBusy by remember { mutableStateOf(false) }
    var directory by remember { mutableStateOf(emptyList<Ds100Station>()) }
    LaunchedEffect(username) {
        directory = withContext(Dispatchers.IO) {
            context.assets.open("ds100.tsv").bufferedReader().useLines { lines ->
                lines.mapNotNull { line -> line.split('\t', limit = 2).takeIf { it.size == 2 }
                    ?.let { Ds100Station(it[0], it[1]) } }.toList()
            }
        }
    }
    var arrival by remember { mutableStateOf<Long?>(null) }
    var departure by remember { mutableStateOf<Long?>(null) }
    var source by remember { mutableStateOf("Manuell") }
    var reason by remember { mutableStateOf("") }
    var note by remember { mutableStateOf("") }
    var editing by remember { mutableStateOf<Int?>(null) }
    var now by remember { mutableLongStateOf(System.currentTimeMillis()) }
    LaunchedEffect(Unit) { while (true) { now = System.currentTimeMillis(); delay(1000) } }
    val locationManager = remember { context.getSystemService(Context.LOCATION_SERVICE) as LocationManager }
    val listener = remember { LocationListener { fix -> currentLocation = fix } }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
        gpsEnabled = result.values.any { it }
        if (!gpsEnabled) message = "Standortberechtigung fehlt"
    }
    DisposableEffect(gpsEnabled, dutyStarted) {
        if (gpsEnabled && dutyStarted && (context.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED || context.checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED)) {
            runCatching {
                locationManager.requestLocationUpdates(LocationManager.GPS_PROVIDER, 5000L, 0f, listener)
                locationManager.requestLocationUpdates(LocationManager.NETWORK_PROVIDER, 5000L, 0f, listener)
            }.onFailure { message = "GPS nicht verfügbar: ${it.message}" }
        }
        onDispose { locationManager.removeUpdates(listener) }
    }
    LaunchedEffect(gpsEnabled, dutyStarted) { detector.reset() }
    LaunchedEffect(currentLocation, dutyStarted, gpsEnabled) {
        val fix = currentLocation ?: return@LaunchedEffect
        if (!gpsEnabled || !dutyStarted || fix.accuracy > 50f ||
            fix.time < System.currentTimeMillis() - 120000L) return@LaunchedEffect
        if (arrival != null && !gpsTrackingStop) return@LaunchedEffect
        if (departure != null) return@LaunchedEffect
        val event = detector.sample(fix.time, fix.latitude, fix.longitude,
            if (fix.hasSpeed()) fix.speed else null, ::distanceMeters) ?: return@LaunchedEffect
        if (event.departure == null && arrival == null) {
            arrival = event.arrival; departure = null; gpsTrackingStop = true
            stopLocation = Location(fix); source = "GPS – prüfen"
            station = ""; ds100 = ""; reason = ""; note = ""; suggestions = emptyList()
            message = "Stillstand erkannt – Standort kann ergänzt werden"
            lookupVersion++
        } else if (gpsTrackingStop && event.departure != null) {
            departure = event.departure; gpsTrackingStop = false
            message = "Abfahrt erkannt – Standzeit bitte prüfen und speichern"
        }
    }
    // A separate effect keeps slow name resolution from cancelling time detection.
    LaunchedEffect(lookupVersion, directory) {
        if (lookupVersion == 0 || directory.isEmpty()) return@LaunchedEffect
        val fix = stopLocation ?: currentLocation ?: return@LaunchedEffect
        val startedFor = arrival
        val originalName = station
        val originalCode = ds100
        lookupBusy = true
        try {
            val names = withContext(Dispatchers.IO) { fetchPlaces(fix.latitude, fix.longitude).map { it.name } }
            val matches = matchPlaces(names, directory)
            if (arrival == startedFor && station == originalName && ds100 == originalCode) {
                suggestions = matches
                message = if (matches.isEmpty()) "Kein DS100-Treffer zum Ort – nur Zeiten erfasst; Standort manuell ergänzen"
                    else "${matches.size} DS100-Vorschläge zu Orten im 5-km-Umkreis – bitte auswählen"
            }
        } catch (cancelled: kotlinx.coroutines.CancellationException) { throw cancelled }
        catch (error: Exception) {
            message = "Ortssuche fehlgeschlagen – Zeiten bleiben erhalten; Standort manuell ergänzen"
        } finally { lookupBusy = false }
    }
    val elapsed = arrival?.let { duration(it, departure ?: now) } ?: 0L
    LaunchedEffect(elapsed, reason) { if (elapsed < MIN_PAUSE && reason == "Pause") reason = "" }
    fun persist(newEntries: List<StopEntry>) { entries = newEntries; saveEntries(context, username, newEntries) }
    fun reset() { lookupVersion = 0; arrival = null; departure = null; station = ""; ds100 = ""; gpsTrackingStop = false; stopLocation = null; suggestions = emptyList(); detector.reset(); reason = ""; note = ""; source = "Manuell" }

    Scaffold(topBar = { TopAppBar(title = { Text("Zugfahrt · LokZeit") }) }) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item {
                Text("Dienst und Zug", style = MaterialTheme.typography.titleLarge)
                Button(onClick = {
                    dutyStarted = !dutyStarted; prefs.edit().putBoolean("duty", dutyStarted).apply()
                    if (!dutyStarted) { gpsEnabled = false; gpsTrackingStop = false; message = "Dienst beendet" }
                }) { Text(if (dutyStarted) "Dienst beenden" else "Dienst starten") }
                OutlinedTextField(trainNumber, { trainNumber = it; prefs.edit().putString("train", it).apply() }, label = { Text("Zugnummer") }, modifier = Modifier.fillMaxWidth())
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(enabled = dutyStarted, onClick = {
                        if (context.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED && context.checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) != PackageManager.PERMISSION_GRANTED)
                            permission.launch(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION))
                        else { gpsEnabled = !gpsEnabled; if (!gpsEnabled) gpsTrackingStop = false }
                    }) { Text(if (gpsEnabled) "GPS stoppen" else "GPS starten") }
                    Button(enabled = currentLocation != null && !lookupBusy && directory.isNotEmpty(), onClick = {
                        if (arrival == null) stopLocation = null
                        lookupVersion++
                    }) { Text(if (lookupBusy) "Suche …" else "Ort / DS100 suchen") }
                }
                Text(message, style = MaterialTheme.typography.bodySmall)
                Text("GPS erfasst Stillstände unabhängig vom Standort. Ortssuche: 5 km. Nur bei geöffnetem Bildschirm und laufendem Dienst.", style = MaterialTheme.typography.bodySmall)
                Text("DS100-Verzeichnis: DB AG, Stand 04/2018 (CC BY 4.0). Vorschläge bitte prüfen.", style = MaterialTheme.typography.bodySmall)
            }
            item {
                Text("Aktueller Aufenthalt", style = MaterialTheme.typography.titleLarge)
                suggestions.forEach { suggestion ->
                    TextButton(onClick = {
                        station = suggestion.name; ds100 = suggestion.code; suggestions = emptyList()
                    }) { Text("${suggestion.code} · ${suggestion.name}") }
                }
                OutlinedTextField(station, { station = it; source = "Manuell korrigiert" }, label = { Text("Bahnhofsname (manuell ergänzbar)") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(ds100, { ds100 = it.uppercase().trim() }, label = { Text("DS100-Kürzel") }, modifier = Modifier.fillMaxWidth())
                Button(enabled = ds100.isNotBlank() && directory.isNotEmpty(), onClick = {
                    val matches = directory.filter { it.code.replace(" ", "").equals(ds100.replace(" ", ""), ignoreCase = true) }
                    suggestions = matches
                    message = if (matches.isEmpty()) "DS100 nicht gefunden – Bahnhofsname manuell ergänzen"
                        else "DS100 gefunden – Vorschlag bitte auswählen"
                }) { Text("DS100 suchen") }
                Text("Ankunft: ${arrival?.let(::stamp) ?: "–"}   Abfahrt: ${departure?.let(::stamp) ?: "–"}")
                Text("Standzeit: ${elapsed.clock()} · $source")
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(enabled = arrival == null, onClick = { arrival = System.currentTimeMillis(); departure = null; source = "Manuell" }) { Text("Ankunft") }
                    Button(enabled = arrival != null && departure == null, onClick = { departure = System.currentTimeMillis(); gpsTrackingStop = false }) { Text("Abfahrt") }
                    if (arrival != null) TextButton(onClick = { reset() }) { Text("Verwerfen") }
                }
                Text("Erkannte Zeiten können nach dem Speichern bearbeitet werden.")
            }
            item {
                StopReasonDropdown(reason, elapsed, onSelect = { reason = it })
                OutlinedTextField(note, { note = it }, label = { Text("Notiz (optional)") }, modifier = Modifier.fillMaxWidth())
                Button(enabled = arrival != null && departure != null && validReason(reason, elapsed), onClick = {
                    persist(listOf(StopEntry(station.trim(), arrival!!, departure!!, reason, note.trim(), source, ds100)) + entries)
                    reset()
                }, modifier = Modifier.fillMaxWidth()) { Text("Standzeit speichern") }
            }
            item {
                Text("Standzeiten – Zug ${trainNumber.ifBlank { "–" }}", style = MaterialTheme.typography.titleLarge)
                Button(enabled = selectedIds.isNotEmpty(), onClick = { transferOpen = true }) {
                    Text("Übernehmen (${selectedIds.size})")
                }
            }
            itemsIndexed(entries) { index, entry ->
                Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(12.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked = entry.id in selectedIds, onCheckedChange = { checked ->
                            selectedIds = if (checked) selectedIds + entry.id else selectedIds - entry.id
                        })
                        Text(entry.station.ifBlank { "Standort ergänzen" }, style = MaterialTheme.typography.titleMedium)
                    }
                    Text("${stamp(entry.arrival)} – ${stamp(entry.departure)}")
                    Text("${duration(entry.arrival, entry.departure).clock()} · ${entry.reason}${if (entry.note.isBlank()) "" else " – ${entry.note}"}")
                    Text("${entry.source}${if (entry.ds100.isBlank()) "" else " · DS100 ${entry.ds100}"}", style = MaterialTheme.typography.bodySmall)
                    TextButton(onClick = { editing = index }) { Text("Betriebsstelle / Zeiten bearbeiten") }
                } }
            }
        }
    }
    editing?.let { index -> entries.getOrNull(index)?.let { entry ->
        EditStopDialog(entry, onDismiss = { editing = null }, onSave = { updated ->
            persist(entries.toMutableList().also { it[index] = updated }); editing = null
        }, onDelete = { selectedIds = selectedIds - entry.id; persist(entries.toMutableList().also { it.removeAt(index) }); editing = null })
    } }
    if (transferOpen) TransferStopsDialog(username, entries.filter { it.id in selectedIds },
        onDismiss = { transferOpen = false }, onTransferred = {
            selectedIds = emptySet(); transferOpen = false
            message = "Ausgewählte Standzeiten in die Details der Zugfahrt übernommen"
        })

}

@Composable
internal fun EditStopDialog(entry: StopEntry, onDismiss: () -> Unit, onSave: (StopEntry) -> Unit, onDelete: () -> Unit) {
    var name by remember(entry) { mutableStateOf(entry.station) }
    var code by remember(entry) { mutableStateOf(entry.ds100) }
    var arrival by remember(entry) { mutableStateOf(stamp(entry.arrival)) }
    var departure by remember(entry) { mutableStateOf(stamp(entry.departure)) }
    var reason by remember(entry) { mutableStateOf(entry.reason) }
    var note by remember(entry) { mutableStateOf(entry.note) }
    val start = runCatching { java.time.LocalDateTime.parse(arrival, DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm:ss")).atZone(ZoneId.systemDefault()).toInstant().toEpochMilli() }.getOrNull()
    val end = runCatching { java.time.LocalDateTime.parse(departure, DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm:ss")).atZone(ZoneId.systemDefault()).toInstant().toEpochMilli() }.getOrNull()
    val seconds = if (start != null && end != null && end >= start) duration(start, end) else 0L
    AlertDialog(onDismissRequest = onDismiss, title = { Text("Standzeit korrigieren") }, text = {
        Column(Modifier.heightIn(max = 510.dp).verticalScroll(rememberScrollState())) {
            OutlinedTextField(name, { name = it }, label = { Text("Betriebsstelle") })
            OutlinedTextField(code, { code = it.uppercase().trim() }, label = { Text("DS100-Kürzel (optional)") })
            OutlinedTextField(arrival, { arrival = it }, label = { Text("Ankunft: TT.MM.JJJJ HH:mm:ss") })
            OutlinedTextField(departure, { departure = it }, label = { Text("Abfahrt: TT.MM.JJJJ HH:mm:ss") })
            Text("Dauer: ${seconds.clock()}")
            StopReasonDropdown(reason, seconds, onSelect = { reason = it })
            OutlinedTextField(note, { note = it }, label = { Text("Notiz (optional)") })
            TextButton(onClick = onDelete) { Text("Falschen Eintrag löschen") }
        }
    }, confirmButton = {
        TextButton(enabled = start != null && end != null && end >= start && validReason(reason, seconds), onClick = {
            onSave(entry.copy(station = name.trim(), arrival = start!!, departure = end!!, reason = reason, note = note.trim(), source = "Manuell korrigiert", ds100 = code))
        }) { Text("Speichern") }
    }, dismissButton = { TextButton(onClick = onDismiss) { Text("Abbrechen") } })
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun StopReasonDropdown(value: String, seconds: Long, onSelect: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
        OutlinedTextField(
            value = value,
            onValueChange = {},
            readOnly = true,
            label = { Text("Grund der Standzeit") },
            placeholder = { Text("Bitte auswählen") },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            modifier = Modifier.menuAnchor().fillMaxWidth()
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            STOP_REASONS.forEach { option ->
                val available = option != "Pause" || seconds >= MIN_PAUSE
                DropdownMenuItem(
                    text = { Text(if (option == "Pause" && !available) "Pause (ab 15:00 min)" else option) },
                    enabled = available,
                    onClick = { onSelect(option); expanded = false }
                )
            }
        }
    }
}
