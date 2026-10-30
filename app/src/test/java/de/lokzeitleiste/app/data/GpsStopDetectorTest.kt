package de.lokzeitleiste.app.data

import org.junit.Assert.*
import org.junit.Test

class GpsStopDetectorTest {
    private val distance = { a: Double, _: Double, b: Double, _: Double -> kotlin.math.abs(a - b).toFloat() }

    @Test fun `stop is detected without a station or network and departure uses first movement time`() {
        val detector = GpsStopDetector()
        for (time in 1000L..116000L step 5000L)
            assertNull(detector.sample(time, 0.0, 0.0, 0f, distance))
        assertEquals(GpsStopDetector.Event(1000L), detector.sample(121000L, 0.0, 0.0, 0f, distance))
        assertNull(detector.sample(126000L, 200.0, 0.0, 5f, distance))
        assertNull(detector.sample(141000L, 250.0, 0.0, 5f, distance))
        assertEquals(GpsStopDetector.Event(1000L, 126000L), detector.sample(156000L, 300.0, 0.0, 5f, distance))
    }

    @Test fun `missing location samples cannot establish a stop`() {
        val detector = GpsStopDetector()
        assertNull(detector.sample(1000L, 0.0, 0.0, null, distance))
        assertNull(detector.sample(200000L, 0.0, 0.0, null, distance))
        assertNull(detector.sample(201000L, 0.0, 0.0, null, distance))
    }

    @Test fun `movement and reset prevent false stops`() {
        val detector = GpsStopDetector()
        for (time in 1000L..241000L step 5000L)
            assertNull(detector.sample(time, 0.0, 0.0, 8f, distance))
        detector.reset()
        assertNull(detector.sample(300000L, 0.0, 0.0, 0f, distance))
    }

    @Test fun `place lookup respects word boundaries and returns ambiguous stations for review`() {
        val directory = listOf(Ds100Station("AA", "Hamburg-Altona"), Ds100Station("AH", "Hamburg Hbf"),
            Ds100Station("X", "Hamburger Straße"), Ds100Station("Y", "Bad Münster"))
        assertEquals(setOf("AA", "AH"), matchPlaces(listOf("Hamburg"), directory).map { it.code }.toSet())
        assertEquals(listOf("Y"), matchPlaces(listOf("Bad Munster"), directory).map { it.code })
        assertTrue(matchPlaces(listOf("Unbekannt"), directory).isEmpty())
    }

    @Test fun `transfer is idempotent and retains other stops and missing locations`() {
        val a = StopEntry("Alt", 1000, 2000, "Zugfolge", "", "GPS", id = "a")
        val b = StopEntry("", 3000, 4000, "Zugfolge", "", "GPS", id = "b")
        val updated = a.copy(station = "Neu", ds100 = "AA")
        assertEquals(listOf(updated, b), mergeStops(listOf(a, b), listOf(updated)))
        assertEquals(listOf(updated, b), mergeStops(mergeStops(listOf(a), listOf(updated, b)), listOf(updated, b)))
    }
}
