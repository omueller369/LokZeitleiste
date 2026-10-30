package de.lokzeitleiste.app.data

import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

data class StopEntry(
    val station: String, val arrival: Long, val departure: Long, val reason: String,
    val note: String, val source: String, val ds100: String = "",
    val id: String = UUID.randomUUID().toString()
)

fun stopsFromJson(array: JSONArray): List<StopEntry> = (0 until array.length()).map { i ->
    val item = array.getJSONObject(i)
    StopEntry(item.getString("station"), item.getLong("arrival"), item.getLong("departure"),
        item.getString("reason"), item.optString("note"), item.optString("source", "Manuell"),
        item.optString("ds100"), item.optString("id").ifBlank {
            UUID.nameUUIDFromBytes("$i:$item".toByteArray(Charsets.UTF_8)).toString()
        })
}

fun stopsToJson(stops: List<StopEntry>): JSONArray = JSONArray().also { array ->
    stops.forEach { array.put(JSONObject().put("id", it.id).put("station", it.station)
        .put("arrival", it.arrival).put("departure", it.departure).put("reason", it.reason)
        .put("note", it.note).put("source", it.source).put("ds100", it.ds100)) }
}

// Repeat transfers update the same stop, without dropping existing trip details.
fun mergeStops(existing: List<StopEntry>, selected: List<StopEntry>): List<StopEntry> =
    (existing.filter { old -> selected.none { it.id == old.id } } + selected).sortedBy { it.arrival }
