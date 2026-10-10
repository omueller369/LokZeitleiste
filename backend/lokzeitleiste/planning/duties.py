from datetime import date, timedelta
from ..models import TfDutyProfile

SHIFTS={'standard':dict(label='Streckendienst',start='',end='',minutes=480),
        'border_day':dict(label='Grenzdienst Tag',start='09:00',end='21:00',minutes=720),
        'border_night':dict(label='Grenzdienst Nacht',start='21:00',end='09:00',minutes=720)}
DRIVER_TYPES={'route':'Strecken-TF','border':'Grenz-TF','both':'Grenz- und Strecken-TF'}


def driver_type(db,tf_id):
    row=db.get(TfDutyProfile,tf_id)
    return row.driver_type if row else 'route'


def resolve_shift(db,tf_id,kind,requested,previous='standard',previous_kind='Ungeplant'):
    if kind!='Arbeitstag':return 'standard'
    shift=requested or (previous if previous_kind=='Arbeitstag' else 'border_day' if driver_type(db,tf_id)=='border' else 'standard')
    if shift not in SHIFTS:raise ValueError('Ungültige Schicht')
    if shift!='standard' and driver_type(db,tf_id) not in ('border','both'):
        raise ValueError('Grenzdienst erfordert Grenz-TF oder Grenz- und Strecken-TF.')
    return shift


def duty_info(day,kind,shift,is_holiday):
    shift=shift if kind=='Arbeitstag' else 'standard'
    cfg=SHIFTS[shift]
    end_date=day+timedelta(days=1) if shift=='border_night' and kind=='Arbeitstag' else day
    return dict(shift=shift,shift_label=cfg['label'] if kind=='Arbeitstag' else '',
                planned_start=day.isoformat()+'T'+cfg['start'] if kind=='Arbeitstag' and cfg['start'] else None,
                planned_end=end_date.isoformat()+'T'+cfg['end'] if kind=='Arbeitstag' and cfg['end'] else None,
                planned_minutes=cfg['minutes'] if kind=='Arbeitstag' else 480 if kind=='Urlaub' else 0,
                target_minutes=0 if is_holiday else cfg['minutes'] if kind=='Arbeitstag' else 480 if kind=='Urlaub' else 0)
