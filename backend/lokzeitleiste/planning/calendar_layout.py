"""Monday-aligned month rows: all Saturdays/Sundays share fixed year columns."""
from datetime import date
YEAR_COLUMNS=37
WEEKDAYS=('Montag','Dienstag','Mittwoch','Donnerstag','Freitag','Samstag','Sonntag')
def year_slots(month):
    days=month['days']
    offset=date.fromisoformat(days[0]['date']).weekday() if days else 0
    return [None]*offset+days+[None]*(YEAR_COLUMNS-offset-len(days))
