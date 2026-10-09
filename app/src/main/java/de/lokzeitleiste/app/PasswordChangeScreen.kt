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
fun PasswordChangeScreen(username: String, token: String, mandatory: Boolean = false,
    onSuccess: (String, String) -> Unit, onCancel: () -> Unit) {
    var current by remember { mutableStateOf("") }
    var new by remember { mutableStateOf("") }
    var confirm by remember { mutableStateOf("") }
    var error by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp), verticalArrangement = Arrangement.Center) {
        Text("Passwort ändern", style = MaterialTheme.typography.headlineMedium)
        Text("Konto: $username")
        if (mandatory) Text("Vor der Nutzung müssen Sie Ihr Initialpasswort ändern.")
        OutlinedTextField(current, { current = it }, enabled = !busy, label = { Text("Aktuelles Passwort") },
            visualTransformation = PasswordVisualTransformation())
        OutlinedTextField(new, { new = it }, enabled = !busy, label = { Text("Neues Passwort (mindestens 12 Zeichen)") },
            visualTransformation = PasswordVisualTransformation())
        OutlinedTextField(confirm, { confirm = it }, enabled = !busy, label = { Text("Passwort wiederholen") },
            visualTransformation = PasswordVisualTransformation())
        if (error.isNotBlank()) Text(error, color = MaterialTheme.colorScheme.error)
        Button(enabled = !busy, onClick = {
            if (new.length < 12 || new != confirm || new == current) {
                error = "Mindestens zwölf Zeichen, gleiche Bestätigung und ein anderes Passwort erforderlich."
            } else {
                busy = true; error = ""
                scope.launch {
                    try {
                        val result = ApiClient.changePassword(username, token, current, new, confirm)
                        current = ""; new = ""; confirm = ""
                        onSuccess(result.username, result.token)
                    } catch (exception: Exception) {
                        error = (exception.message ?: "Passwortwechsel fehlgeschlagen.") +
                            " Falls die Änderung gespeichert wurde, melden Sie sich mit dem neuen Passwort an."
                    } finally { busy = false }
                }
            }
        }) { Text(if (busy) "Wird geändert …" else "Passwort speichern") }
        TextButton(enabled = !busy, onClick = onCancel) { Text(if (mandatory) "Zur Anmeldung" else "Abbrechen") }
    }
}
