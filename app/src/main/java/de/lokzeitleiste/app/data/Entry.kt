package de.lokzeitleiste.app.data

import java.time.*
import java.util.UUID

data class Entry(
    val kind: String, val date: String, val start: String, val end: String,
    val pause: Int, val guest: Int, val note: String,
    val away: Boolean = false, val accommodation: String = "", val hotelName: String = "",
    val clientId: String = UUID.randomUUID().toString(), val endDate: String? = null
)

fun minutes(time: String): Int = LocalTime.parse(time).let { it.hour * 60 + it.minute }

fun length(e: Entry): Int {
    return (Duration.between(startAt(e), endAt(e)).toMinutes().toInt() - e.pause).coerceAtLeast(0)
}

fun startAt(e: Entry): LocalDateTime = LocalDate.parse(e.date).atTime(LocalTime.parse(e.start))

fun endAt(e: Entry): LocalDateTime {
    val from = startAt(e)
    var until = LocalDate.parse(e.endDate ?: e.date).atTime(LocalTime.parse(e.end))
    if (e.endDate == null && !until.isAfter(from)) until = until.plusDays(1)
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

private fun monthInterval(e: Entry, month: YearMonth, guestOnly: Boolean = false): Pair<LocalDateTime,LocalDateTime> {
    val from = startAt(e)
    val activeEnd = endAt(e).minusMinutes(e.pause.toLong())
    val until = if (guestOnly) minOf(activeEnd, from.plusMinutes(e.guest.toLong())) else activeEnd
    return maxOf(from, month.atDay(1).atStartOfDay()) to minOf(until, month.plusMonths(1).atDay(1).atStartOfDay())
}

fun monthMinutes(e: Entry, month: YearMonth, guestOnly: Boolean = false): Int {
    val (from, until) = monthInterval(e, month, guestOnly)
    return Duration.between(from, until).toMinutes().toInt().coerceAtLeast(0)
}

fun monthOverlap(e: Entry, month: YearMonth, condition: (LocalDateTime) -> Boolean): Int {
    val (from, until) = monthInterval(e, month)
    var time = from
    var count = 0
    while (time < until) { if (condition(time)) count++; time = time.plusMinutes(1) }
    return count
}
