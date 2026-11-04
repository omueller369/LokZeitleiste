"""System-wide plan colours. Leave and rest override weekends; holidays retain diagonal status."""
from ..localization import source as _text_source
from datetime import date
COLORS={_text_source('server_planning_palette.text_eb8f579b6931'):'F5F5F5',_text_source('server_planning_palette.text_35d3a889824d'):'FF7256',_text_source('server_planning_palette.text_e79aa42d7d18'):'66CDAA',_text_source('server_planning_palette.text_52e37a639da5'):'EEF0F3',_text_source('server_planning_palette.text_ecda07db6e0b'):'FFE4E1',_text_source('server_planning_palette.text_fd7058ac0c38'):'EEDC82'}
def base_key(day):
    if day['kind'] in (_text_source('server_planning_palette.text_35d3a889824d'),_text_source('server_planning_palette.text_e79aa42d7d18')):return day['kind']
    value=day['date'];value=date.fromisoformat(value) if isinstance(value,str) else value
    return _text_source('server_planning_palette.text_fd7058ac0c38') if value.weekday()>=5 else day['kind']
def background_key(day):return _text_source('server_planning_palette.text_ecda07db6e0b') if day.get('is_holiday') else base_key(day)
