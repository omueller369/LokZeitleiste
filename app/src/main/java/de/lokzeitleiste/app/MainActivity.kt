package de.lokzeitleiste.app

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import de.lokzeitleiste.app.network.TokenVault

/** Native login, followed by the same versioned TF portal used in the browser. */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        fun openPortal() { startActivity(Intent(this, TfPortalActivity::class.java)); finish() }
        if (TokenVault.username(this).isNotBlank()) { openPortal(); return }
        setContent { MaterialTheme { LanguageShell { LoginScreen { username, token ->
            TokenVault.save(this, username, token); openPortal()
        } } } }
    }
}
