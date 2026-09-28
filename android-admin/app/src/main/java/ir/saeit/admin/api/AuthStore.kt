package ir.saeit.admin.api

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

class AuthStore(context: Context) {
    private val masterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()
    private val prefs = EncryptedSharedPreferences.create(
        context,
        "saeit_admin_auth",
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    fun token(): String? = prefs.getString("token", null)
    fun username(): String? = prefs.getString("username", null)
    fun save(token: String, username: String) {
        prefs.edit().putString("token", token).putString("username", username).apply()
    }
    fun clear() { prefs.edit().clear().apply() }
}
