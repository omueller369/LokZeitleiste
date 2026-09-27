package de.lokzeitleiste.app.data

import java.time.*
import java.util.UUID

data class Entry(
    val kind: String, val date: String, val start: String, val end: String,
    val pause: Int, val guest: Int, val note: String,
    val away: Boolean = false, val accommodation: String = "", val hotelName: String = "",
    val clientId: String = UUID.randomUUID().toString()
)

fun minutes(time: String): Int = LocalTime.parse(time).let { it.hour * 60 + it.minute }

fun length(e: Entry): Int {
    val start = minutes(e.start)
    var end = minutes(e.end)
    if (end <= start) end += 1440
    return (end - start - e.pause).coerceAtLeast(0)
}

fun startAt(e: Entry): LocalDateTime = LocalDate.parse(e.date).atTime(LocalTime.parse(e.start))

fun endAt(e: Entry): LocalDateTime {
    val from = startAt(e)
    var until = LocalDate.parse(e.date).atTime(LocalTime.parse(e.end))
    if (!until.isAfter(from)) until = until.plusDays(1)
    return until
}

fun overlap(e: Entry, condition: (LocalDateTime) -> Boolean): Int {
    val from = startAt(e)
    val until = endAt(e)
    var count = 0
    var time = from
    while (time < until) { if (condition(time)) count++; time = time.plusMinutes(1) }
    return (count - e.pause.coerceAtMost(count)).coerceAtLeast(0)
}

fun displayTime(n: Int) = "%d:%02d h".format(n / 60, n % 60)
