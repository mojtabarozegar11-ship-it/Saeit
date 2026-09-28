package ir.saeit.admin

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import ir.saeit.admin.api.AuthStore
import ir.saeit.admin.api.SaeitApi
import ir.saeit.admin.ui.MasterAgentViewModel
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalLayoutDirection

private const val BASE_URL = "https://zomorodmelal.ir"

@Composable
fun SaeitAdminApp() {
    val context = LocalContext.current
    val store = remember { AuthStore(context) }
    val api = remember { SaeitApi(BASE_URL) { store.token() } }
    val factory = remember {
        object : ViewModelProvider.Factory {
            override fun <T : androidx.lifecycle.ViewModel> create(modelClass: Class<T>): T =
                MasterAgentViewModel(api, store::save, store::clear, store.username()) as T
        }
    }
    val vm: MasterAgentViewModel = viewModel(factory = factory)
    val state by vm.state.collectAsState()
    CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
        Surface(Modifier.fillMaxSize()) {
            if (state.authenticated) AdminHome(vm) else LoginScreen(vm, state.busy, state.error)
        }
    }
}
@Composable
private fun LoginScreen(vm: MasterAgentViewModel, busy: Boolean, error: String?) {
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    Column(
        Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center
    ) {
        Text("پنل مدیریت Saeit", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(8.dp))
        Text("ورود امن مدیر به مرکز کنترل")
        Spacer(Modifier.height(24.dp))
        OutlinedTextField(username, { username = it }, Modifier.fillMaxWidth(), label = { Text("نام کاربری مدیر") }, singleLine = true)
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(password, { password = it }, Modifier.fillMaxWidth(), label = { Text("رمز عبور") }, singleLine = true)
        Spacer(Modifier.height(16.dp))
        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Spacer(Modifier.height(8.dp))
        Button(
            onClick = { vm.login(username, password) },
            enabled = username.isNotBlank() && password.isNotBlank() && !busy,
            Modifier.fillMaxWidth()
        ) { Text(if (busy) "در حال ورود..." else "ورود به پنل") }
        Spacer(Modifier.height(12.dp))
        Text("اتصال فقط به https://zomorodmelal.ir انجام می‌شود.", style = MaterialTheme.typography.bodySmall)
    }
}
@Composable
private fun AdminHome(vm: MasterAgentViewModel) {
    val state by vm.state.collectAsState()
    var tab by remember { mutableIntStateOf(0) }
    LaunchedEffect(Unit) {
        vm.refresh()
        while (true) {
            kotlinx.coroutines.delay(15000)
            vm.refresh()
        }
    }
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("مرکز کنترل Saeit") },
                actions = { TextButton(onClick = vm::logout) { Text("خروج") } }
            )
        },
        bottomBar = {
            NavigationBar {
                NavigationBarItem(tab == 0, { tab = 0 }, label = { Text("داشبورد") }, icon = { Text("⌂") })
                NavigationBarItem(tab == 1, { tab = 1 }, label = { Text("تأییدها") }, icon = { Text("✓") })
                NavigationBarItem(tab == 2, { tab = 2 }, label = { Text("Master Agent") }, icon = { Text("AI") })
                NavigationBarItem(tab == 3, { tab = 3 }, label = { Text("Agentها") }, icon = { Text("AG") })
                NavigationBarItem(tab == 4, { tab = 4 }, label = { Text("سیستم") }, icon = { Text("SYS") })
                NavigationBarItem(tab == 5, { tab = 5 }, label = { Text("Taskها") }, icon = { Text("TSK") })
                NavigationBarItem(tab == 6, { tab = 6 }, label = { Text("عملیات") }, icon = { Text("OPS") })
            }
        }
    ) { padding ->
        when (tab) {
            0 -> DashboardScreen(state, vm, Modifier.padding(padding))
            1 -> ApprovalScreen(state, vm, Modifier.padding(padding))
            2 -> ChatScreen(state, vm, Modifier.padding(padding))
            3 -> AgentScreen(state, vm, Modifier.padding(padding))
            4 -> SystemScreen(state, vm, Modifier.padding(padding))
            6 -> OperationsScreen(state, vm, Modifier.padding(padding))
            else -> TaskScreen(state, vm, Modifier.padding(padding))
        }
    }
}

@Composable
private fun AgentScreen(state: ir.saeit.admin.ui.AdminState, vm: MasterAgentViewModel, modifier: Modifier) {
    LazyColumn(
        modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
        contentPadding = PaddingValues(vertical = 8.dp)
    ) {
        item { Text("کنترل Agentها", style = MaterialTheme.typography.headlineSmall) }
        if (state.agents.isEmpty()) {
            item { Text("Agent قابل نمایش وجود ندارد.") }
        } else {
            items(state.agents, key = { it.id }) { agent ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp)) {
                        Text(agent.name, style = MaterialTheme.typography.titleMedium)
                        Text(agent.code)
                        Text("ریسک: " + agent.risk + " · وضعیت: " + if (agent.active) "فعال" else "غیرفعال")
                        Spacer(Modifier.height(8.dp))
                        Button(
                            onClick = { vm.setAgentActive(agent.id, !agent.active) },
                            enabled = !state.busy,
                            Modifier.fillMaxWidth()
                        ) {
                            Text(if (agent.active) "غیرفعال‌سازی" else "فعال‌سازی")
                        }
                    }
                }
            }
        }
        item {
            Button(onClick = vm::refresh, enabled = !state.busy, Modifier.fillMaxWidth()) {
                Text("به‌روزرسانی Agentها")
            }
        }
    }
}

@Composable
private fun DashboardScreen(state: ir.saeit.admin.ui.AdminState, vm: MasterAgentViewModel, modifier: Modifier) {
    LazyColumn(
        modifier.fillMaxSize().padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        contentPadding = PaddingValues(vertical = 16.dp)
    ) {
        item {
            Text("سلام " + (state.username ?: "مدیر"), style = MaterialTheme.typography.headlineSmall)
            Text("وضعیت لحظه‌ای مرکز کنترل")
        }
        state.error?.let { item { Text(it, color = MaterialTheme.colorScheme.error) } }
        val score = state.masterScore
        item {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("امتیاز زنده Master Agent", style = MaterialTheme.typography.titleLarge)
                    Text("هدف: 100/100 · پنجره شواهد: ${score?.windowDays ?: 7} روز")
                    Text("امپراتوری: ${score?.empire ?: 0.0}/100")
                    Text("کسب‌وکار و اقتصاد: ${score?.businessEconomy ?: 0.0}/100")
                    Text("سایت: ${score?.website ?: 0.0}/100")
                    Text("امتیاز کل: ${score?.overall ?: 0.0}/100", style = MaterialTheme.typography.headlineMedium)
                    Text("این امتیاز از شواهد عملیاتی محاسبه می‌شود؛ امتیاز هدف، امتیاز ادعایی نیست.", style = MaterialTheme.typography.bodySmall)
                }
            }
        }
        val d = state.snapshot?.dashboard
        item { MetricCard("Agentهای فعال", d?.activeAgents ?: 0, "از " + (d?.agents ?: 0) + " Agent ثبت‌شده") }
        item { MetricCard("Taskهای صف", d?.queuedTasks ?: 0, "کل Taskها: " + (d?.tasks ?: 0)) }
        item { MetricCard("تأییدهای در انتظار", d?.approvals ?: 0, "نیازمند تصمیم مالک") }
        item { MetricCard("محصولات فعال", d?.activeProducts ?: 0, "کل محصولات: " + (d?.products ?: 0)) }
        item { MetricCard("سفارش‌ها", d?.orders ?: 0, "چرخه تجارت") }
        item { MetricCard("خدمات", d?.serviceOfferings ?: 0, "Provider: " + (d?.serviceProviders ?: 0) + " · درخواست: " + (d?.serviceRequests ?: 0)) }
        item { MetricCard("اجرای Agent خدمات", d?.agentRuns ?: 0, "Service Marketplace Agent") }
        item { MetricCard("درآمد ثبت‌شده", d?.revenueTotal ?: "0", "Ledger payment entries") }
        val m = state.snapshot?.master
        item {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("Master Agent — 24/7", style = MaterialTheme.typography.titleLarge)
                    Text("Scheduler: ${m?.scheduler ?: "-"}")
                    Text("Watchdog: ${m?.watchdog ?: "-"}")
                    Text("وضعیت: ${m?.latestStatus ?: "-"} · Run #${m?.latestRunId ?: 0}")
                    Text("موفق: ${m?.succeeded ?: 0} · خطا: ${m?.failed ?: 0} · Queue: ${m?.queued ?: 0} · Running: ${m?.running ?: 0} · Stale: ${m?.stale ?: 0}")
                    Text("Internet Gateway: ${m?.internet ?: "-"}")
                    Text("آخرین اجرا: ${m?.lastRunAt ?: "-"}", style = MaterialTheme.typography.bodySmall)
                    if (!m?.latestError.isNullOrBlank()) Text("خطا: ${m?.latestError}", color = MaterialTheme.colorScheme.error)
                }
            }
        }
        item {
            Button(onClick = vm::refresh, enabled = !state.busy, Modifier.fillMaxWidth()) {
                Text(if (state.busy) "در حال به‌روزرسانی..." else "به‌روزرسانی مرکز کنترل")
            }
        }
    }
}
@Composable
private fun MetricCard(title: String, value: Int, subtitle: String) {
    MetricCard(title, value.toString(), subtitle)
}

@Composable
private fun MetricCard(title: String, value: String, subtitle: String) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Text(value, style = MaterialTheme.typography.headlineLarge)
            Text(subtitle, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun ApprovalScreen(state: ir.saeit.admin.ui.AdminState, vm: MasterAgentViewModel, modifier: Modifier) {
    LazyColumn(
        modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        contentPadding = PaddingValues(vertical = 8.dp)
    ) {
        item { Text("مرکز تأیید مالک", style = MaterialTheme.typography.headlineSmall) }
        state.error?.let { item { Text(it, color = MaterialTheme.colorScheme.error) } }
        if (state.approvals.isEmpty()) item { Text("در حال حاضر تأیید در انتظار وجود ندارد.") }
        items(state.approvals, key = { it.id }) { approval ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp)) {
                    Text("#" + approval.id + " · " + approval.action, style = MaterialTheme.typography.titleMedium)
                    Text("هدف: " + approval.target)
                    Text("ریسک: " + approval.risk)
                    Spacer(Modifier.height(12.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = { vm.decideApproval(approval.id, true) }, enabled = !state.busy) { Text("تأیید") }
                        OutlinedButton(onClick = { vm.decideApproval(approval.id, false) }, enabled = !state.busy) { Text("رد") }
                    }
                }
            }
        }
    }
}

@Composable
private fun SystemScreen(state: ir.saeit.admin.ui.AdminState, vm: MasterAgentViewModel, modifier: Modifier) {
    LazyColumn(
        modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        contentPadding = PaddingValues(vertical = 8.dp)
    ) {
        item { Text("سلامت و Audit سیستم", style = MaterialTheme.typography.headlineSmall) }
        item {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp)) {
                    Text("Database", style = MaterialTheme.typography.titleMedium)
                    Text(if (state.snapshot != null) "OK" else "در انتظار اتصال")
                    Text("Master Agent: در دسترس")
                    Text("Approval Gate: فعال")
                }
            }
        }
        item { Text("آخرین رویدادهای Audit", style = MaterialTheme.typography.titleLarge) }
        if (state.snapshot?.audits.isNullOrEmpty()) {
            item { Text("هنوز رویداد Audit قابل نمایش ثبت نشده است.") }
        } else {
            items(state.snapshot!!.audits, key = { it.id }) { audit ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp)) {
                        Text(audit.action, style = MaterialTheme.typography.titleMedium)
                        Text(audit.actor + " → " + audit.target)
                        Text(audit.createdAt, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
        item {
            Button(onClick = vm::refresh, enabled = !state.busy, Modifier.fillMaxWidth()) {
                Text(if (state.busy) "در حال بررسی..." else "بررسی مجدد سلامت و Audit")
            }
        }
    }
}

@Composable
private fun ChatScreen(state: ir.saeit.admin.ui.AdminState, vm: MasterAgentViewModel, modifier: Modifier) {
    var input by remember { mutableStateOf("") }
    Column(modifier.fillMaxSize()) {
        LazyColumn(
            Modifier.weight(1f).fillMaxWidth().padding(horizontal = 12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
            contentPadding = PaddingValues(vertical = 12.dp)
        ) {
            item {
                Text("گفت‌وگوی مالک با Master Agent", style = MaterialTheme.typography.headlineSmall)
                Spacer(Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { vm.executeCommand("status") }, enabled = !state.busy) { Text("سلامت سیستم") }
                    OutlinedButton(onClick = { vm.executeCommand("evolution") }, enabled = !state.busy) { Text("چرخه تکامل") }
                    OutlinedButton(onClick = { vm.executeCommand("watchdog") }, enabled = !state.busy) { Text("نگهبان ۲۴/۷") }
                    OutlinedButton(onClick = { vm.executeCommand("performance") }, enabled = !state.busy) { Text("گزارش عملکرد") }
                }
            }
            items(state.items) { item ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp)) {
                        Text(if (item.role == "user") "مالک" else "Master Agent", style = MaterialTheme.typography.labelMedium)
                        Spacer(Modifier.height(4.dp))
                        Text(item.text)
                    }
                }
            }
            state.error?.let { item { Text(it, color = MaterialTheme.colorScheme.error) } }
        }
        Row(Modifier.fillMaxWidth().padding(12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(input, { input = it }, Modifier.weight(1f), placeholder = { Text("دستور یا پرسش...") })
            Button(onClick = { vm.send(input); input = "" }, enabled = input.isNotBlank() && !state.busy) { Text("ارسال") }
        }
    }
}
@Composable
private fun TaskScreen(state: ir.saeit.admin.ui.AdminState, vm: MasterAgentViewModel, modifier: Modifier) {
    LazyColumn(
        modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
        contentPadding = PaddingValues(vertical = 8.dp)
    ) {
        item { Text("مرکز Taskها", style = MaterialTheme.typography.headlineSmall) }
        item { Text("چرخه اجرا تحت کنترل Runtime و Governance است.") }
        if (state.tasks.isEmpty()) {
            item { Text("Task قابل نمایش وجود ندارد.") }
        } else {
            items(state.tasks, key = { it.id }) { task ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp)) {
                        Text("#${task.id} · ${task.action}", style = MaterialTheme.typography.titleMedium)
                        Text("Agent: ${task.agent}")
                        Text("وضعیت: ${task.status} · ریسک: ${task.risk}")
                        Text("تلاش: ${task.attempt}/${task.maxAttempts}")
                        if (task.status == "queued") {
                            Button(onClick = { vm.taskAction(task.id, "claim") }, enabled = !state.busy) { Text("Claim") }
                        }
                        if (task.status == "running") {
                            Text("Execution: " + task.executionId.take(12))
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Button(onClick = { vm.taskAction(task.id, "heartbeat", task.executionId) }, enabled = !state.busy) { Text("Heartbeat") }
                                Button(onClick = { vm.taskAction(task.id, "complete", task.executionId) }, enabled = !state.busy) { Text("Complete") }
                            }
                            OutlinedButton(onClick = { vm.taskAction(task.id, "fail", task.executionId) }, enabled = !state.busy) { Text("Fail") }
                        }
                    }
                }
            }
        }
        item {
            Button(onClick = vm::refresh, enabled = !state.busy, Modifier.fillMaxWidth()) {
                Text("به‌روزرسانی Taskها")
            }
        }
    }
}

@Composable
private fun OperationsScreen(state: ir.saeit.admin.ui.AdminState, vm: MasterAgentViewModel, modifier: Modifier) {
    val o = state.operations
    LazyColumn(modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp), contentPadding = PaddingValues(vertical = 8.dp)) {
        item { Text("مرکز عملیات زنده", style = MaterialTheme.typography.headlineSmall); Text("Timeline واقعی Robotها، Agentها، تکامل، Approval و رویدادها") }
        item { Text("Robot Runs", style = MaterialTheme.typography.titleLarge) }
        items(o?.runs ?: emptyList(), key = { it.id }) { r -> Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(12.dp)) { Text("#${r.id} · ${r.robot}", style = MaterialTheme.typography.titleMedium); Text("وضعیت: ${r.status}"); Text("شروع: ${r.startedAt}", style = MaterialTheme.typography.bodySmall); if (r.error.isNotBlank()) Text("خطا: ${r.error}", color = MaterialTheme.colorScheme.error) } } }
        item { Text("Agentها", style = MaterialTheme.typography.titleLarge) }
        items(o?.agents ?: emptyList(), key = { it.id }) { a -> Text("${a.name} · ${if (a.active) "فعال" else "غیرفعال"}") }
        item { Text("Evolution / Recovery", style = MaterialTheme.typography.titleLarge) }
        items(o?.evolution ?: emptyList(), key = { it.id }) { e -> Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(12.dp)) { Text("${e.action} · ${e.target}"); Text("${e.status} · ریسک ${e.risk}"); Text(e.createdAt, style = MaterialTheme.typography.bodySmall) } } }
        item { Text("Approval Gate: ${o?.approvals?.size ?: 0} مورد در انتظار", style = MaterialTheme.typography.titleLarge) }
        items(o?.approvals ?: emptyList(), key = { it.id }) { a -> Text("#${a.id} · ${a.action} · ${a.target} · ${a.risk}") }
        item { Text("Performance", style = MaterialTheme.typography.titleLarge) }
        items(o?.performance ?: emptyList(), key = { it.agentId }) { p -> Text("${p.agent}: موفق ${p.success} · خطا ${p.failed} · latency ${p.latencyMs}ms · کیفیت ${p.quality ?: "-"}") }
        item { Text("Ecosystem Events", style = MaterialTheme.typography.titleLarge) }
        items(o?.events ?: emptyList(), key = { it.id }) { e -> Text("${e.type} · ${e.actor} · ${e.createdAt}") }
        item { Button(onClick = vm::refresh, enabled = !state.busy, Modifier.fillMaxWidth()) { Text("به‌روزرسانی عملیات") } }
    }
}
