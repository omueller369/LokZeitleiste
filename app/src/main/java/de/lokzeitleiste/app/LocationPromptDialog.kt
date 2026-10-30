package de.lokzeitleiste.app

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import de.lokzeitleiste.app.data.Ds100Station
import de.lokzeitleiste.app.data.searchDs100
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun LocationPromptDialog(
    directory: List<Ds100Station>,
    suggestions: List<Ds100Station>,
    onChoose: (String, String) -> Unit,
    onDismiss: () -> Unit
) {
    var query by remember { mutableStateOf("") }
    var expanded by remember { mutableStateOf(false) }
    var matches by remember { mutableStateOf(suggestions.take(50)) }
    var searching by remember { mutableStateOf(false) }
    LaunchedEffect(query, directory, suggestions) {
        val text = query
        if (text.isBlank()) {
            matches = suggestions.take(50)
            searching = false
        } else {
            matches = emptyList()
            searching = true
            delay(200)
            matches = withContext(Dispatchers.Default) { searchDs100(text, directory) }
            searching = false
        }
    }
    AlertDialog(onDismissRequest = onDismiss,
        title = { Text("Wo steht der Zug?") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Seit mehr als fünf Minuten Stillstand ist noch kein Standort eingetragen. Ort oder DS100 eingeben und einen Treffer auswählen – oder nur den Ortsnamen übernehmen.")
                ExposedDropdownMenuBox(expanded = expanded && matches.isNotEmpty(), onExpandedChange = { expanded = it }) {
                    OutlinedTextField(
                        value = query,
                        onValueChange = { query = it; expanded = true },
                        label = { Text("Ort oder DS100") },
                        singleLine = true,
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded && matches.isNotEmpty()) },
                        modifier = Modifier.menuAnchor(MenuAnchorType.PrimaryEditable).fillMaxWidth()
                    )
                    ExposedDropdownMenu(expanded = expanded && matches.isNotEmpty(), onDismissRequest = { expanded = false },
                        modifier = Modifier.heightIn(max = 280.dp)) {
                        matches.forEach { match ->
                            DropdownMenuItem(text = { Text("${match.code} · ${match.name}") }, onClick = {
                                onChoose(match.name, match.code)
                            })
                        }
                    }
                }
                if (searching) Text("Suche …")
                if (!searching && query.isNotBlank() && matches.isEmpty()) Text("Kein Treffer. Den Ortsnamen kannst du trotzdem übernehmen.")
                if (matches.size == 50) Text("Bis zu 50 Treffer – Eingabe bei Bedarf genauer machen.")
                Text("DS100-Verzeichnis: Stand 04/2018. Angaben bitte prüfen.", style = MaterialTheme.typography.bodySmall)
            }
        },
        confirmButton = {
            TextButton(enabled = query.isNotBlank(), onClick = { onChoose(query.trim(), "") }) {
                Text("Nur Ortsnamen übernehmen")
            }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Später") } }
    )
}
