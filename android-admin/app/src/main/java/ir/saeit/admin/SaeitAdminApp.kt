package ir.saeit.admin

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ir.saeit.admin.api.SaeitApi
import ir.saeit.admin.ui.MasterAgentViewModel

@Composable
fun SaeitAdminApp() {
    var baseUrl by remember { mutableStateOf("https://zomorodmelal.ir") }
    var token by remember { mutableStateOf("") }
    var configured by remember { mutableStateOf(false) }

    if (!configured) {
        SetupScreen(baseUrl, token, { baseUrl = it }, { token = it }, { configured = true })
    } else {
        val vm = remember { MasterAgentViewModel(SaeitApi(baseUrl) { token }) }
        MasterAgentScreen(vm)
    }
}

@Composable
private fun SetupScreen(baseUrl: String, token: String, onBaseUrl: (String) -> Unit, onToken: (String) -> Unit, onContinue: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center) {
        Text("Saeit Admin", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(8.dp))
        Text("اتصال امن به API پروژه Saeit")
        Spacer(Modifier.height(20.dp))
        OutlinedTextField(baseUrl, onBaseUrl, Modifier.fillMaxWidth(), label = { Text("API Base URL") }, singleLine = true)
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(token, onToken, Modifier.fillMaxWidth(), label = { Text("Bearer Token") }, singleLine = true)
        Spacer(Modifier.height(20.dp))
        Button(onClick = onContinue, enabled = baseUrl.startsWith("https://"), modifier = Modifier.fillMaxWidth()) { Text("ورود به پنل") }
    }
}

@Composable
private fun MasterAgentScreen(vm: MasterAgentViewModel) {
    val state by vm.state.collectAsState()
    var input by remember { mutableStateOf("") }
    val listState = rememberLazyListState()
    LaunchedEffect(state.items.size) {
        if (state.items.isNotEmpty()) listState.animateScrollToItem(state.items.lastIndex)
    }
    Column(Modifier.fillMaxSize()) {
        TopAppBar(title = { Text("Master Agent") })
        LazyColumn(Modifier.weight(1f).fillMaxWidth().padding(horizontal = 12.dp), state = listState, verticalArrangement = Arrangement.spacedBy(8.dp), contentPadding = PaddingValues(vertical = 12.dp)) {
            items(state.items) { item ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp)) {
                        Text(if (item.role == "user") "مالک" else "Master Agent", style = MaterialTheme.typography.labelMedium)
                        Spacer(Modifier.height(4.dp))
                        Text(item.text)
                    }
                }
            }
            if (state.busy) item { CircularProgressIndicator(Modifier.size(24.dp)) }
        }
        state.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(horizontal = 12.dp)) }
        Row(Modifier.fillMaxWidth().padding(12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(input, { input = it }, Modifier.weight(1f), placeholder = { Text("دستور به Master Agent...") })
            Button(onClick = { vm.send(input); input = "" }, enabled = input.isNotBlank() && !state.busy) { Text("ارسال") }
        }
    }
}