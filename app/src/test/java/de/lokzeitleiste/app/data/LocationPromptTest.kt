package de.lokzeitleiste.app.data

import org.junit.Assert.*
import org.junit.Test

class LocationPromptTest {
    @Test fun `location question requires more than five minutes and a missing location`() {
        assertFalse(shouldAskForLocation(300, true, true, "", false))
        assertTrue(shouldAskForLocation(301, true, true, "", false))
        assertFalse(shouldAskForLocation(301, true, true, "Hamburg", false))
        assertFalse(shouldAskForLocation(301, false, true, "", false))
        assertFalse(shouldAskForLocation(301, true, false, "", false))
        assertFalse(shouldAskForLocation(301, true, true, "", true))
    }

    @Test fun `search accepts partial names and exact codes including spaces`() {
        val stations = listOf(Ds100Station("AH", "Hamburg Hbf"), Ds100Station("AA  G", "Hamburg-Altona Gbf"),
            Ds100Station("AA", "Hamburg-Altona"), Ds100Station("ZZ", "Aachen"))
        assertEquals("AA", searchDs100("aa", stations).first().code)
        assertEquals("AA  G", searchDs100("aa g", stations).first().code)
        assertEquals(setOf("AA", "AA  G"), searchDs100("altona", stations).map { it.code }.toSet())
        assertEquals(3, searchDs100("hamburg", stations).size)
    }

    @Test fun `unknown or blank queries return no station so free text remains possible`() {
        val directory = listOf(Ds100Station("AA", "Hamburg-Altona"))
        assertTrue(searchDs100("   ", directory).isEmpty())
        assertTrue(searchDs100("Mein unbekannter Ort", directory).isEmpty())
    }

    @Test fun `dropdown result count is bounded`() {
        val directory = (1..100).map { Ds100Station("X$it", "Ort $it") }
        assertEquals(50, searchDs100("Ort", directory).size)
        assertEquals(5, searchDs100("Ort", directory, limit = 5).size)
    }
}
