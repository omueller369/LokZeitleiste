package de.lokzeitleiste.app

import android.Manifest
import android.annotation.SuppressLint
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.webkit.*
import android.widget.*
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.lifecycle.lifecycleScope
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import androidx.webkit.JavaScriptReplyProxy
import de.lokzeitleiste.app.network.*
import de.lokzeitleiste.app.portal.*
import kotlinx.coroutines.*
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayInputStream
import java.io.OutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID

class TfPortalActivity : ComponentActivity() {
    private lateinit var web: WebView
    private lateinit var policy: PortalPolicy
    private lateinit var store: GpsTrackStore
    private lateinit var updater:PortalUpdater
    private var session=JSONObject()
    private var fileCallback: ValueCallback<Array<Uri>>?=null
    private var pendingGps: Pair<JSONObject,JavaScriptReplyProxy>?=null
    private var pendingDownload: String?=null
    private var pendingExport: Pair<String,JavaScriptReplyProxy>?=null
    private var exportStream: OutputStream?=null
    private var exportId: String?=null
    private var exportBytes=0L
    private var leaving=false
    private val toolButtons=mutableListOf<Pair<Button,String>>()
    private val filePicker=registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        fileCallback?.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(result.resultCode,result.data));fileCallback=null
    }
    private val locationPermission=registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {
        val job=pendingGps;pendingGps=null
        if(job!=null) if(checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)==PackageManager.PERMISSION_GRANTED) startGps(job.first,job.second)
        else reply(job.second,job.first,false,"Präziser Standort wurde nicht erlaubt.")
    }
    private val saveFile=registerForActivityResult(ActivityResultContracts.CreateDocument("*/*")) { uri ->
        val export=pendingExport;pendingExport=null
        if(export!=null) {
            if(uri==null) reply(export.second,JSONObject().put("id",export.first),false,"Speichern abgebrochen.")
            else try { exportStream=contentResolver.openOutputStream(uri,"wt");require(exportStream!=null);exportId=UUID.randomUUID().toString();exportBytes=0;reply(export.second,JSONObject().put("id",export.first),true,JSONObject().put("export_id",exportId)) }
            catch(error:Exception) { reply(export.second,JSONObject().put("id",export.first),false,error.message?:"Datei konnte nicht gespeichert werden.") }
        } else {
            val url=pendingDownload;pendingDownload=null
            if(uri!=null && url!=null) download(url,uri)
        }
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if(TokenVault.username(this).isBlank()) { login();return }
        try { policy=PortalPolicy(ApiClient.base()) } catch(error:Exception) { toast(error.message?:"Serveradresse (HTTPS) prüfen.");finish();return }
        store=GpsTrackStore(this)
        LanguageRuntime.initialize(this)
        LanguageRuntime.code=getSharedPreferences("lokzeitleiste_language",MODE_PRIVATE).getString("language","de")?:"de"
        val layout=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL;fitsSystemWindows=true }
        val tools=LinearLayout(this)
        fun tool(label:String,action:()->Unit) { tools.addView(Button(this).apply { text=LanguageRuntime.translate(label,LanguageRuntime.code);toolButtons.add(this to label);setOnClickListener { action() } },LinearLayout.LayoutParams(0,LinearLayout.LayoutParams.WRAP_CONTENT,1f)) }
        tool("TF Portal") { navigateHome() }
        tool("Bisherige Erfassungen") { if(GpsRecordingService.currentKey!=null) toast("Bitte zuerst die GPS-Aufzeichnung beenden.") else { startActivity(Intent(this,LegacyActivity::class.java));finish() } }
        tool("Abmelden") { logout() }
        web=WebView(this);layout.addView(tools);layout.addView(web,LinearLayout.LayoutParams(-1,0,1f));setContentView(layout)
        updater=PortalUpdater(this)
        tool("Update") { updater.check(true) }
        configureWebView()
        onBackPressedDispatcher.addCallback(this,object:OnBackPressedCallback(true) { override fun handleOnBackPressed() {
            if(GpsRecordingService.currentKey!=null) { toast("Bitte zuerst die GPS-Aufzeichnung beenden.");return }
            if(web.canGoBack())web.goBack() else finish()
        } })
        lifecycleScope.launch { initialize() }
    }
    private fun toast(message:String) {
        val notice=Toast.makeText(this,LanguageRuntime.translate(message,LanguageRuntime.code),Toast.LENGTH_LONG)
        notice.show()
        if(message.contains("GPS",ignoreCase=true) || message.contains("HTTPS",ignoreCase=true)) {
            Handler(Looper.getMainLooper()).postDelayed({ notice.cancel() },3000L)
        }
    }
    private fun navigateHome() { if(GpsRecordingService.currentKey!=null)toast("Bitte zuerst die GPS-Aufzeichnung beenden.") else web.loadUrl(policy.origin+"/tf") }
    private fun login() { startActivity(Intent(this,MainActivity::class.java));finish() }
    private fun logout(force:Boolean=false) {
        if(GpsRecordingService.currentKey!=null) { if(!force){toast("Bitte zuerst die GPS-Aufzeichnung beenden.");return};stopService(Intent(this,GpsRecordingService::class.java));GpsRecordingService.currentKey=null }
        if(leaving)return;leaving=true
        val token=TokenVault.token(this)
        lifecycleScope.launch {
            if(token!=null) runCatching { withTimeout(5000) { ApiClient.logout(token) } }
            TokenVault.clear(this@TfPortalActivity)
            CookieManager.getInstance().removeAllCookies { CookieManager.getInstance().flush();login() }
        }
    }
    private suspend fun initialize() {
        val token=TokenVault.token(this) ?: return login()
        val username=TokenVault.username(this)
        val prefs=getSharedPreferences("portal_identity",MODE_PRIVATE)
        val cacheKey=policy.origin+"|"+username
        try {
            val account=ApiClient.identity(token)
            require(account.optString("role")=="tf") { "TF Portal ist nur für Triebfahrzeugführer verfügbar." }
            val profile=if(account.optBoolean("password_change_required")) JSONObject() else ApiClient.portalIdentity(token)
            session=JSONObject().put("account",account).put("profile",profile).put("username",username)
            prefs.edit().putString(cacheKey,session.toString()).apply()
        } catch(_:AuthenticationRequired) { logout(true);return }
        catch(error:Exception) {
            val cached=prefs.getString(cacheKey,null)
            if(cached==null) { toast(error.message?:"Server nicht erreichbar. Bitte zunächst online anmelden.");finish();return }
            // Only transport failures permit offline access; server rejections remain authoritative.
            if(error !is java.io.IOException) { toast(error.message?:"Zugriff verweigert.");finish();return }
            session=JSONObject(cached)
        }
        val secure=if(policy.origin.startsWith("https:")) "; Secure" else ""
        CookieManager.getInstance().setAcceptCookie(true)
        CookieManager.getInstance().setCookie(policy.origin,"admin_session=$token; Path=/; HttpOnly; SameSite=Strict; Max-Age=31536000$secure") {
            CookieManager.getInstance().flush()
            web.loadUrl(policy.origin+if(session.getJSONObject("account").optBoolean("password_change_required")) "/account" else if(GpsRecordingService.currentKey!=null) "/tf/arbeitsbericht" else "/tf")
        }
    }
    @SuppressLint("SetJavaScriptEnabled")
    private fun configureWebView() {
        web.settings.apply { javaScriptEnabled=true;domStorageEnabled=true;allowFileAccess=false;allowContentAccess=true;mixedContentMode=WebSettings.MIXED_CONTENT_NEVER_ALLOW;setSupportMultipleWindows(false);javaScriptCanOpenWindowsAutomatically=false;setGeolocationEnabled(false);userAgentString += " LokZeitleisteAndroid/0.11" }
        CookieManager.getInstance().setAcceptThirdPartyCookies(web,false)
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG)
        if(WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) {
            WebViewCompat.addWebMessageListener(web,"NativePortal",setOf(policy.origin)) { _,message,origin,isMainFrame,proxy ->
                if(isMainFrame && policy.sameOrigin(origin.toString()) && policy.sameOrigin(web.url.orEmpty())) {
                    try { require((message.data?.length?:0)<150000);handle(JSONObject(message.data?:"{}"),proxy) }
                    catch(error:Exception) { toast(error.message?:"App-Anfrage fehlgeschlagen.") }
                }
            }
        } else toast("Android System WebView aktualisieren, um GPS und GPX-Export zu verwenden.")
        web.webViewClient=object:WebViewClient() {
            override fun shouldOverrideUrlLoading(view:WebView,request:WebResourceRequest):Boolean {
                val value=request.url.toString()
                if(policy.sameOrigin(value)) {
                    if(GpsRecordingService.currentKey!=null && request.isForMainFrame) { toast("Bitte zuerst die GPS-Aufzeichnung beenden.");return true }
                    return false
                }
                if(request.isForMainFrame && request.hasGesture() && request.url.scheme in listOf("https","http","tel","mailto")) runCatching { startActivity(Intent(Intent.ACTION_VIEW,request.url)) }
                return true
            }
            override fun shouldInterceptRequest(view:WebView,request:WebResourceRequest):WebResourceResponse? {
                if(!policy.sameOrigin(request.url.toString())) return WebResourceResponse("text/plain","UTF-8",403,"Forbidden",emptyMap(),ByteArrayInputStream(byteArrayOf()))
                if(request.method!="GET")return null
                if(request.url.path=="/locales/catalog.json")return WebResourceResponse("application/json","UTF-8",assets.open("catalog.json"))
                val name=policy.asset(request.url.path.orEmpty()) ?: return null
                return try {
                    var bytes=assets.open("tf-portal/$name").use { it.readBytes() }
                    if(name.endsWith(".html")) bytes=String(bytes,Charsets.UTF_8).replace("<head>","<head><script src=\"/android-portal.js\"></script>").toByteArray(Charsets.UTF_8)
                    val mime=when { name.endsWith(".html")->"text/html";name.endsWith(".css")->"text/css";else->"text/javascript" }
                    WebResourceResponse(mime,"UTF-8",200,"OK",mapOf("Cache-Control" to "no-store","Content-Security-Policy" to "frame-src 'none'; object-src 'none'"),ByteArrayInputStream(bytes))
                } catch(_:Exception) { WebResourceResponse("text/plain","UTF-8",500,"Missing portal asset",emptyMap(),ByteArrayInputStream(byteArrayOf())) }
            }
            override fun onReceivedSslError(view:WebView,handler:SslErrorHandler,error:android.net.http.SslError) { handler.cancel();toast("Das HTTPS-Zertifikat des Servers ist ungültig.") }
        }
        web.webChromeClient=object:WebChromeClient() {
            override fun onJsAlert(view:WebView,url:String,message:String,result:JsResult):Boolean { android.app.AlertDialog.Builder(this@TfPortalActivity).setMessage(message).setPositiveButton(android.R.string.ok) { _,_->result.confirm() }.setOnCancelListener { result.cancel() }.show();return true }
            override fun onJsConfirm(view:WebView,url:String,message:String,result:JsResult):Boolean { android.app.AlertDialog.Builder(this@TfPortalActivity).setMessage(message).setPositiveButton(android.R.string.ok) { _,_->result.confirm() }.setNegativeButton(android.R.string.cancel) { _,_->result.cancel() }.setOnCancelListener { result.cancel() }.show();return true }
            override fun onShowFileChooser(view:WebView,callback:ValueCallback<Array<Uri>>,params:FileChooserParams):Boolean {
                fileCallback?.onReceiveValue(null);fileCallback=callback
                val intent=Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*").putExtra(Intent.EXTRA_ALLOW_MULTIPLE,params.mode==FileChooserParams.MODE_OPEN_MULTIPLE)
                val types=params.acceptTypes.orEmpty().filter { it.contains('/') }.toTypedArray();if(types.isNotEmpty())intent.putExtra(Intent.EXTRA_MIME_TYPES,types)
                try { filePicker.launch(intent) } catch(_:Exception) { fileCallback?.onReceiveValue(null);fileCallback=null }
                return true
            }
        }
        web.setDownloadListener { url,_,disposition,mime,_->
            if(policy.sameOrigin(url) && pendingDownload==null && pendingExport==null && exportStream==null) { pendingDownload=url;saveFile.launch(URLUtil.guessFileName(url,disposition,mime)) }
            else toast("Download kann nicht geöffnet werden.")
        }
    }
    private fun reply(proxy:JavaScriptReplyProxy,request:JSONObject,ok:Boolean,value:Any) {
        proxy.postMessage(JSONObject().put("id",request.optString("id")).put("ok",ok).put(if(ok)"value" else "error",value).toString())
    }
    private fun trackKey(request:JSONObject):String {
        val key=request.getString("key");require(key.startsWith(session.getJSONObject("profile").getInt("id").toString()+"."));require(key.matches(Regex("[0-9]+\\.[A-Za-z0-9-]{1,100}")));return key
    }
    private fun handle(request:JSONObject,proxy:JavaScriptReplyProxy) {
        try {
            when(request.getString("method")) {
                "session" -> reply(proxy,request,true,session)
                "language" -> {
                    val language=request.getString("language");require(language in LanguageRuntime.codes);LanguageRuntime.code=language
                    getSharedPreferences("lokzeitleiste_language",MODE_PRIVATE).edit().putString("language",language).apply()
                    for((button,label)in toolButtons)button.text=LanguageRuntime.translate(label,language)
                    reply(proxy,request,true,JSONObject())
                }
                "expired" -> { reply(proxy,request,true,JSONObject());logout(true) }
                "gps.start" -> {
                    require(Uri.parse(web.url).path=="/tf/arbeitsbericht")
                    trackKey(request)
                    if(checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)!=PackageManager.PERMISSION_GRANTED) {
                        require(pendingGps==null);pendingGps=request to proxy
                        val permissions=mutableListOf(Manifest.permission.ACCESS_FINE_LOCATION,Manifest.permission.ACCESS_COARSE_LOCATION)
                        if(Build.VERSION.SDK_INT>=33) permissions.add(Manifest.permission.POST_NOTIFICATIONS)
                        locationPermission.launch(permissions.toTypedArray())
                    } else startGps(request,proxy)
                }
                "gps.snapshot" -> {
                    val key=trackKey(request);val after=request.optLong("after",0);val points=store.read(key);val result=JSONArray()
                    for(i in 0 until points.length()) if(points.getJSONObject(i).getLong("t")>after && result.length()<1000)result.put(points.getJSONObject(i))
                    reply(proxy,request,true,JSONObject().put("points",result).put("running",GpsRecordingService.currentKey==key))
                }
                "gps.stop" -> { val key=trackKey(request);if(GpsRecordingService.currentKey==key){stopService(Intent(this,GpsRecordingService::class.java));GpsRecordingService.currentKey=null};reply(proxy,request,true,JSONObject()) }
                "gps.erase" -> { val key=trackKey(request);require(GpsRecordingService.currentKey!=key);store.erase(key);reply(proxy,request,true,JSONObject()) }
                "export.start" -> {
                    require(pendingDownload==null && pendingExport==null && exportStream==null)
                    pendingExport=request.getString("id") to proxy
                    saveFile.launch(request.optString("name","Dokument").replace(Regex("[/\\\\\\x00-\\x1f]"),"_").take(180))
                }
                "export.chunk" -> {
                    require(request.getString("export_id")==exportId && exportStream!=null)
                    val bytes=android.util.Base64.decode(request.getString("data"),android.util.Base64.DEFAULT)
                    require(bytes.size<=65536 && exportBytes+bytes.size<=32*1024*1024);exportStream!!.write(bytes);exportBytes+=bytes.size;reply(proxy,request,true,JSONObject())
                }
                "export.finish" -> { require(request.getString("export_id")==exportId);exportStream?.close();exportStream=null;exportId=null;reply(proxy,request,true,JSONObject()) }
                else -> reply(proxy,request,false,"Unbekannte App-Anfrage.")
            }
        } catch(error:Exception) { reply(proxy,request,false,error.message?:"App-Anfrage fehlgeschlagen.") }
    }
    private fun startGps(request:JSONObject,proxy:JavaScriptReplyProxy) {
        try {
            val key=trackKey(request);require(GpsRecordingService.currentKey==null || GpsRecordingService.currentKey==key) { "Eine andere GPS-Aufzeichnung läuft bereits." }
            require(getSystemService(android.location.LocationManager::class.java).isProviderEnabled(android.location.LocationManager.GPS_PROVIDER)) { "GPS in den Android-Einstellungen einschalten." }
            if(GpsRecordingService.currentKey==null) { store.begin(key,request.optBoolean("reset"));GpsRecordingService.currentKey=key;startForegroundService(Intent(this,GpsRecordingService::class.java).putExtra("key",key)) }
            reply(proxy,request,true,JSONObject())
        } catch(error:Exception) { GpsRecordingService.currentKey=null;reply(proxy,request,false,error.message?:"GPS konnte nicht gestartet werden.") }
    }
    private fun download(url:String,destination:Uri) {
        val cookie=CookieManager.getInstance().getCookie(policy.origin)
        lifecycleScope.launch {
            try { val mime=withContext(Dispatchers.IO) {
                require(policy.sameOrigin(url));val connection=URL(url).openConnection() as HttpURLConnection
                try { connection.instanceFollowRedirects=false;connection.connectTimeout=15000;connection.readTimeout=30000;connection.setRequestProperty("Cookie",cookie.orEmpty());require(connection.responseCode in 200..299) { "Download fehlgeschlagen (${connection.responseCode})." }
                    contentResolver.openOutputStream(destination,"wt")!!.use { output->connection.inputStream.use { input->input.copyTo(output) } }
                    connection.contentType?.substringBefore(';')?:"application/octet-stream"
                } finally { connection.disconnect() }
            };android.app.AlertDialog.Builder(this@TfPortalActivity).setMessage(LanguageRuntime.translate("Dokument gespeichert.",LanguageRuntime.code)).setPositiveButton(LanguageRuntime.translate("Ansehen",LanguageRuntime.code)) { _,_->
                    runCatching { startActivity(Intent(Intent.ACTION_VIEW).setDataAndType(destination,mime).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)) }.onFailure { toast("Keine passende App zum Öffnen vorhanden.") }
                }.setNegativeButton(android.R.string.cancel,null).show() } catch(error:Exception) { toast(error.message?:"Download fehlgeschlagen.") }
        }
    }
    override fun onResume() { super.onResume();if(::updater.isInitialized)updater.resume() }
    override fun onDestroy() { fileCallback?.onReceiveValue(null);exportStream?.close();if(::web.isInitialized){web.stopLoading();web.destroy()};super.onDestroy() }
}
