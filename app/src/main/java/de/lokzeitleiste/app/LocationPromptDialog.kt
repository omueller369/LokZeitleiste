package de.lokzeitleiste.app

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import de.lokzeitleiste.app.data.Ds100Station
import de.lokzeitleiste.app.data.searchDs100

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
    val matches = remember(query, directory, suggestions) {
        if (query.isBlank()) suggestions.take(50) else searchDs100(query, directory)
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
                if (query.isNotBlank() && matches.isEmpty()) Text("Kein Treffer. Den Ortsnamen kannst du trotzdem übernehmen.")
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
