package ir.saeit.admin.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import ir.saeit.admin.api.SaeitApi
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import org.json.JSONObject

data class ChatItem(val role: String, val text: String)
data class ChatState(val items: List<ChatItem> = emptyList(), val busy: Boolean = false, val error: String? = null, val sessionId: Long? = null)

class MasterAgentViewModel(private val api: SaeitApi) : ViewModel() {
    private val _state = MutableStateFlow(ChatState())
    val state: StateFlow<ChatState> = _state

    fun send(text: String) {
        val clean = text.trim()
        if (clean.isEmpty() || _state.value.busy) return
        _state.value = _state.value.copy(items = _state.value.items + ChatItem("user", clean), busy = true, error = null)
        viewModelScope.launch(Dispatchers.IO) {
            try {
                val raw = api.sendMasterMessage(_state.value.sessionId, clean)
                val json = JSONObject(raw)
                val id = json.optJSONObject("session")?.optLong("id")?.takeIf { it > 0 } ?: _state.value.sessionId
                val reply = json.optString("reply").ifBlank { "پاسخی از سرور دریافت نشد." }
                _state.value = _state.value.copy(items = _state.value.items + ChatItem("assistant", reply), busy = false, sessionId = id)
            } catch (e: Exception) {
                _state.value = _state.value.copy(busy = false, error = e.message ?: "خطای ارتباط با سرور")
            }
        }
    }
}