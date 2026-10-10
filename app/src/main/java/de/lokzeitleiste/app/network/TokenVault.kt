package de.lokzeitleiste.app.network

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

object TokenVault {
    private const val ALIAS = "lokzeitleiste_api_token"
    private fun prefs(context: Context) = context.getSharedPreferences("remote_session", 0)
    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(ALIAS, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(KeyGenParameterSpec.Builder(ALIAS,
            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .build())
        return generator.generateKey()
    }
    fun save(context: Context, username: String, token: String) {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val bytes = cipher.iv + cipher.doFinal(token.toByteArray(Charsets.UTF_8))
        prefs(context).edit().putString("username", username)
            .putString("sealed_token", Base64.encodeToString(bytes, Base64.NO_WRAP)).apply()
        de.lokzeitleiste.app.LanguageRuntime.accountVersion++
    }
    fun token(context: Context): String? {
        val raw = prefs(context).getString("sealed_token", null) ?: return null
        return runCatching {
            val bytes = Base64.decode(raw, Base64.DEFAULT)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, bytes.copyOfRange(0, 12)))
            String(cipher.doFinal(bytes.copyOfRange(12, bytes.size)), Charsets.UTF_8)
        }.getOrNull()
    }
    fun username(context: Context): String =
        if (token(context) != null) prefs(context).getString("username", "") ?: "" else ""
    fun clear(context: Context) { prefs(context).edit().clear().apply(); de.lokzeitleiste.app.LanguageRuntime.accountVersion++ }
}
