package ir.saeit.admin.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import ir.saeit.admin.api.AdminSnapshot
import ir.saeit.admin.api.ApprovalItem
import ir.saeit.admin.api.SaeitApi
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import org.json.JSONObject

data class ChatItem(val role: String, val text: String)
data class AdminState(
    val authenticated: Boolean = false, val username: String? = null,
    val snapshot: AdminSnapshot? = null, val approvals: List<ApprovalItem> = emptyList(), val agents: List<ir.saeit.admin.api.AgentItem> = emptyList(),
    val tasks: List<ir.saeit.admin.api.TaskItem> = emptyList(),
    val operations: ir.saeit.admin.api.OperationsSnapshot? = null,
    val masterScore: ir.saeit.admin.api.MasterScore? = null,
    val items: List<ChatItem> = emptyList(), val sessionId: Long? = null,
    val busy: Boolean = false, val error: String? = null
)

class MasterAgentViewModel(
    private val api: SaeitApi,
    private val saveToken: (String, String) -> Unit,
    private val clearToken: () -> Unit,
    initialUsername: String? = null
) : ViewModel() {
    private val _state = MutableStateFlow(AdminState(authenticated = initialUsername != null, username = initialUsername))
    val state: StateFlow<AdminState> = _state

    fun login(username: String, password: String) {
        if (username.isBlank() || password.isBlank() || _state.value.busy) return
        _state.value = _state.value.copy(busy = true, error = null)
        viewModelScope.launch(Dispatchers.IO) {
            try {
                val result = api.login(username.trim(), password)
                saveToken(result.token, result.username)
                _state.value = _state.value.copy(authenticated = true, username = result.username, busy = false)
                refresh()
            } catch (e: Exception) {
                _state.value = _state.value.copy(busy = false, error = "ورود ناموفق: " + (e.message ?: "خطای ارتباط"))
            }
        }
    }

    fun logout() { clearToken(); _state.value = AdminState() }

    fun clearError() { _state.value = _state.value.copy(error = null) }

    fun refresh() {
        if (!_state.value.authenticated || _state.value.busy) return
        _state.value = _state.value.copy(busy = true, error = null)
        viewModelScope.launch(Dispatchers.IO) {
            try {
                _state.value = _state.value.copy(snapshot = api.adminSnapshot(), approvals = api.approvals(), agents = api.agents(), tasks = api.tasks(), operations = api.operations(), masterScore = api.masterScore(), busy = false)
            } catch (e: Exception) {
                _state.value = _state.value.copy(busy = false, error = e.message ?: "خطای دریافت اطلاعات")
            }
        }
    }


    fun setAgentActive(id: Long, active: Boolean) {
        if (_state.value.busy) return
        _state.value = _state.value.copy(busy = true, error = null)
        viewModelScope.launch(Dispatchers.IO) {
            try {
                api.setAgentActive(id, active)
                _state.value = _state.value.copy(snapshot = api.adminSnapshot(), agents = api.agents(), busy = false)
            } catch (e: Exception) {
                _state.value = _state.value.copy(busy = false, error = e.message ?: "خطای تغییر وضعیت Agent")
            }
        }
    }

    fun taskAction(id: Long, action: String, executionId: String = "") {
        if (_state.value.busy) return
        _state.value = _state.value.copy(busy = true, error = null)
        viewModelScope.launch(Dispatchers.IO) {
            try {
                api.taskAction(id, action, executionId)
                _state.value = _state.value.copy(snapshot = api.adminSnapshot(), tasks = api.tasks(), busy = false)
            } catch (e: Exception) {
                _state.value = _state.value.copy(busy = false, error = e.message ?: "خطای عملیات Task")
            }
        }
    }

    fun decideApproval(id: Long, approved: Boolean) {
        if (_state.value.busy) return
        _state.value = _state.value.copy(busy = true, error = null)
        viewModelScope.launch(Dispatchers.IO) {
            try {
                api.decideApproval(id, approved)
                _state.value = _state.value.copy(snapshot = api.adminSnapshot(), approvals = api.approvals(), agents = api.agents(), tasks = api.tasks(), operations = api.operations(), masterScore = api.masterScore(), busy = false)
            } catch (e: Exception) {
                _state.value = _state.value.copy(busy = false, error = e.message ?: "خطای تصمیم تأیید")
            }
        }
    }

    fun executeCommand(command: String) {
        if (_state.value.busy || !_state.value.authenticated) return
        _state.value = _state.value.copy(busy = true, error = null)
        viewModelScope.launch(Dispatchers.IO) {
            try {
                val json = JSONObject(api.executeMasterCommand(command))
                val output = json.optJSONObject("output")
                val detail = output?.optString("action").orEmpty().takeIf { it.isNotBlank() }
                    ?: output?.optString("gateway").orEmpty().takeIf { it.isNotBlank() }
                    ?: ""
                val command = json.optString("command")
                val outputText = output?.let { out ->
                    val parts = mutableListOf<String>()
                    if (out.has("status")) parts += "status=" + out.optString("status")
                    if (out.has("action")) parts += "action=" + out.optString("action")
                    if (out.has("http_status")) parts += "HTTP=" + out.optInt("http_status")
                    if (out.has("scheduler")) parts += "scheduler=" + out.optString("scheduler")
                    if (out.has("watchdog")) parts += "watchdog=" + out.optString("watchdog")
                    if (out.has("total_master_runs")) parts += "runs=" + out.optInt("total_master_runs")
                    if (out.has("latest_run_id")) parts += "latest=" + out.optLong("latest_run_id")
                    out.optJSONObject("last_result")?.let { lr ->
                        parts += "agents=" + lr.optInt("agents_evaluated")
                        parts += "queued=" + lr.optInt("queued")
                        parts += "failed=" + lr.optInt("failed")
                    }
                    parts.joinToString(" · ")
                }.orEmpty()
                val reply = "اجرای واقعی Master Agent: " + json.optString("status") +
                    " · run_id=" + json.optLong("run_id") +
                    " · command=" + command +
                    (if (outputText.isNotBlank()) " · $outputText" else if (detail.isNotBlank()) " · $detail" else "")
                _state.value = _state.value.copy(items = _state.value.items + ChatItem("assistant", reply), busy = false)
                refresh()
            } catch (e: Exception) {
                _state.value = _state.value.copy(busy = false, error = e.message ?: "خطای اجرای دستور Master Agent")
            }
        }
    }

    fun send(text: String) {
        val clean = text.trim()
        if (clean.isEmpty() || _state.value.busy || !_state.value.authenticated) return
        _state.value = _state.value.copy(items = _state.value.items + ChatItem("user", clean), busy = true, error = null)
        viewModelScope.launch(Dispatchers.IO) {
            try {
                val json = JSONObject(api.sendMasterMessage(_state.value.sessionId, clean))
                val id = json.optJSONObject("session")?.optLong("id")?.takeIf { it > 0 } ?: _state.value.sessionId
                val reply = json.optString("reply").ifBlank { "پاسخی از سرور دریافت نشد." }
                _state.value = _state.value.copy(items = _state.value.items + ChatItem("assistant", reply), busy = false, sessionId = id)
            } catch (e: Exception) {
                _state.value = _state.value.copy(busy = false, error = e.message ?: "خطای ارتباط با Master Agent")
            }
        }
    }
}
