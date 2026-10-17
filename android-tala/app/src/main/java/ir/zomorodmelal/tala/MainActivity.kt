package ir.zomorodmelal.tala

import android.content.ActivityNotFoundException
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.webkit.CookieManager
import android.webkit.SafeBrowsingResponse
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.viewinterop.AndroidView

private const val TALA_URL = "https://zomorodmelal.ir/tala/"

class MainActivity : ComponentActivity() {
    private var siteView: WebView? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = Color.rgb(17, 16, 14)
        window.navigationBarColor = Color.rgb(17, 16, 14)
        window.decorView.systemUiVisibility = 0

        val canGoBack = mutableStateOf(false)
        setContent {
            MaterialTheme {
                BackHandler(enabled = canGoBack.value) {
                    siteView?.goBack()
                    canGoBack.value = siteView?.canGoBack() == true
                }
                Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    AndroidView(
                        modifier = Modifier.fillMaxSize(),
                        factory = { context ->
                            WebView(context).apply {
                                setBackgroundColor(Color.rgb(17, 16, 14))
                                importantForAutofill = View.IMPORTANT_FOR_AUTOFILL_NO
                                settings.apply {
                                    javaScriptEnabled = true
                                    domStorageEnabled = true
                                    databaseEnabled = true
                                    cacheMode = WebSettings.LOAD_DEFAULT
                                    mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
                                    allowFileAccess = false
                                    allowContentAccess = false
                                    javaScriptCanOpenWindowsAutomatically = false
                                    setSupportMultipleWindows(false)
                                    builtInZoomControls = false
                                    displayZoomControls = false
                                    setSupportZoom(false)
                                }
                                CookieManager.getInstance().setAcceptThirdPartyCookies(this, false)
                                webViewClient = object : WebViewClient() {
                                    override fun shouldOverrideUrlLoading(
                                        view: WebView,
                                        request: WebResourceRequest
                                    ): Boolean {
                                        if (!request.isForMainFrame) return false
                                        val uri = request.url
                                        if (isTalaPage(uri)) return false
                                        if (uri.scheme == "https" || uri.scheme == "http") {
                                            openExternal(uri)
                                        } else {
                                            Toast.makeText(
                                                this@MainActivity,
                                                getString(R.string.scope_error),
                                                Toast.LENGTH_SHORT
                                            ).show()
                                        }
                                        return true
                                    }

                                    override fun onPageFinished(view: WebView, url: String) {
                                        canGoBack.value = view.canGoBack()
                                    }

                                    override fun onReceivedError(
                                        view: WebView,
                                        request: WebResourceRequest,
                                        error: WebResourceError
                                    ) {
                                        if (request.isForMainFrame) {
                                            canGoBack.value = view.canGoBack()
                                        }
                                    }
                                }
                                webChromeClient = WebChromeClient()
                                siteView = this
                                loadUrl(TALA_URL)
                            }
                        },
                        update = { view ->
                            if (siteView !== view) siteView = view
                        }
                    )
                }
            }
        }
    }

    private fun isTalaPage(uri: Uri): Boolean {
        val allowedPort = uri.port == -1 || uri.port == 443
        val allowedPath = uri.path == "/tala" || uri.path?.startsWith("/tala/") == true
        return uri.scheme == "https" &&
            uri.host.equals("zomorodmelal.ir", ignoreCase = true) &&
            allowedPort &&
            allowedPath
    }

    private fun openExternal(uri: Uri) {
        try {
            startActivity(Intent(Intent.ACTION_VIEW, uri))
        } catch (_: ActivityNotFoundException) {
            Toast.makeText(this, getString(R.string.scope_error), Toast.LENGTH_SHORT).show()
        }
    }

    override fun onResume() {
        super.onResume()
        siteView?.onResume()
    }

    override fun onPause() {
        siteView?.onPause()
        super.onPause()
    }

    override fun onDestroy() {
        siteView?.apply {
            stopLoading()
            loadUrl("about:blank")
            clearHistory()
            removeAllViews()
            destroy()
        }
        siteView = null
        super.onDestroy()
    }
}
