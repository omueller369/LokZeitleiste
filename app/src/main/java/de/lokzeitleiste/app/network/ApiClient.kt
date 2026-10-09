package de.lokzeitleiste.app.network

import de.lokzeitleiste.app.BuildConfig
import de.lokzeitleiste.app.data.Entry
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.time.YearMonth

object ApiClient {
    private fun base(): String = BuildConfig.API_BASE_URL.trimEnd('/').also {
        val uri = runCatching { URI(it) }.getOrNull()
        val localEmulator = BuildConfig.DEBUG && uri?.scheme == "http" &&
            uri.host == "10.0.2.2" && uri.port == 8080 && uri.rawUserInfo == null
        require((uri?.scheme == "https" && uri.host != null) || localEmulator) {
            "Serveradresse fehlt: HTTPS oder im Debug-Emulator http://10.0.2.2:8080 konfigurieren."
        }
    }
    private fun post(path: String, body: JSONObject, token: String? = null): JSONObject {
        val connection = URL(base() + path).openConnection() as HttpURLConnection
        connection.requestMethod = "POST"
        connection.connectTimeout = 15000
        connection.readTimeout = 30000
        connection.doOutput = true
        connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
        if (token != null) connection.setRequestProperty("Authorization", "Bearer $token")
        try {
            connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            val stream = if (connection.responseCode in 200..299) connection.inputStream else connection.errorStream
            val content = stream?.bufferedReader()?.use { it.readText() } ?: ""
            if (connection.responseCode !in 200..299)
                error(if (connection.responseCode == 401) "Anmeldung abgelaufen. Bitte erneut anmelden."
                      else "Serverfehler ${connection.responseCode}: $content")
            return JSONObject(content)
        } finally { connection.disconnect() }
    }
    data class LoginResult(val username: String, val token: String, val passwordChangeRequired: Boolean)
    suspend fun login(username: String, password: String): LoginResult = withContext(Dispatchers.IO) {
        val reply = post("/api/v1/tf/login", JSONObject().put("username", username).put("password", password))
        LoginResult(reply.getString("username"), reply.getString("access_token"), reply.optBoolean("password_change_required"))
    }
    suspend fun changePassword(username: String, token: String, current: String, new: String, confirm: String): LoginResult {
        withContext(Dispatchers.IO) {
            post("/api/v1/account/password", JSONObject().put("current_password", current)
                .put("new_password", new).put("confirm_password", confirm), token)
        }
        return login(username, new)
    }
    suspend fun logout(token: String) = withContext(Dispatchers.IO) {
        post("/api/v1/tf/logout", JSONObject(), token)
        Unit
    }
    data class UploadResult(val accepted: Int, val emailQueued: Boolean)
    suspend fun upload(month: YearMonth, entries: List<Entry>, token: String): UploadResult = withContext(Dispatchers.IO) {
        val items = JSONArray()
        entries.forEach { items.put(JSONObject()
            .put("client_id", it.clientId).put("kind", it.kind).put("date", it.date)
            .put("start", it.start).put("end", it.end).put("pause", it.pause)
            .put("guest", it.guest).put("note", it.note).put("away", it.away)
            .put("accommodation", it.accommodation).put("hotel_name", it.hotelName)) }
        val reply = post("/api/v1/me/months/${month.year}/${month.monthValue}/entries",
            JSONObject().put("entries", items), token)
        UploadResult(reply.getInt("accepted"), reply.optString("email_status") == "queued")
    }
}
