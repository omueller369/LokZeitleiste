package de.lokzeitleiste.app.portal

import java.net.URI

/** Exact origin comparison, not host suffix matching; bearer/cookies never leave this origin. */
class PortalPolicy(base: String) {
    private val root = URI(base)
    val origin: String = "${root.scheme}://${root.rawAuthority}"
    init { require(root.scheme in listOf("https", "http") && root.host != null && root.rawUserInfo == null && root.rawQuery == null && root.rawFragment == null && root.path.orEmpty() in listOf("", "/")) }
    fun sameOrigin(value: String): Boolean = runCatching {
        val uri = URI(value)
        fun port(u: URI) = if (u.port >= 0) u.port else if (u.scheme == "https") 443 else 80
        uri.rawUserInfo == null && uri.scheme == root.scheme && uri.host.equals(root.host, true) && port(uri) == port(root)
    }.getOrDefault(false)
    fun asset(path: String): String? = when(path) {
        "/tf", "/tf/arbeitsbericht", "/tf/arbeitsplan", "/tf/bahnhoefe", "/tf/leuna-uebergabeprotokoll" -> "tf-portal.html"
        "/tf/lokuebergabebuch", "/tf/loco-handover" -> "loco-handover.html"
        "/tf/handover-protocols.js" -> "handover-protocols.js"
        "/tf/loco-handover.js" -> "loco-handover.js"
        "/documents" -> "documents.html"
        "/account" -> "account.html"
        "/my/worktime" -> "my-worktime.html"
        "/admin/portal.css" -> "portal.css"
        "/my/worktime.js" -> "my-worktime.js"
        "/documents.js", "/documents.css", "/account.js", "/entry-form.js", "/responsive.css", "/i18n.js", "/android-portal.js" -> path.substringAfterLast('/')
        "/tf/portal.js" -> "tf-portal.js"
        "/tf/portal.css" -> "tf-portal.css"
        "/tf/work-report-feedback.js", "/tf/work-report.js", "/tf/work-report.css", "/tf/train-journeys.js", "/tf/gps.js", "/tf/stations.js", "/tf/station-sharing.js", "/tf/return.js" -> if(path.endsWith("return.js")) "tf-return.js" else path.substringAfterLast('/')
        else -> null
    }
}
