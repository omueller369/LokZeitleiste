"""Read-only comparison of Tf working hours and Berlin planning targets."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .db import database_session
from .models import User


def year_overview(db, tf_id, year, month_summary):
    months = []
    for month in range(1, 13):
        summary = month_summary(db, tf_id, year, month)
        actual = {d['date']: d for d in summary['days']}
        days = []
        for planned in summary['planning']['days']:
            recorded = actual.get(planned['date'], {})
            work = recorded.get('work_without_guest', 0) + recorded.get('guest', 0)
            complete = planned['kind'] != 'Ungeplant' or planned['is_holiday']
            days.append(dict(planned, work_minutes=work, credited_minutes=recorded.get('credited', 0),
                             actual_kind=recorded.get('type', 'Keine Erfassung'),
                             guest_minutes=recorded.get('guest', 0), topup_minutes=recorded.get('topup', 0),
                             vacation_minutes=recorded.get('vacation', 0), sick_minutes=recorded.get('sick', 0),
                             complete=complete, balance_minutes=work-planned['target_minutes'] if complete else None))
        work = sum(d['work_minutes'] for d in days)
        target = summary['target_minutes']
        complete = summary['planning']['complete']
        months.append(dict(month=month, days=days, work_minutes=work, target_minutes=target,
                           credited_minutes=summary['totals']['credited'], complete=complete,
                           unplanned_days=summary['planning']['unplanned_days'],
                           balance_minutes=work-target if complete else None))
    totals = {k: sum(m[k] for m in months) for k in ('work_minutes', 'target_minutes', 'credited_minutes', 'unplanned_days')}
    complete = all(m['complete'] for m in months)
    totals.update(complete=complete, balance_minutes=totals['work_minutes']-totals['target_minutes'] if complete else None)
    return dict(tf_user_id=tf_id, year=year, months=months, totals=totals)


def create_router(require_admin, month_summary):
    router = APIRouter()

    @router.get('/api/v1/admin/tf/{tf_id}/hours/{year}')
    def get_hours(tf_id: int, year: int, viewer: User = Depends(require_admin), db: Session = Depends(database_session)):
        if not 2000 <= year <= 2100:
            raise HTTPException(422, 'Ungültiges Jahr')
        user = db.get(User, tf_id)
        if not user or user.role != 'tf':
            raise HTTPException(404, 'Tf nicht gefunden')
        return year_overview(db, tf_id, year, month_summary)

    return router
