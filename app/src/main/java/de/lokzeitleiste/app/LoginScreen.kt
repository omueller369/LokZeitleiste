package de.lokzeitleiste.app

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
    val scope = rememberCoroutineScope()
    Column(Modifier.fillMaxSize().padding(32.dp), verticalArrangement = Arrangement.Center) {
        Text("LokZeitleiste", style = MaterialTheme.typography.headlineLarge)
        Text("Tf-Anmeldung mit dem vom Admin angelegten Konto")
        Spacer(Modifier.height(24.dp))
        OutlinedTextField(username, { username = it }, label = { Text("Benutzername") })
        OutlinedTextField(password, { password = it }, label = { Text("Passwort") },
            visualTransformation = PasswordVisualTransformation())
        if (message.isNotBlank()) Text(message, color = MaterialTheme.colorScheme.error)
        Button(enabled = !busy, onClick = {
            busy = true; message = ""
            scope.launch {
                try {
                    val (name, token) = ApiClient.login(username.trim().lowercase(), password)
                    password = ""
                    onSuccess(name, token)
                } catch (error: Exception) {
                    message = error.message ?: "Anmeldung fehlgeschlagen."
                } finally { busy = false }
            }
        }) { Text(if (busy) "Anmeldung läuft …" else "Anmelden") }
        Text("Die Anmeldung bleibt auf diesem Gerät gespeichert.", style = MaterialTheme.typography.bodySmall)
    }
}
