"""Gesetzliche Berliner Feiertage, ohne Ersatzfeiertage oder Schulferien."""
from functools import lru_cache
import holidays


@lru_cache(maxsize=101)
def berlin_holidays(year: int):
    return holidays.country_holidays('DE',subdiv='BE',years=year,language='de',observed=False)


def holiday_info(day):
    name=berlin_holidays(day.year).get(day,'')
    return {'is_holiday':bool(name),'holiday_name':name,'holiday_state':'BE'}
