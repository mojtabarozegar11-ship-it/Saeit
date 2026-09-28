package ir.saeit.admin.api

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

data class LoginResult(val token: String, val username: String)
data class DashboardSnapshot(
    val agents: Int = 0, val activeAgents: Int = 0,
    val tasks: Int = 0, val queuedTasks: Int = 0,
    val approvals: Int = 0, val products: Int = 0, val activeProducts: Int = 0,
    val orders: Int = 0, val serviceOfferings: Int = 0, val serviceProviders: Int = 0,
    val serviceRequests: Int = 0, val serviceOrders: Int = 0,
    val serviceRefunds: Int = 0, val serviceReviews: Int = 0,
    val agentRuns: Int = 0, val revenueTotal: String = "0"
)
data class ApprovalItem(
    val id: Long, val action: String, val target: String, val risk: String, val status: String
)
data class AgentItem(val id: Long, val code: String, val name: String, val active: Boolean, val risk: String)
data class TaskItem(val id: Long, val action: String, val status: String, val agent: String, val executionId: String, val attempt: Int, val maxAttempts: Int, val risk: String)
data class AuditItem(
    val id: Long, val action: String, val actor: String, val target: String, val createdAt: String
)
data class MasterRuntime(
    val scheduler: String = "", val watchdog: String = "", val enabled: Boolean = false,
    val ownerApproved: Boolean = false, val lastRunAt: String = "", val lastResult: String = "",
    val succeeded: Int = 0, val failed: Int = 0, val queued: Int = 0, val running: Int = 0,
    val stale: Int = 0, val internet: String = "unknown", val latestRunId: Long = 0,
    val latestStatus: String = "unknown", val latestError: String = ""
)
data class AdminSnapshot(val dashboard: DashboardSnapshot, val audits: List<AuditItem>, val master: MasterRuntime = MasterRuntime())
data class RobotRunItem(val id: Long, val robot: String, val status: String, val traceId: String, val startedAt: String, val finishedAt: String, val error: String)
data class OpsAgentItem(val id: Long, val name: String, val active: Boolean)
data class EvolutionItem(val id: Long, val target: String, val action: String, val status: String, val risk: String, val createdAt: String)
data class EventItem(val id: Long, val type: String, val actor: String, val domain: String, val traceId: String, val createdAt: String)
data class OpsApprovalItem(val id: Long, val action: String, val target: String, val risk: String, val status: String)
data class AgentPerformanceItem(val agentId: Long, val agent: String, val success: Int, val failed: Int, val latencyMs: Int, val quality: String?, val businessValue: String?)
data class OperationsSnapshot(val runs: List<RobotRunItem>, val agents: List<OpsAgentItem>, val evolution: List<EvolutionItem>, val events: List<EventItem>, val approvals: List<OpsApprovalItem>, val performance: List<AgentPerformanceItem>)
data class MasterScore(
    val target: Double = 100.0, val overall: Double = 0.0, val empire: Double = 0.0,
    val businessEconomy: Double = 0.0, val website: Double = 0.0, val windowDays: Int = 7,
    val generatedAt: String = "", val evidence: String = ""
)


class SaeitApi(private val baseUrl: String, private val tokenProvider: () -> String?) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(8, java.util.concurrent.TimeUnit.SECONDS)
        .readTimeout(12, java.util.concurrent.TimeUnit.SECONDS)
        .writeTimeout(12, java.util.concurrent.TimeUnit.SECONDS)
        .build()
    private val jsonType = "application/json".toMediaType()

    private fun request(path: String, method: String = "GET", body: String? = null): String {
        val builder = Request.Builder().url(baseUrl.trimEnd('/') + path).addHeader("Accept", "application/json")
        tokenProvider()?.takeIf { it.isNotBlank() }?.let { builder.addHeader("Authorization", "Token " + it) }
        if (method == "POST") builder.post((body ?: "{}").toRequestBody(jsonType))
        val response = client.newCall(builder.build()).execute()
        response.use { responseBody ->
            val text = responseBody.body?.string().orEmpty()
            if (!responseBody.isSuccessful) error("API " + responseBody.code + ": " + text.take(300))
            return text
        }
    }

    fun login(username: String, password: String): LoginResult {
        val body = JSONObject().put("username", username).put("password", password).toString()
        val json = JSONObject(request("/api/auth/token/", "POST", body))
        return LoginResult(json.getString("token"), json.getJSONObject("user").getString("username"))
    }

    fun adminSnapshot(): AdminSnapshot {
        val root = JSONObject(request("/api/admin/dashboard/"))
        val c = root.getJSONObject("counts")
        val dashboard = DashboardSnapshot(
            agents = c.optInt("agents"), activeAgents = c.optInt("active_agents"),
            tasks = c.optInt("tasks"), queuedTasks = c.optInt("queued_tasks"),
            approvals = c.optInt("approvals"), products = c.optInt("products"),
            activeProducts = c.optInt("active_products"), orders = c.optInt("orders"),
            serviceOfferings = c.optInt("service_offerings"),
            serviceProviders = c.optInt("service_providers"),
            serviceRequests = c.optInt("service_requests"),
            serviceOrders = c.optInt("service_orders"),
            serviceRefunds = c.optInt("service_refunds"),
            serviceReviews = c.optInt("service_reviews"),
            agentRuns = c.optInt("agent_runs"),
            revenueTotal = c.optString("revenue_total", "0")
        )
        val runtime = root.optJSONObject("master_runtime")
        val statuses = runtime?.optJSONArray("run_status")
        var succeeded = 0; var failed = 0
        if (statuses != null) for (i in 0 until statuses.length()) {
            val st = statuses.getJSONObject(i); if (st.optString("status") == "succeeded") succeeded = st.optInt("count") else if (st.optString("status") == "failed") failed = st.optInt("count")
        }
        val latest = runtime?.optJSONObject("latest_run")
        val rm = runtime?.optJSONObject("runtime_metrics")
        val master = MasterRuntime(
            scheduler = runtime?.optString("scheduler").orEmpty(), watchdog = runtime?.optString("watchdog").orEmpty(),
            enabled = runtime?.optBoolean("enabled") ?: false, ownerApproved = runtime?.optBoolean("owner_approved") ?: false,
            lastRunAt = runtime?.optString("last_run_at").orEmpty(), lastResult = runtime?.optJSONObject("last_result")?.toString().orEmpty(),
            succeeded = succeeded, failed = failed, queued = rm?.optInt("queued") ?: 0, running = rm?.optInt("running") ?: 0, stale = rm?.optInt("stale_running") ?: 0,
            internet = runtime?.optJSONObject("internet")?.optString("status", "unknown") ?: "unknown",
            latestRunId = latest?.optLong("id") ?: 0, latestStatus = latest?.optString("status", "unknown") ?: "unknown", latestError = latest?.optString("error").orEmpty()
        )
        val rows = root.optJSONArray("recent_audits")
        val audits = if (rows == null) emptyList() else (0 until rows.length()).map { i ->
            val x = rows.getJSONObject(i)
            AuditItem(
                x.optLong("id"),
                x.optString("action"),
                x.optString("actor_type"),
                x.optString("target_type") + ":" + x.optString("target_id"),
                x.optString("created_at")
            )
        }
        return AdminSnapshot(dashboard, audits, master)
    }

    fun masterScore(): MasterScore {
        val x = JSONObject(request("/api/admin/master-score/"))
        return MasterScore(
            target = x.optDouble("target", 100.0), overall = x.optDouble("overall", 0.0),
            empire = x.optDouble("empire", 0.0), businessEconomy = x.optDouble("business_economy", 0.0),
            website = x.optDouble("website", 0.0), windowDays = x.optInt("window_days", 7),
            generatedAt = x.optString("generated_at"), evidence = x.optJSONObject("evidence")?.toString().orEmpty()
        )
    }

    fun operations(): OperationsSnapshot {
        val root = JSONObject(request("/api/admin/operations/"))
        fun arr(name: String) = root.optJSONArray(name)
        val runs = arr("robot_runs")?.let { a -> (0 until a.length()).map { i -> val x=a.getJSONObject(i); RobotRunItem(x.optLong("id"),x.optString("robot"),x.optString("status"),x.optString("trace_id"),x.optString("started_at"),x.optString("finished_at"),x.optString("error")) } } ?: emptyList()
        val agents = arr("agents")?.let { a -> (0 until a.length()).map { i -> val x=a.getJSONObject(i); OpsAgentItem(x.optLong("id"),x.optString("name"),x.optBoolean("active")) } } ?: emptyList()
        val evolution = arr("evolution")?.let { a -> (0 until a.length()).map { i -> val x=a.getJSONObject(i); EvolutionItem(x.optLong("id"),x.optString("target"),x.optString("action"),x.optString("status"),x.optString("risk"),x.optString("created_at")) } } ?: emptyList()
        val events = arr("events")?.let { a -> (0 until a.length()).map { i -> val x=a.getJSONObject(i); EventItem(x.optLong("id"),x.optString("type"),x.optString("actor"),x.optString("domain"),x.optString("trace_id"),x.optString("created_at")) } } ?: emptyList()
        val approvals = arr("approvals")?.let { a -> (0 until a.length()).map { i -> val x=a.getJSONObject(i); OpsApprovalItem(x.optLong("id"),x.optString("action"),x.optString("target"),x.optString("risk"),x.optString("status")) } } ?: emptyList()
        val performance = arr("performance")?.let { a -> (0 until a.length()).map { i -> val x=a.getJSONObject(i); AgentPerformanceItem(x.optLong("agent_id"),x.optString("agent"),x.optInt("success"),x.optInt("failed"),x.optInt("latency_ms"),x.optString("quality").takeIf { it.isNotBlank() },x.optString("business_value").takeIf { it.isNotBlank() }) } } ?: emptyList()
        return OperationsSnapshot(runs, agents, evolution, events, approvals, performance)
    }

    fun agents(): List<AgentItem> {
        val raw = request("/api/agent-control/")
        val root = runCatching { JSONObject(raw) }.getOrNull()
        val rows = root?.optJSONArray("results") ?: if (raw.trimStart().startsWith("[")) org.json.JSONArray(raw) else return emptyList()
        return (0 until rows.length()).map { i ->
            val x = rows.getJSONObject(i)
            AgentItem(x.optLong("id"), x.optString("code"), x.optString("name"), x.optBoolean("active"), x.optString("risk_level"))
        }
    }

    fun setAgentActive(id: Long, active: Boolean): AgentItem {
        val action = if (active) "activate" else "deactivate"
        val x = JSONObject(request("/api/agent-control/" + id + "/" + action + "/", "POST", "{}"))
        return AgentItem(x.optLong("id"), x.optString("code"), x.optString("name"), x.optBoolean("active"), x.optString("risk_level"))
    }

    fun tasks(): List<TaskItem> {
        val raw = request("/api/tasks/")
        val root = runCatching { JSONObject(raw) }.getOrNull()
        val rows = root?.optJSONArray("results") ?: if (raw.trimStart().startsWith("[")) org.json.JSONArray(raw) else return emptyList()
        return (0 until rows.length()).map { i ->
            val x = rows.getJSONObject(i)
            val agent = x.optJSONObject("agent")?.optString("name") ?: x.optString("agent")
            TaskItem(x.optLong("id"), x.optString("action_type"), x.optString("status"), agent,
                x.optString("execution_id"), x.optInt("attempt_count"), x.optInt("max_attempts"), x.optString("risk_snapshot"))
        }
    }

    fun taskAction(id: Long, action: String, executionId: String = "", error: String = ""): TaskItem {
        val body = JSONObject()
        if (executionId.isNotBlank()) body.put("execution_id", executionId)
        if (action == "complete") body.put("output_data", JSONObject().put("source", "android-admin"))
        if (action == "fail") body.put("error", error.ifBlank { "Failed from Android Admin" })
        val x = JSONObject(request("/api/tasks/" + id + "/" + action + "/", "POST", body.toString()))
        val agent = x.optJSONObject("agent")?.optString("name") ?: x.optString("agent")
        return TaskItem(x.optLong("id"), x.optString("action_type"), x.optString("status"), agent,
            x.optString("execution_id"), x.optInt("attempt_count"), x.optInt("max_attempts"), x.optString("risk_snapshot"))
    }

    fun approvals(): List<ApprovalItem> {
        val raw = request("/api/approvals/?status=pending")
        val root = runCatching { JSONObject(raw) }.getOrNull()
        val rows = root?.optJSONArray("results") ?: if (raw.trimStart().startsWith("[")) org.json.JSONArray(raw) else return emptyList()
        return (0 until rows.length()).map { i ->
            val x = rows.getJSONObject(i)
            ApprovalItem(x.optLong("id"), x.optString("action_type"), x.optString("target_type"),
                x.optString("risk"), x.optString("status"))
        }
    }

    fun decideApproval(id: Long, approved: Boolean, note: String = ""): String {
        val body = JSONObject().put("approved", approved).put("note", note)
        return request("/api/approvals/" + id + "/decide/", "POST", body.toString())
    }

    fun sendMasterMessage(sessionId: Long?, message: String): String {
        val path = if (sessionId == null) "/api/master-chat/" else "/api/master-chat/" + sessionId + "/messages/"
        val payload = JSONObject().put("message", message)
        if (sessionId == null) payload.put("title", "Android Admin")
        return request(path, "POST", payload.toString())
    }

    fun executeMasterCommand(command: String): String {
        return request("/api/master-chat/command/", "POST", JSONObject().put("command", command).toString())
    }
}
