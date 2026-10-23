package de.lokzeitleiste.app.portal

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest

/** App-private durable journal; fixes survive WebView suspension and process death. */
class GpsTrackStore(context: Context) {
    private val directory = File(context.filesDir, "portal-gps").apply { mkdirs() }
    private fun file(key: String): File {
        require(key.matches(Regex("[0-9]+\\.[A-Za-z0-9-]{1,100}")))
        val hash = MessageDigest.getInstance("SHA-256").digest(key.toByteArray()).joinToString("") { "%02x".format(it) }
        return File(directory, "$hash.jsonl")
    }
    fun begin(key: String, reset: Boolean) = synchronized(lock) { val f=file(key); if(reset) f.writeText(""); Unit }
    fun append(key: String, point: JSONObject) = synchronized(lock) { file(key).appendText(point.toString()+"\n") }
    fun read(key: String): JSONArray = synchronized(lock) {
        val result=JSONArray();val f=file(key)
        if(f.exists()) f.forEachLine { line -> if(line.isNotBlank()) runCatching { result.put(JSONObject(line)) } }
        result
    }
    fun erase(key: String) = synchronized(lock) { file(key).delete(); Unit }
    companion object { private val lock=Any() }
}
