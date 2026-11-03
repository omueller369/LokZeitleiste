package de.lokzeitleiste.app.portal
import org.junit.Assert.*
import org.junit.Test

class HelpPrintDocumentTest {
    @Test fun plainHelpOnlyAndHtmlEscaped() {
        val html=HelpPrintDocument.render("Hilfe & Erklärung","Gruppe\n\n1. <script>alert('x')</script>\n2. ☕ 0:30")
        assertTrue(html.contains("Hilfe &amp; Erklärung"))
        assertTrue(html.contains("&lt;script&gt;"))
        assertFalse(html.contains("<script>"))
        assertTrue(html.contains("1. "))
        assertTrue(html.contains("☕ 0:30"))
        assertFalse(html.contains("<iframe"))
    }
    @Test fun limitsAndEmptyContent() {
        for(values in listOf("" to "Text","Titel" to "","x".repeat(201) to "Text","Titel" to "x".repeat(100001))) {
            try { HelpPrintDocument.render(values.first,values.second);fail("invalid help accepted") } catch(_:IllegalArgumentException) { }
        }
    }
}
