package de.lokzeitleiste.app.data

/** Times are independent of station data and network availability. */
class GpsStopDetector {
    private var anchor: Pair<Double, Double>? = null
    private var since = 0L
    private var lastTime = 0L
    private var active = false
    private var movingSince = 0L

    data class Event(val arrival: Long, val departure: Long? = null)

    fun reset() { anchor = null; since = 0L; lastTime = 0L; active = false; movingSince = 0L }

    fun sample(time: Long, lat: Double, lon: Double, speed: Float?, distance: (Double, Double, Double, Double) -> Float): Event? {
        if (time <= lastTime) return null
        // A gap must not count as evidence of standing still or moving.
        if (lastTime != 0L && time - lastTime > 120000L) {
            if (!active) { anchor = null; since = 0L }
            movingSince = 0L
        }
        lastTime = time
        val point = anchor
        if (point == null) { anchor = lat to lon; since = time; return null }
        val meters = distance(point.first, point.second, lat, lon)
        if (!active) {
            if (meters > 75f || (speed != null && speed > 1.5f)) { anchor = lat to lon; since = time }
            else if (time - since >= 120000L) { active = true; return Event(since) }
        } else {
            val moving = meters > 150f || (speed != null && speed > 2.5f)
            if (!moving) movingSince = 0L
            else if (movingSince == 0L) movingSince = time
            else if (time - movingSince >= 30000L) {
                val result = Event(since, movingSince)
                reset()
                return result
            }
        }
        return null
    }
}

data class Ds100Station(val code: String, val name: String)

private fun normalizePlace(value: String): String = java.text.Normalizer.normalize(
    value.lowercase(java.util.Locale.GERMAN).replace("ß", "ss"), java.text.Normalizer.Form.NFD
).replace(Regex("\\p{M}+"), "").replace(Regex("[^a-z0-9]+"), " ")
    .replace(Regex("\\b(am|an der)\\b"), " ").replace(Regex("\\s+"), " ").trim()

fun matchPlaces(places: List<String>, directory: List<Ds100Station>): List<Ds100Station> {
    val names = places.map(::normalizePlace).filter { it.isNotBlank() }.toSet()
    return directory.filter { row ->
        val station = normalizePlace(row.name)
        names.any { place -> station == place || station.startsWith("$place ") }
    }.distinctBy { it.code }.sortedWith(compareBy({ it.name }, { it.code }))
}

fun shouldAskForLocation(seconds: Long, recording: Boolean, activeStop: Boolean, locationName: String, alreadyAsked: Boolean): Boolean =
    seconds > 300L && recording && activeStop && locationName.isBlank() && !alreadyAsked

/** Offline search by either name or DS100, with exact code matches first. */
fun searchDs100(query: String, directory: List<Ds100Station>, limit: Int = 50): List<Ds100Station> {
    val name = normalizePlace(query)
    val code = query.filterNot { it.isWhitespace() }.uppercase(java.util.Locale.GERMAN)
    if (name.isBlank() || limit <= 0) return emptyList()
    return directory.mapNotNull { row ->
        val rowCode = row.code.filterNot { it.isWhitespace() }.uppercase(java.util.Locale.GERMAN)
        val rowName = normalizePlace(row.name)
        val rank = when {
            rowCode == code -> 0
            rowName == name -> 1
            rowCode.startsWith(code) -> 2
            rowName.startsWith(name) -> 3
            rowName.contains(name) -> 4
            else -> return@mapNotNull null
        }
        row to rank
    }.sortedWith(compareBy({ it.second }, { it.first.name }, { it.first.code }))
        .map { it.first }.distinctBy { it.code }.take(limit)
}
