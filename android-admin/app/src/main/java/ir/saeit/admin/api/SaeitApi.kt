package ir.saeit.admin.api

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

class SaeitApi(private val baseUrl: String, private val tokenProvider: () -> String?) {
    private val client = OkHttpClient()
    private val jsonType = "application/json".toMediaType()

    fun sendMasterMessage(sessionId: Long?, message: String): String {
        val path = if (sessionId == null) "/api/master-chat/" else "/api/master-chat/" + sessionId + "/messages/"
        val body = JSONObject().apply {
            put("message", message)
            if (sessionId == null) put("title", "Android Admin")
        }.toString().toRequestBody(jsonType)
        val req = Request.Builder().url(baseUrl.trimEnd('/') + path).post(body)
            .addHeader("Accept", "application/json")
            .apply { tokenProvider()?.takeIf { it.isNotBlank() }?.let { addHeader("Authorization", "Bearer " + it) } }
            .build()
        client.newCall(req).execute().use { replyObj ->
            val text = replyObj.body?.string().orEmpty()
            if (!replyObj.isSuccessful) error("API " + replyObj.code + ": " + text)
            return text
        }
    }
}