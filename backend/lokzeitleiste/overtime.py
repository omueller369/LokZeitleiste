"""Monthly overtime per duty; immutable closing snapshots with explicit reopening."""
import hashlib
import json
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import contains_eager

from .db import database_session
from .models import User, TfProfile, WorkEntry, WorkEntryDates, WorkMonth, OvertimePolicy, OvertimeClosing, OvertimeAudit, now_utc
from .reports.intervals import interval

CAP = 40 * 60
SHIFT_KINDS = {'Sonstige Erfassung', 'Zugfahrt'}


def current_month():
    return datetime.now(ZoneInfo('Europe/Berlin')).date().replace(day=1)


def month_date(year, month):
    if not 2000 <= year <= 2100 or not 1 <= month <= 12:
        raise HTTPException(422, 'Ungültiger Monat')
    return date(year, month, 1)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def tf_user(db, tf_id, lock=False):
    query = select(User).where(User.id == tf_id)
    if lock:
        query = query.with_for_update()
    user = db.scalar(query)
    if not user or user.role != 'tf':
        raise HTTPException(404, 'Mitarbeiter nicht gefunden')
    return user


def policy_at(db, tf_id, month, lock=False):
    query=select(OvertimePolicy).where(
        OvertimePolicy.tf_user_id == tf_id, OvertimePolicy.month <= month
    ).order_by(OvertimePolicy.month.desc()).limit(1)
    return db.scalar(query.with_for_update() if lock else query)


def duty_rows(db, tf_id, month, lock=False):
    following = date(month.year + 1, 1, 1) if month.month == 12 else date(month.year, month.month + 1, 1)
    query = select(WorkEntry).join(WorkMonth).outerjoin(WorkEntryDates).options(contains_eager(WorkEntry.date_override)).where(
        WorkMonth.tf_user_id == tf_id, WorkEntry.entry_date >= month, WorkEntry.entry_date < following
    ).order_by(WorkEntry.entry_date, WorkEntry.start_time, WorkEntry.id)
    entries = db.scalars(query.with_for_update() if lock else query).all()
    rows = []
    for entry in entries:
        begin, end = interval(entry)
        duration = int((end - begin).total_seconds() // 60)
        if duration <= 0:
            raise HTTPException(409, 'Ungültige Dienstzeit im Überstundenkonto.')
        rows.append(dict(entry_id=entry.id,kind=entry.kind,start_at=begin.isoformat(),end_at=end.isoformat(),
                         duration_minutes=duration,overtime_minutes=max(0,duration-480) if entry.kind in SHIFT_KINDS else 0))
    return rows


def booked(db, tf_id, lock=False):
    query=select(OvertimeClosing).where(
        OvertimeClosing.tf_user_id == tf_id, OvertimeClosing.status == 'closed'
    ).order_by(OvertimeClosing.month)
    return db.scalars(query.with_for_update() if lock else query).all()


def closing_dict(row):
    if not row:
        return None
    return dict(month=row.month.isoformat()[:7],status=row.status,mode=row.mode,total_minutes=row.total_minutes,
                annual_minutes=row.annual_minutes,payout_minutes=row.payout_minutes,revision=row.revision,
                actor_id=row.actor_id,updated_at=row.updated_at.isoformat())


def view(db, tf_id, month, lock=False):
    policy = policy_at(db,tf_id,month,lock)
    enabled = bool(policy and policy.enabled)
    rows = duty_rows(db,tf_id,month,lock)
    fingerprint = digest(rows)
    closing = db.scalar(select(OvertimeClosing).where(OvertimeClosing.tf_user_id==tf_id,OvertimeClosing.month==month).with_for_update()) if lock else db.get(OvertimeClosing,(tf_id,month))
    accounts = booked(db,tf_id,lock)
    balance = sum(row.annual_minutes for row in accounts)
    total = sum(row['overtime_minutes'] for row in rows) if enabled else 0
    token = digest(dict(fingerprint=fingerprint,enabled=enabled,
                        policy=policy.month.isoformat() if policy else None,
                        revision=closing.revision if closing else 0,
                        bookings=[(row.month.isoformat(),row.revision,row.annual_minutes,row.payout_minutes) for row in accounts]))
    return dict(month=month.isoformat()[:7],enabled=enabled,rows=rows,total_minutes=total,
                bank_balance_minutes=balance,bank_cap_minutes=CAP,bank_available_minutes=max(0,CAP-balance),
                closing=closing_dict(closing),stale=bool(closing and closing.status=='closed' and closing.fingerprint!=fingerprint),
                can_close=month<current_month(),token=token)


def audit(db,tf_id,month,actor,action,snapshot):
    db.add(OvertimeAudit(tf_user_id=tf_id,month=month,actor_id=actor.id,action=action,
                         snapshot_json=json.dumps(snapshot,ensure_ascii=False)))


def allocate(total, balance, mode):
    if total < 0 or balance < 0 or balance > CAP:
        raise HTTPException(409,'Ungültiger Kontostand im Überstundenkonto.')
    annual = min(total,CAP-balance) if mode=='annual' else 0
    return annual,total-annual


class PolicyInput(BaseModel):
    enabled:bool
    expected_token:str = Field(pattern=r'^[0-9a-f]{64}$')


class CloseInput(BaseModel):
    mode:Literal['payout','annual']
    expected_token:str = Field(pattern=r'^[0-9a-f]{64}$')


class ReopenInput(BaseModel):
    reason:str = Field(min_length=1,max_length=1000)
    expected_token:str = Field(pattern=r'^[0-9a-f]{64}$')


def create_router(require_admin):
    router = APIRouter(prefix='/api/v1/admin/tf/{tf_id}/overtime')

    @router.get('/{year}/{month}')
    def get_month(tf_id:int,year:int,month:int,actor:User=Depends(require_admin),db=Depends(database_session)):
        tf_user(db,tf_id)
        return view(db,tf_id,month_date(year,month))

    @router.get('/{year}')
    def get_year(tf_id:int,year:int,actor:User=Depends(require_admin),db=Depends(database_session)):
        first=month_date(year,1)
        tf_user(db,tf_id)
        accounts=booked(db,tf_id)
        rows=[]
        for number in range(1,13):
            data=view(db,tf_id,date(year,number,1))
            rows.append({key:data[key] for key in ('month','enabled','total_minutes','closing','stale')})
        opening=sum(row.annual_minutes for row in accounts if row.month<first)
        changes=db.scalars(select(OvertimeAudit).where(OvertimeAudit.tf_user_id==tf_id,
            OvertimeAudit.month>=first,OvertimeAudit.month<date(year+1,1,1)
        ).order_by(OvertimeAudit.id.desc()).limit(100)).all()
        return dict(year=year,months=rows,opening_minutes=opening,
                    bank_balance_minutes=sum(row.annual_minutes for row in accounts),bank_cap_minutes=CAP,
                    history=[dict(id=row.id,month=row.month.isoformat()[:7],action=row.action,actor_id=row.actor_id,
                                  created_at=row.created_at.isoformat(),snapshot=json.loads(row.snapshot_json)) for row in changes])

    @router.put('/{year}/{month}/policy')
    def set_policy(tf_id:int,year:int,month:int,data:PolicyInput,actor:User=Depends(require_admin),db=Depends(database_session)):
        tf_user(db,tf_id,True)
        day=month_date(year,month)
        before=view(db,tf_id,day,True)
        if data.expected_token!=before['token']:
            raise HTTPException(409,'Überstundenkonto wurde geändert. Bitte neu laden.')
        if before['enabled']==data.enabled:
            return before
        if any(row.month>=day for row in booked(db,tf_id,True)):
            raise HTTPException(409,'Zuerst betroffene Monatsabschlüsse wieder öffnen.')
        row=db.get(OvertimePolicy,(tf_id,day))
        if not row:
            row=OvertimePolicy(tf_user_id=tf_id,month=day,enabled=data.enabled,actor_id=actor.id)
            db.add(row)
        else:
            row.enabled=data.enabled
            row.actor_id=actor.id
            row.updated_at=now_utc()
        audit(db,tf_id,day,actor,'policy',dict(before=before['enabled'],after=data.enabled))
        db.flush()
        result=view(db,tf_id,day,True)
        db.commit()
        return result

    @router.post('/{year}/{month}/close')
    def close(tf_id:int,year:int,month:int,data:CloseInput,actor:User=Depends(require_admin),db=Depends(database_session)):
        tf_user(db,tf_id,True)
        day=month_date(year,month)
        before=view(db,tf_id,day,True)
        if before['closing'] and before['closing']['status']=='closed':
            raise HTTPException(409,'Monat ist bereits abgeschlossen.')
        if data.expected_token!=before['token']:
            raise HTTPException(409,'Überstundenkonto wurde geändert. Bitte neu laden.')
        if not before['enabled']:
            raise HTTPException(409,'Überstundenkonto ist für diesen Monat nicht aktiviert.')
        if not before['can_close']:
            raise HTTPException(409,'Monatsabschluss erst nach Monatsende möglich.')
        for item in booked(db,tf_id,True):
            if item.fingerprint!=digest(duty_rows(db,tf_id,item.month,True)):
                raise HTTPException(409,'Geänderte Monatsabschlüsse zuerst prüfen und wieder öffnen.')
        annual,payout=allocate(before['total_minutes'],before['bank_balance_minutes'],data.mode)
        row=db.get(OvertimeClosing,(tf_id,day))
        if not row:
            row=OvertimeClosing(tf_user_id=tf_id,month=day,actor_id=actor.id)
            db.add(row)
        row.status='closed'
        row.mode=data.mode
        row.total_minutes=before['total_minutes']
        row.annual_minutes=annual
        row.payout_minutes=payout
        row.fingerprint=digest(before['rows'])
        row.revision=(row.revision or 0)+1
        row.actor_id=actor.id
        row.updated_at=now_utc()
        db.flush()
        audit(db,tf_id,day,actor,'close',closing_dict(row))
        result=view(db,tf_id,day,True)
        db.commit()
        return result

    @router.post('/{year}/{month}/reopen')
    def reopen(tf_id:int,year:int,month:int,data:ReopenInput,actor:User=Depends(require_admin),db=Depends(database_session)):
        tf_user(db,tf_id,True)
        day=month_date(year,month)
        before=view(db,tf_id,day,True)
        if data.expected_token!=before['token']:
            raise HTTPException(409,'Überstundenkonto wurde geändert. Bitte neu laden.')
        row=db.get(OvertimeClosing,(tf_id,day))
        if not row or row.status!='closed':
            raise HTTPException(409,'Kein abgeschlossener Monat vorhanden.')
        if not data.reason.strip():
            raise HTTPException(422,'Änderungsgrund erforderlich')
        audit(db,tf_id,day,actor,'reopen',dict(before=closing_dict(row),reason=data.reason.strip()))
        row.status='open'
        row.revision+=1
        row.actor_id=actor.id
        row.updated_at=now_utc()
        db.flush()
        result=view(db,tf_id,day,True)
        db.commit()
        return result

    return router
