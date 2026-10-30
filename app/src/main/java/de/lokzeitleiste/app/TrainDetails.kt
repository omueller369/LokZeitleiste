package de.lokzeitleiste.app

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import de.lokzeitleiste.app.data.*
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private val stopTimeFormat = DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm:ss").withZone(ZoneId.systemDefault())

@Composable
fun TransferStopsDialog(username: String, selected: List<StopEntry>, onDismiss: () -> Unit, onTransferred: () -> Unit) {
    val context = LocalContext.current
    val trips = remember(username) { loadEntries(context, username).filter { it.kind == "Zugfahrt" }.sortedByDescending { it.date + it.start } }
    var targetId by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf("") }
    AlertDialog(onDismissRequest = onDismiss, title = { Text("In Zugfahrtdetails übernehmen") }, text = {
        Column(Modifier.heightIn(max = 440.dp).verticalScroll(rememberScrollState())) {
            Text("${selected.size} Standzeiten ausgewählt. Ziel-Zugfahrt auswählen:")
            if (trips.isEmpty()) Text("Bitte zuerst eine Zugfahrt in der Monatsübersicht anlegen. Die Standzeiten bleiben erhalten.")
            trips.forEach { trip ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    RadioButton(selected = targetId == trip.clientId, onClick = { targetId = trip.clientId })
                    Text("${trip.date} · ${trip.start}–${trip.end}" + if (trip.note.isBlank()) "" else " · ${trip.note}")
                }
            }
            if (error.isNotBlank()) Text(error, color = MaterialTheme.colorScheme.error)
        }
    }, confirmButton = {
        Button(enabled = targetId != null && selected.isNotEmpty(), onClick = {
            // Read the latest full list so unrelated records are never overwritten by a stale UI snapshot.
            val all = loadEntries(context, username)
            val target = all.firstOrNull { it.clientId == targetId && it.kind == "Zugfahrt" }
            if (target == null) error = "Zugfahrt nicht mehr vorhanden. Bitte erneut öffnen."
            else {
                val from = startAt(target).atZone(ZoneId.systemDefault()).toInstant().toEpochMilli()
                val until = endAt(target).atZone(ZoneId.systemDefault()).toInstant().toEpochMilli()
                if (selected.any { it.arrival < from || it.departure > until || it.departure < it.arrival })
                    error = "Die ausgewählten Standzeiten müssen im Zeitraum der Ziel-Zugfahrt liegen. Bitte Auswahl oder Zeiten prüfen."
                else {
                    saveEntries(context, username, all.map { trip ->
                        if (trip.clientId == targetId) trip.copy(stops = mergeStops(trip.stops, selected)) else trip
                    })
                    onTransferred()
                }
            }
        }) { Text("Übernehmen") }
    }, dismissButton = { TextButton(onClick = onDismiss) { Text("Abbrechen") } })
}

@Composable
fun TrainDetailsDialog(trip: Entry, onDismiss: () -> Unit, onSave: (Entry) -> Unit) {
    var editingId by remember { mutableStateOf<String?>(null) }
    AlertDialog(onDismissRequest = onDismiss, title = { Text("Details zur Zugfahrt") }, text = {
        Column(Modifier.heightIn(max = 480.dp).verticalScroll(rememberScrollState())) {
            Text("${trip.date} · ${trip.start}–${trip.end}")
            if (trip.note.isNotBlank()) Text(trip.note)
            if (trip.stops.isEmpty()) Text("Noch keine Standzeiten übernommen. In der GPS-Aufzeichnung Einträge auswählen und „Übernehmen“ drücken.")
            trip.stops.sortedBy { it.arrival }.forEach { stop ->
                HorizontalDivider()
                Text("${stop.ds100.ifBlank { "DS100 ergänzen" }} · ${stop.station.ifBlank { "Bahnhofsname ergänzen" }}")
                Text("${stopTimeFormat.format(Instant.ofEpochMilli(stop.arrival))} – ${stopTimeFormat.format(Instant.ofEpochMilli(stop.departure))}")
                Text("${stop.reason}${if (stop.note.isBlank()) "" else " · ${stop.note}"}")
                TextButton(onClick = { editingId = stop.id }) { Text("Standort / Zeiten bearbeiten") }
            }
        }
    }, confirmButton = { TextButton(onClick = onDismiss) { Text("Schließen") } })
    trip.stops.firstOrNull { it.id == editingId }?.let { stop ->
        EditStopDialog(stop, onDismiss = { editingId = null }, onSave = { updated ->
            onSave(trip.copy(stops = mergeStops(trip.stops, listOf(updated)))); editingId = null
        }, onDelete = {
            onSave(trip.copy(stops = trip.stops.filterNot { it.id == stop.id })); editingId = null
        })
    }
}
