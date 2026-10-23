package de.lokzeitleiste.app.portal

import android.app.AlertDialog
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.PackageInfo
import android.net.Uri
import android.os.Build
import android.provider.Settings
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.core.content.FileProvider
import androidx.lifecycle.lifecycleScope
import de.lokzeitleiste.app.BuildConfig
import kotlinx.coroutines.*
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/** Public GitHub test releases only. Android always handles the final installation consent. */
class PortalUpdater(private val activity:ComponentActivity) {
    private val prefs=activity.getSharedPreferences("portal_updates",0)
    private val directory=File(activity.cacheDir,"updates").apply { mkdirs() }
    private var checking=false
    private var offered=false
    private var awaitingSettings=false
    private var pending:File?=null
    private fun message(value:String) { Toast.makeText(activity,value,Toast.LENGTH_LONG).show() }
    fun resume() {
        if(GpsRecordingService.currentKey!=null)return
        if(awaitingSettings) { awaitingSettings=false;if(activity.packageManager.canRequestPackageInstalls())pending?.let { install(it) };return }
        check(false)
    }
    fun check(manual:Boolean) {
        if(GpsRecordingService.currentKey!=null) { if(manual)message("Bitte zuerst die GPS-Aufzeichnung beenden.");return }
        if(checking)return
        val filename=prefs.getString("pending",null)
        if(filename!=null && filename.matches(Regex("update-[0-9]+\\.apk"))) {
            val file=File(directory,filename)
            if(file.exists() && runCatching { verified(file) }.getOrDefault(false)) { if(manual||!offered)offer(file);return }
            file.delete();prefs.edit().remove("pending").apply()
        }
        if(!manual && System.currentTimeMillis()-prefs.getLong("checked",0)<6*3600000L)return
        prefs.edit().putLong("checked",System.currentTimeMillis()).apply();checking=true
        activity.lifecycleScope.launch {
            try {
                val apk=withContext(Dispatchers.IO) { findAndDownload() }
                if(apk==null) { if(manual)message("Keine neuere Testversion verfügbar.") }
                else { prefs.edit().putString("pending",apk.name).apply();if(GpsRecordingService.currentKey==null)offer(apk) }
            } catch(error:Exception) { if(manual)message("Update-Prüfung fehlgeschlagen: "+(error.message?:"Keine Verbindung")) }
            finally { checking=false }
        }
    }
    private fun connect(value:String):HttpURLConnection {
        var next=value
        repeat(6) {
            require(UpdatePolicy.allowedUrl(next)) { "Ungültige Update-Adresse" }
            val connection=URL(next).openConnection() as HttpURLConnection
            connection.instanceFollowRedirects=false;connection.connectTimeout=15000;connection.readTimeout=60000
            connection.setRequestProperty("User-Agent","LokZeitleiste-Android/${BuildConfig.VERSION_NAME}")
            if(connection.responseCode in listOf(301,302,303,307,308)) {
                val location=connection.getHeaderField("Location")?:error("Update-Weiterleitung fehlt")
                next=URL(URL(next),location).toString();connection.disconnect()
            } else { val code=connection.responseCode;if(code!=200){connection.disconnect();error("GitHub HTTP $code")};return connection }
        }
        error("Zu viele Update-Weiterleitungen")
    }
    private fun json(url:String):String {
        val connection=connect(url)
        return try { connection.inputStream.use { input->
            val output=java.io.ByteArrayOutputStream();val buffer=ByteArray(8192)
            while(true){val count=input.read(buffer);if(count<0)break;require(output.size()+count<=2*1024*1024);output.write(buffer,0,count)}
            String(output.toByteArray(),Charsets.UTF_8)
        } } finally { connection.disconnect() }
    }
    private fun findAndDownload():File? {
        val releases=JSONArray(json("https://api.github.com/repos/omueller369/LokZeitleiste/releases?per_page=20"))
        var metadataUrl="";var apkUrl="";var latest=BuildConfig.VERSION_CODE
        for(i in 0 until releases.length()) {
            val release=releases.getJSONObject(i)
            if(release.optBoolean("draft"))continue
            val code=UpdatePolicy.releaseVersion(release.optString("tag_name"))?:continue
            if(code<=latest)continue
            val assets=release.getJSONArray("assets");var candidateMetadata="";var candidateApk=""
            for(n in 0 until assets.length()) { val asset=assets.getJSONObject(n);when(asset.optString("name")){"update.json"->candidateMetadata=asset.getString("browser_download_url");"LokZeitleiste-TF-Portal.apk"->candidateApk=asset.getString("browser_download_url")} }
            if(candidateMetadata.isBlank()||candidateApk.isBlank())continue
            latest=code;metadataUrl=candidateMetadata;apkUrl=candidateApk
        }
        if(metadataUrl.isBlank())return null
        val metadata=JSONObject(json(metadataUrl))
        require(metadata.optString("application_id")==BuildConfig.APPLICATION_ID && metadata.getInt("version_code")==latest)
        require(metadata.getString("sha256").matches(Regex("[a-f0-9]{64}")))
        val file=File(directory,"update-$latest.apk");val temporary=File(directory,"update.part")
        val connection=connect(apkUrl)
        try {
            val digest=MessageDigest.getInstance("SHA-256");var size=0L
            connection.inputStream.use { input->temporary.outputStream().use { output->val buffer=ByteArray(65536);while(true){val count=input.read(buffer);if(count<0)break;size+=count;require(size<=150*1024*1024) { "APK zu groß" };digest.update(buffer,0,count);output.write(buffer,0,count)} } }
            val hash=digest.digest().joinToString("") { "%02x".format(it) };require(hash==metadata.getString("sha256")) { "APK-Prüfsumme stimmt nicht" }
            require(verified(temporary,latest)) { "Paketname, Signatur oder Versionsnummer passt nicht zur installierten App" }
            if(file.exists())file.delete();require(temporary.renameTo(file));return file
        } finally { connection.disconnect();temporary.delete() }
    }
    @Suppress("DEPRECATION")
    private fun certificates(info:PackageInfo):Set<String> {
        val signatures=if(Build.VERSION.SDK_INT>=28)info.signingInfo?.apkContentsSigners else info.signatures
        return signatures.orEmpty().map { signature->MessageDigest.getInstance("SHA-256").digest(signature.toByteArray()).joinToString(""){"%02x".format(it)} }.toSet()
    }
    @Suppress("DEPRECATION")
    private fun verified(file:File,expected:Int?=null):Boolean {
        val flags=if(Build.VERSION.SDK_INT>=28)PackageManager.GET_SIGNING_CERTIFICATES else PackageManager.GET_SIGNATURES
        val installed=activity.packageManager.getPackageInfo(activity.packageName,flags)
        val apk=activity.packageManager.getPackageArchiveInfo(file.absolutePath,flags) ?: return false
        val code=if(Build.VERSION.SDK_INT>=28)apk.longVersionCode else apk.versionCode.toLong()
        return apk.packageName==activity.packageName && code>BuildConfig.VERSION_CODE && (expected==null||code==expected.toLong()) && certificates(apk).isNotEmpty() && certificates(apk)==certificates(installed)
    }
    private fun offer(file:File) {
        if(activity.isFinishing||activity.isDestroyed)return
        pending=file;offered=true
        AlertDialog.Builder(activity).setTitle("Neue TF-Portal-Testversion").setMessage("Die neue Version ist heruntergeladen und geprüft. Jetzt das Android-Update öffnen? Ihre App-Daten bleiben bei einem regulären Update erhalten.")
            .setPositiveButton("Update installieren") { _,_->install(file) }.setNegativeButton("Später",null).show()
    }
    private fun install(file:File) {
        if(GpsRecordingService.currentKey!=null){message("Bitte zuerst die GPS-Aufzeichnung beenden.");return}
        if(!verified(file)){message("Update ist nicht für diese Installation geeignet.");return}
        if(!activity.packageManager.canRequestPackageInstalls()) {
            awaitingSettings=true;pending=file
            AlertDialog.Builder(activity).setTitle("App-Updates erlauben").setMessage("Aktivieren Sie für LokZeitleiste „Aus dieser Quelle zulassen“. Danach zurückkehren und die Installation bestätigen.")
                .setPositiveButton("Einstellungen") { _,_->activity.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,Uri.parse("package:"+activity.packageName))) }.setNegativeButton("Abbrechen") { _,_->awaitingSettings=false }.show();return
        }
        val uri=FileProvider.getUriForFile(activity,activity.packageName+".updates",file)
        runCatching { activity.startActivity(Intent(Intent.ACTION_VIEW).setDataAndType(uri,"application/vnd.android.package-archive").addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)) }.onFailure { message("Android-Paketinstallation konnte nicht geöffnet werden.") }
    }
}
