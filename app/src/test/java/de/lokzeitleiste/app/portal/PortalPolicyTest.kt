package de.lokzeitleiste.app.portal
import org.junit.Assert.*
import org.junit.Test
class PortalPolicyTest {
    private val policy=PortalPolicy("https://ctl-software.io-goerlitz.eu")
    @Test fun exactOrigin() {
        assertTrue(policy.sameOrigin("https://ctl-software.io-goerlitz.eu/tf"))
        assertTrue(policy.sameOrigin("https://ctl-software.io-goerlitz.eu:443/documents"))
        for(url in listOf("http://ctl-software.io-goerlitz.eu/tf","https://ctl-software.io-goerlitz.eu.evil.test/tf","https://ctl-software.io-goerlitz.eu:444/tf","https://attacker@ctl-software.io-goerlitz.eu/tf","file:///tf","javascript:alert(1)")) assertFalse(url,policy.sameOrigin(url))
    }
    @Test fun onlyPackagedPublicViews() {
        assertEquals("loco-handover.html",policy.asset("/tf/lokuebergabebuch"))
        assertEquals("loco-handover.js",policy.asset("/tf/loco-handover.js"))
        for(path in listOf("/tf","/tf/arbeitsbericht","/tf/bahnhoefe","/tf/arbeitsplan","/documents","/account","/my/worktime")) assertNotNull(policy.asset(path))
        for(path in listOf("/admin","/api/v1/tf/portal","/api/v1/documents/download","/tf/../../secret")) assertNull(policy.asset(path))
    }
}
