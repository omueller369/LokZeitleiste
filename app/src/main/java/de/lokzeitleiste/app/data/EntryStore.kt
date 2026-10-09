package de.lokzeitleiste.app.data

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

fun loadEntries(context: Context, username: String): List<Entry> = runCatching {
    val raw = context.getSharedPreferences("entries_$username", 0).getString("data", "[]")
    val array = JSONArray(raw)
    (0 until array.length()).map { i -> array.getJSONObject(i).let {
        Entry(it.getString("kind"), it.getString("date"), it.getString("start"), it.getString("end"),
            it.getInt("pause"), it.getInt("guest"), it.optString("note"),
            it.optBoolean("away", false), it.optString("accommodation"), it.optString("hotelName"),
            it.optString("clientId").ifBlank { java.util.UUID.randomUUID().toString() },
            if (it.isNull("endDate") || !it.has("endDate")) null else it.getString("endDate"))
    } }
}.getOrDefault(emptyList())

fun saveEntries(context: Context, username: String, entries: List<Entry>) {
    val array = JSONArray()
    entries.forEach { array.put(JSONObject().put("kind", it.kind).put("date", it.date).put("start", it.start)
        .put("end", it.end).put("pause", it.pause).put("guest", it.guest).put("note", it.note)
        .put("away", it.away).put("accommodation", it.accommodation).put("hotelName", it.hotelName)
        .put("clientId", it.clientId).put("endDate", it.endDate ?: JSONObject.NULL)) }
    context.getSharedPreferences("entries_$username", 0).edit().putString("data", array.toString()).apply()
}
