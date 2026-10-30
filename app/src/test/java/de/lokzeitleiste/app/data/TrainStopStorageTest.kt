package de.lokzeitleiste.app.data

import org.json.JSONArray
import org.junit.Assert.*
import org.junit.Test

class TrainStopStorageTest {
    @Test fun `legacy stop data keeps all values and gains a stable id`() {
        val raw = """[{"station":"Altbahnhof","arrival":1234,"departure":9876,"reason":"Zugfolge","note":"Bestand","source":"GPS/OSM – prüfen","ds100":"AA"}]"""
        val first = stopsFromJson(JSONArray(raw)).single()
        assertEquals(first, stopsFromJson(JSONArray(raw)).single())
        assertEquals("Altbahnhof", first.station)
        assertEquals(1234L, first.arrival)
        assertEquals(9876L, first.departure)
        assertEquals("Bestand", first.note)
        assertEquals("AA", first.ds100)
        assertEquals(listOf(first), stopsFromJson(stopsToJson(listOf(first))))
    }

    @Test fun `blank location and corrections round trip with the same identity`() {
        val stop = StopEntry("", 1000L, 9000L, "Zugfolge", "", "GPS")
        val restored = stopsFromJson(stopsToJson(listOf(stop))).single()
        assertEquals(stop, restored)
        val updated = restored.copy(station = "Hamburg-Altona", ds100 = "AA")
        assertEquals(stop.id, stopsFromJson(stopsToJson(listOf(updated))).single().id)
    }
}
