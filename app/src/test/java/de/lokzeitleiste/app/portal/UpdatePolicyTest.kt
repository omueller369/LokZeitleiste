package de.lokzeitleiste.app.portal
import org.junit.Assert.*
import org.junit.Test
class UpdatePolicyTest {
    @Test fun releaseCodesAreMonotonicAndBounded() {
        assertEquals(100012,UpdatePolicy.releaseVersion("android-test-12"))
        for(tag in listOf("v0.11","android-test-0","android-test--1","android-test-1-extra","android-test-99999999999999999999"))assertNull(UpdatePolicy.releaseVersion(tag))
    }
    @Test fun downloadsOnlyFromExactHttpsGithubHosts() {
        assertTrue(UpdatePolicy.allowedUrl("https://github.com/omueller369/LokZeitleiste/releases/download/android-test-12/update.json"))
        assertTrue(UpdatePolicy.allowedUrl("https://release-assets.githubusercontent.com/signed.apk?token=temporary"))
        for(url in listOf("http://github.com/file","https://github.com.evil.test/file","https://github.com:444/file","https://user@github.com/file","file:///tmp/file","https://elsewhere.test/file"))assertFalse(url,UpdatePolicy.allowedUrl(url))
    }
}
