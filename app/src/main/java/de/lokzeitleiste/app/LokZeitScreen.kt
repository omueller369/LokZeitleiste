package de.lokzeitleiste.app

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
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
import kotlinx.coroutines.launch
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
data class StopEntry(val station: String, val arrival: Long, val departure: Long, val reason: String, val note: String, val source: String, val ds100: String = "")

private fun loadEntries(context: Context, username: String): List<StopEntry> = runCatching {
    val array = JSONArray(context.getSharedPreferences("lokzeit_" + username, 0).getString("entries", "[]"))
    (0 until array.length()).map { i -> array.getJSONObject(i).let { StopEntry(it.getString("station"), it.getLong("arrival"), it.getLong("departure"), it.getString("reason"), it.optString("note"), it.optString("source", "Manuell"), it.optString("ds100")) } }
}.getOrDefault(emptyList())
private fun saveEntries(context: Context, username: String, entries: List<StopEntry>) {
    val data = JSONArray()
    entries.forEach { data.put(JSONObject().put("station", it.station).put("arrival", it.arrival).put("departure", it.departure).put("reason", it.reason).put("note", it.note).put("source", it.source).put("ds100", it.ds100)) }
    context.getSharedPreferences("lokzeit_" + username, 0).edit().putString("entries", data.toString()).apply()
}
private fun loadStations(context: Context, username: String): List<Station> = runCatching {
    val array = JSONArray(context.getSharedPreferences("lokzeit_" + username, 0).getString("stations", "[]"))
    (0 until array.length()).map { i -> array.getJSONObject(i).let { Station(it.getString("id"), it.getString("name"), it.getDouble("lat"), it.getDouble("lon"), it.optString("ref")) } }
}.getOrDefault(emptyList())
private fun saveStations(context: Context, username: String, stations: List<Station>) {
    val array = JSONArray()
    stations.forEach { array.put(JSONObject().put("id", it.id).put("name", it.name).put("lat", it.lat).put("lon", it.lon).put("ref", it.ref)) }
    context.getSharedPreferences("lokzeit_" + username, 0).edit().putString("stations", array.toString()).apply()
}

private fun fetchStations(lat: Double, lon: Double): List<Station> {
    // One user-initiated request for a 10 km radius; location samples never trigger network requests.
    val query = "[out:json][timeout:25];(nwr[railway~\"^(station|yard|service_station|junction|halt)$\"](around:10000,$lat,$lon););out center;"
    return fetchQuery(query)
}

private fun fetchByDs100(ref: String): List<Station> {
    require(Regex("[A-Z0-9]{2,7}").matches(ref))
    val query = "[out:json][timeout:25];nwr[\"railway:ref\"=\"$ref\"][railway](47.2,5.8,55.1,15.1);out center;"
    return fetchQuery(query)
}

private fun fetchQuery(query: String): List<Station> {
    val connection = URL("https://overpass-api.de/api/interpreter").openConnection() as HttpURLConnection
    connection.requestMethod = "POST"
    connection.connectTimeout = 15000
    connection.readTimeout = 35000
    connection.doOutput = true
    connection.setRequestProperty("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8")
    connection.setRequestProperty("User-Agent", "LokZeit/0.2 (offline station cache)")
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

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun LokZeitApp(username: String) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val prefs = remember { context.getSharedPreferences("lokzeit_" + username, 0) }
    var dutyStarted by remember { mutableStateOf(prefs.getBoolean("duty", false)) }
    var trainNumber by remember { mutableStateOf(prefs.getString("train", "") ?: "") }
    var entries by remember { mutableStateOf(loadEntries(context, username)) }
    var stations by remember { mutableStateOf(loadStations(context, username)) }
    var currentLocation by remember { mutableStateOf<Location?>(null) }
    var gpsEnabled by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf("GPS ist ausgeschaltet") }
    var station by remember { mutableStateOf("") }
    var ds100 by remember { mutableStateOf("") }
    var candidateId by remember { mutableStateOf<String?>(null) }
    var currentStopId by remember { mutableStateOf<String?>(null) }
    var candidateSince by remember { mutableLongStateOf(0L) }
    var outsideSince by remember { mutableLongStateOf(0L) }
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
                locationManager.requestLocationUpdates(LocationManager.GPS_PROVIDER, 5000L, 15f, listener)
                locationManager.requestLocationUpdates(LocationManager.NETWORK_PROVIDER, 5000L, 15f, listener)
            }.onFailure { message = "GPS nicht verfügbar: ${it.message}" }
        }
        onDispose { locationManager.removeUpdates(listener) }
    }
    // Conservative point proximity: require two minutes within 300 m and two minutes beyond 600 m.
    // OSM points do not describe signal boundaries; a driver must review the result.
    LaunchedEffect(currentLocation, stations, dutyStarted) {
        val fix = currentLocation ?: return@LaunchedEffect
        if (!dutyStarted || fix.accuracy > 100f || fix.time < System.currentTimeMillis() - 120000) return@LaunchedEffect
        val timestamp = fix.time
        val nearest = stations.map { s ->
            val result = FloatArray(1)
            Location.distanceBetween(fix.latitude, fix.longitude, s.lat, s.lon, result)
            s to result[0]
        }.minByOrNull { it.second }
        if (arrival == null) {
            val nearby = nearest?.takeIf { it.second <= 300f }?.first
            if (nearby == null) { candidateId = null; candidateSince = 0L }
            else if (candidateId != nearby.id) { candidateId = nearby.id; candidateSince = timestamp }
            else if (timestamp - candidateSince >= 120000) {
                station = nearby.name; ds100 = nearby.ref; currentStopId = nearby.id; arrival = candidateSince
                departure = null; source = "GPS/OSM – prüfen"; reason = ""; note = ""
                candidateId = null; message = "${nearby.name} erkannt – Zeiten bitte prüfen"
            }
        } else if (departure == null && source.startsWith("GPS")) {
            val selected = stations.firstOrNull { it.id == currentStopId } ?: return@LaunchedEffect
            val distance = FloatArray(1)
            Location.distanceBetween(fix.latitude, fix.longitude, selected.lat, selected.lon, distance)
            if (distance[0] <= 600f) outsideSince = 0L
            else if (outsideSince == 0L) outsideSince = timestamp
            else if (timestamp - outsideSince >= 120000) {
                departure = outsideSince; outsideSince = 0L
                message = "Abfahrt erkannt – bitte kontrollieren und speichern"
            }
        }
    }
    val elapsed = arrival?.let { duration(it, departure ?: now) } ?: 0L
    LaunchedEffect(elapsed, reason) { if (elapsed < MIN_PAUSE && reason == "Pause") reason = "" }
    fun persist(newEntries: List<StopEntry>) { entries = newEntries; saveEntries(context, username, newEntries) }
    fun reset() { arrival = null; departure = null; station = ""; ds100 = ""; currentStopId = null; reason = ""; note = ""; source = "Manuell" }

    Scaffold(topBar = { TopAppBar(title = { Text("Zugfahrt · LokZeit") }) }) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item {
                Text("Dienst und Zug", style = MaterialTheme.typography.titleLarge)
                Button(onClick = {
                    dutyStarted = !dutyStarted; prefs.edit().putBoolean("duty", dutyStarted).apply()
                    if (!dutyStarted) { gpsEnabled = false; message = "Dienst beendet" }
                }) { Text(if (dutyStarted) "Dienst beenden" else "Dienst starten") }
                OutlinedTextField(trainNumber, { trainNumber = it; prefs.edit().putString("train", it).apply() }, label = { Text("Zugnummer") }, modifier = Modifier.fillMaxWidth())
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(enabled = dutyStarted, onClick = {
                        if (context.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED && context.checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) != PackageManager.PERMISSION_GRANTED)
                            permission.launch(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION))
                        else gpsEnabled = !gpsEnabled
                    }) { Text(if (gpsEnabled) "GPS stoppen" else "GPS starten") }
                    Button(enabled = currentLocation != null, onClick = {
                        val fix = currentLocation ?: return@Button
                        scope.launch {
                            message = "OSM-Betriebsstellen werden geladen …"
                            runCatching { withContext(Dispatchers.IO) { fetchStations(fix.latitude, fix.longitude) } }
                                .onSuccess { fetched ->
                                    stations = (stations + fetched).distinctBy { it.id }
                                    saveStations(context, username, stations)
                                    message = "${fetched.size} Betriebsstellen geladen; lokal gespeichert"
                                }.onFailure { message = "Abruf fehlgeschlagen: ${it.message}" }
                        }
                    }) { Text("OSM laden") }
                }
                Text(message, style = MaterialTheme.typography.bodySmall)
                Text("${stations.size} Betriebsstellen gespeichert. GPS nur bei geöffnetem Bildschirm und laufendem Dienst. OSM laden jeweils für die aktuelle Umgebung (10 km).", style = MaterialTheme.typography.bodySmall)
            }
            item {
                Text("Aktueller Aufenthalt", style = MaterialTheme.typography.titleLarge)
                OutlinedTextField(station, { station = it; source = "Manuell korrigiert" }, label = { Text("Betriebsstelle (editierbar)") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(ds100, { ds100 = it.uppercase().trim() }, label = { Text("DS100-Kürzel") }, modifier = Modifier.fillMaxWidth())
                Button(enabled = Regex("[A-Z0-9]{2,7}").matches(ds100), onClick = {
                    val code = ds100
                    val cached = stations.firstOrNull { it.ref.equals(code, ignoreCase = true) }
                    if (cached != null) { station = cached.name; ds100 = cached.ref; source = "DS100/OSM – prüfen"; message = "$code: ${cached.name} gefunden" }
                    else scope.launch {
                        message = "DS100 $code wird gesucht …"
                        runCatching { withContext(Dispatchers.IO) { fetchByDs100(code) } }
                            .onSuccess { results ->
                                val match = results.firstOrNull { it.ref.equals(code, ignoreCase = true) }
                                if (match == null) message = "DS100 $code in OSM nicht gefunden – Betriebsstelle manuell eintragen"
                                else {
                                    stations = (stations + results).distinctBy { it.id }; saveStations(context, username, stations)
                                    station = match.name; ds100 = match.ref; source = "DS100/OSM – prüfen"; message = "$code: ${match.name} gefunden"
                                }
                            }.onFailure { message = "DS100-Abfrage fehlgeschlagen: ${it.message}" }
                    }
                }) { Text("DS100 suchen") }
                Text("Ankunft: ${arrival?.let(::stamp) ?: "–"}   Abfahrt: ${departure?.let(::stamp) ?: "–"}")
                Text("Standzeit: ${elapsed.clock()} · $source")
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(enabled = arrival == null, onClick = { arrival = System.currentTimeMillis(); departure = null; source = "Manuell" }) { Text("Ankunft") }
                    Button(enabled = arrival != null && departure == null, onClick = { departure = System.currentTimeMillis() }) { Text("Abfahrt") }
                    if (arrival != null) TextButton(onClick = { reset() }) { Text("Verwerfen") }
                }
                Text("Erkannte Zeiten können nach dem Speichern bearbeitet werden.")
            }
            item {
                StopReasonDropdown(reason, elapsed, onSelect = { reason = it })
                OutlinedTextField(note, { note = it }, label = { Text("Notiz (optional)") }, modifier = Modifier.fillMaxWidth())
                Button(enabled = arrival != null && departure != null && station.isNotBlank() && validReason(reason, elapsed), onClick = {
                    persist(listOf(StopEntry(station.trim(), arrival!!, departure!!, reason, note.trim(), source, ds100)) + entries)
                    reset()
                }, modifier = Modifier.fillMaxWidth()) { Text("Standzeit speichern") }
            }
            item { Text("Standzeiten – Zug ${trainNumber.ifBlank { "–" }}", style = MaterialTheme.typography.titleLarge) }
            itemsIndexed(entries) { index, entry ->
                Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(12.dp)) {
                    Text(entry.station, style = MaterialTheme.typography.titleMedium)
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
        }, onDelete = { persist(entries.toMutableList().also { it.removeAt(index) }); editing = null })
    } }
}

@Composable
private fun EditStopDialog(entry: StopEntry, onDismiss: () -> Unit, onSave: (StopEntry) -> Unit, onDelete: () -> Unit) {
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
        TextButton(enabled = name.isNotBlank() && start != null && end != null && end >= start && validReason(reason, seconds), onClick = {
            onSave(StopEntry(name.trim(), start!!, end!!, reason, note.trim(), "Manuell korrigiert", code))
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
