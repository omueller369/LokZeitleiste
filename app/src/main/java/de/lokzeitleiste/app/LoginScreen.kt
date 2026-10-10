package de.lokzeitleiste.app

import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import de.lokzeitleiste.app.network.ApiClient
import kotlinx.coroutines.launch

@Composable
fun LoginScreen(onSuccess: (String, String) -> Unit) {
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var message by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var pending by remember { mutableStateOf<ApiClient.LoginResult?>(null) }
    val scope = rememberCoroutineScope()
    pending?.let { account ->
        PasswordChangeScreen(account.username, account.token, mandatory = true,
            onSuccess = { name, token -> pending = null; onSuccess(name, token) },
            onCancel = { scope.launch { runCatching { ApiClient.logout(account.token) } }; pending = null })
        return
    }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp), verticalArrangement = Arrangement.Center) {
        LocalizedText("LokZeitleiste", style = MaterialTheme.typography.headlineLarge)
        LocalizedText("Tf-Anmeldung mit dem vom Admin angelegten Konto")
        Spacer(Modifier.height(24.dp))
        OutlinedTextField(username, { username = it }, label = { LocalizedText("Benutzername") })
        OutlinedTextField(password, { password = it }, label = { LocalizedText("Passwort") },
            visualTransformation = PasswordVisualTransformation())
        if (message.isNotBlank()) LocalizedText(message, color = MaterialTheme.colorScheme.error)
        Button(enabled = !busy, onClick = {
            busy = true; message = ""
            scope.launch {
                try {
                    val result = ApiClient.login(username.trim().lowercase(), password)
                    password = ""
                    if (result.passwordChangeRequired) pending = result else onSuccess(result.username, result.token)
                } catch (error: Exception) {
                    message = error.message ?: "Anmeldung fehlgeschlagen."
                } finally { busy = false }
            }
        }) { LocalizedText(if (busy) "Anmeldung läuft …" else "Anmelden") }
        LocalizedText("Die Anmeldung bleibt auf diesem Gerät gespeichert.", style = MaterialTheme.typography.bodySmall)
    }
}
