"""System-wide plan colours. Leave and rest override weekends; holidays retain diagonal status."""
from datetime import date
COLORS={'Arbeitstag':'F5F5F5','Urlaub':'FF7256','Ruhetag':'66CDAA','Ungeplant':'EEF0F3','Feiertag':'FFE4E1','Wochenende':'EEDC82'}
def base_key(day):
    if day['kind'] in ('Urlaub','Ruhetag'):return day['kind']
    value=day['date'];value=date.fromisoformat(value) if isinstance(value,str) else value
    return 'Wochenende' if value.weekday()>=5 else day['kind']
def background_key(day):return 'Feiertag' if day.get('is_holiday') else base_key(day)
