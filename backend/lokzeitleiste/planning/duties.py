from ..localization import source as _text_source
from datetime import date, timedelta
from ..models import TfDutyProfile

SHIFTS={'standard':dict(label=_text_source('server_planning_duties.text_77d64b3ca8ca'),start='',end='',minutes=480),
        'border_day':dict(label=_text_source('server_planning_duties.text_6c9b9f7f7346'),start='09:00',end='21:00',minutes=720),
        'border_night':dict(label=_text_source('server_planning_duties.text_04b9a3e19613'),start='21:00',end='09:00',minutes=720)}
DRIVER_TYPES={'route':_text_source('server_planning_duties.text_52b8ef8ce077'),'border':_text_source('server_planning_duties.text_2f28091327c1'),'both':_text_source('server_planning_duties.text_cf50f72af462')}


def driver_type(db,tf_id):
    row=db.get(TfDutyProfile,tf_id)
    return row.driver_type if row else 'route'


def resolve_shift(db,tf_id,kind,requested,previous='standard',previous_kind=_text_source('server_planning_duties.text_52e37a639da5'),known_driver_type=None):
    if kind!=_text_source('server_planning_duties.text_eb8f579b6931'):return 'standard'
    tf_type=known_driver_type or driver_type(db,tf_id)
    shift=requested or (previous if previous_kind==_text_source('server_planning_duties.text_eb8f579b6931') else 'border_day' if tf_type=='border' else 'standard')
    if shift not in SHIFTS:raise ValueError(_text_source('server_planning_duties.text_d3fd46ec61ee'))
    if shift!='standard' and tf_type not in ('border','both'):
        raise ValueError(_text_source('server_planning_duties.text_3675898e0efe'))
    return shift


def duty_info(day,kind,shift,is_holiday,standard_minutes=480):
    shift=shift if kind==_text_source('server_planning_duties.text_eb8f579b6931') else 'standard'
    cfg=dict(SHIFTS[shift])
    if shift=='standard':cfg['minutes']=standard_minutes
    end_date=day+timedelta(days=1) if shift=='border_night' and kind==_text_source('server_planning_duties.text_eb8f579b6931') else day
    return dict(shift=shift,shift_label=cfg['label'] if kind==_text_source('server_planning_duties.text_eb8f579b6931') else '',
                planned_start=day.isoformat()+'T'+cfg['start'] if kind==_text_source('server_planning_duties.text_eb8f579b6931') and cfg['start'] else None,
                planned_end=end_date.isoformat()+'T'+cfg['end'] if kind==_text_source('server_planning_duties.text_eb8f579b6931') and cfg['end'] else None,
                planned_minutes=cfg['minutes'] if kind==_text_source('server_planning_duties.text_eb8f579b6931') else 480 if kind==_text_source('server_planning_duties.text_35d3a889824d') else 0,
                target_minutes=0 if is_holiday else cfg['minutes'] if kind==_text_source('server_planning_duties.text_eb8f579b6931') else 480 if kind==_text_source('server_planning_duties.text_35d3a889824d') else 0)
