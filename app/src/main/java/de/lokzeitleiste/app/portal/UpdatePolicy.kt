package de.lokzeitleiste.app.portal
import java.net.URI
object UpdatePolicy {
    fun releaseVersion(tag:String):Int? {
        val match=Regex("android-test-([1-9][0-9]*)").matchEntire(tag)?:return null
        val number=match.groupValues[1].toLongOrNull()?:return null
        return if(number<=2099900000L)(100000L+number).toInt() else null
    }
    fun allowedUrl(value:String):Boolean=runCatching {
        val uri=URI(value)
        uri.scheme=="https" && uri.rawUserInfo==null && uri.port in listOf(-1,443) && uri.host in listOf("api.github.com","github.com","release-assets.githubusercontent.com","objects.githubusercontent.com")
    }.getOrDefault(false)
}
