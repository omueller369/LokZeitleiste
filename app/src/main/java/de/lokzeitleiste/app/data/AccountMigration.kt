package de.lokzeitleiste.app.data

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/** Preserve local records when a verified account is assigned a TF number. */
fun migrateAccountData(context: Context, previous: String?, current: String) {
    if (previous.isNullOrBlank() || previous == current) return
    for ((prefix, keys) in listOf("entries_" to listOf("data"), "lokzeit_" to listOf("entries", "stations"))) {
        val old = context.getSharedPreferences(prefix + previous, 0)
        val target = context.getSharedPreferences(prefix + current, 0)
        for (key in keys) {
            val source = old.getString(key, null) ?: continue
            val marker = "migrated.$previous.$key"
            if (target.getBoolean(marker, false)) continue
            val combined = linkedMapOf<String, JSONObject>()
            for (raw in listOf(source, target.getString(key, "[]") ?: "[]")) {
                val array = runCatching { JSONArray(raw) }.getOrNull() ?: continue
                for (index in 0 until array.length()) {
                    val item = array.optJSONObject(index) ?: continue
                    val identity = item.optString("clientId").ifBlank { item.optString("id").ifBlank { item.toString() } }
                    combined[identity] = item
                }
            }
            target.edit().putString(key, JSONArray(combined.values.toList()).toString()).putBoolean(marker, true).commit()
        }
    }
}
