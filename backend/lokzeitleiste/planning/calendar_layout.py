"""Original year grid: one month per row, calendar days 1-31 in fixed columns."""
YEAR_COLUMNS=31
def year_slots(month):
    return month['days']+[None]*(YEAR_COLUMNS-len(month['days']))
