package de.lokzeitleiste.app.portal

import android.Manifest
import android.app.*
import android.content.Intent
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.IBinder
import android.os.Looper
import de.lokzeitleiste.app.TfPortalActivity
import org.json.JSONObject

/** User-started location foreground service: keeps recording with a locked screen. */
class GpsRecordingService : Service(), LocationListener {
    private lateinit var locations: LocationManager
    private lateinit var store: GpsTrackStore
    private var count=0
    private var first=0L
    private var last=0L
    override fun onCreate() {
        super.onCreate();store=GpsTrackStore(this);locations=getSystemService(LocationManager::class.java)
        getSystemService(NotificationManager::class.java).createNotificationChannel(NotificationChannel("train-gps", "GPS-Zugfahrt", NotificationManager.IMPORTANCE_LOW))
    }
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val key=intent?.getStringExtra("key") ?: return START_NOT_STICKY
        if(currentKey!=null && currentKey!=key) { stopSelf(startId);return START_NOT_STICKY }
        currentKey=key
        val saved=store.read(key);count=saved.length();first=if(count>0)saved.getJSONObject(0).getLong("t") else 0L;last=if(count>0)saved.getJSONObject(count-1).getLong("t") else 0L
        val open=PendingIntent.getActivity(this,0,Intent(this,TfPortalActivity::class.java),PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val notification=Notification.Builder(this,"train-gps").setSmallIcon(android.R.drawable.ic_menu_mylocation).setContentTitle("LokZeitleiste · GPS-Zugfahrt").setContentText("Aufzeichnung läuft. Zum Beenden die App öffnen.").setContentIntent(open).setOngoing(true).build()
        startForeground(71,notification)
        if(checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)!=PackageManager.PERMISSION_GRANTED || !locations.isProviderEnabled(LocationManager.GPS_PROVIDER)) { stopSelf();return START_NOT_STICKY }
        try { locations.requestLocationUpdates(LocationManager.GPS_PROVIDER,5000L,0f,this,Looper.getMainLooper()) }
        catch(_:SecurityException) { stopSelf() }
        return START_NOT_STICKY
    }
    override fun onLocationChanged(location: Location) {
        val key=currentKey ?: return
        val t=location.time
        if(t<=last || !location.hasAccuracy() || location.accuracy>100000) return
        if(count>=20000 || first>0 && t-first>48*3600000L) { stopSelf();return }
        val point=JSONObject().put("t",t).put("lat",location.latitude).put("lon",location.longitude).put("accuracy",location.accuracy.toDouble())
            .put("speed",if(location.hasSpeed() && location.speed>=0 && location.speed<=200) location.speed.toDouble() else JSONObject.NULL)
        try { store.append(key,point);last=t;if(first==0L)first=t;count++ } catch(_:Exception) { stopSelf() }
    }
    @Suppress("DEPRECATION")
    override fun onStatusChanged(provider:String?,status:Int,extras:android.os.Bundle?) { }
    override fun onProviderEnabled(provider:String) { }
    override fun onProviderDisabled(provider:String) { }
    override fun onDestroy() { runCatching { locations.removeUpdates(this) };currentKey=null;stopForeground(STOP_FOREGROUND_REMOVE);super.onDestroy() }
    override fun onBind(intent: Intent?): IBinder? = null
    companion object { @Volatile var currentKey: String?=null }
}
