from datetime import date, datetime
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..accounts.access import demand, ready, redact_plan
from ..db import database_session
from ..models import StaffProfile, TfProfile, User, WorkEntry, WorkEntryAudit, WorkEntryLock, WorkMonth, WorkTimeChange, now_utc
from ..schemas import EntryBatch, EntryIn
from ..worktime.service import validate_no_overlap
from ..reports.daily import WORK_KINDS
from ..reports.intervals import set_end_date,entry_end_date,touched_months
from ..worktime.api import TimeEdit
from .service import assert_unlocked, entry_view, user_overview


class LockInput(BaseModel):
    locked: bool
    expected_updated_at: datetime
    reason: str = Field(min_length=1,max_length=1000)


def create_router(require_account,require_admin,entry_dict,month_summary,upload_entries):
    router=APIRouter()

    def target(db,user_id):
        user=db.get(User,user_id)
        if not user or user.role not in ('tf','staff'):
            raise HTTPException(404,'Mitarbeiter nicht gefunden')
        return user

    def check_periods(db,user,entry,entry_dict,month_summary):
        for year,month in touched_months(entry.entry_date,entry_end_date(entry)):
            user_overview(db,user,year,month,entry_dict,month_summary,lock=True)

    def create(db,actor,user,item,tasks):
        if not 2000 <= item.date.year <= 2100:
            raise HTTPException(422,'Datum muss zwischen 2000 und 2100 liegen')
        db.scalar(select(User).where(User.id==user.id).with_for_update())
        existing=db.scalar(select(WorkEntry).join(WorkMonth).where(
            WorkMonth.tf_user_id==user.id,WorkEntry.client_id==str(item.client_id)).with_for_update())
        normalized=item.model_dump(mode='json')
        normalized['start']=item.start.strftime('%H:%M');normalized['end']=item.end.strftime('%H:%M')
        if existing:
            if entry_dict(existing)!=normalized:
                raise HTTPException(409,'Diese Erfassung existiert bereits mit anderen Daten. Bitte neu laden.')
            return entry_view(db,existing,entry_dict)
        if user.role=='tf':
            # Bestehender Eingang mit PDF-Quittung bleibt auch bei manueller Erfassung erhalten.
            upload_entries(item.date.year,item.date.month,EntryBatch(entries=[item]),tasks,user,db,manual_actor=actor)
            entry=db.scalar(select(WorkEntry).join(WorkMonth).where(
                WorkMonth.tf_user_id==user.id,WorkEntry.client_id==str(item.client_id)))
        else:
            period=db.scalar(select(WorkMonth).where(WorkMonth.tf_user_id==user.id,
                WorkMonth.year==item.date.year,WorkMonth.month==item.date.month).with_for_update())
            if not period:
                period=WorkMonth(tf_user_id=user.id,year=item.date.year,month=item.date.month);db.add(period);db.flush()
            entry=WorkEntry(work_month_id=period.id,client_id=str(item.client_id),kind=item.kind,entry_date=item.date,
                start_time=item.start.strftime('%H:%M'),end_time=item.end.strftime('%H:%M'),pause_minutes=item.pause,
                guest_minutes=item.guest,note=item.note,away=item.away,accommodation=item.accommodation,hotel_name=item.hotel_name)
            set_end_date(entry,item.end_date)
            db.add(entry);db.flush()
            try:
                validate_no_overlap(db,user.id,entry)
                check_periods(db,user,entry,entry_dict,month_summary)
            except ValueError as exc:
                db.rollback();raise HTTPException(409,str(exc)) from exc
        if user.role=='staff':
            db.add(WorkEntryAudit(entry_id=entry.id,actor_id=actor.id,action='manual_created'))
            db.commit()
        db.refresh(entry)
        return entry_view(db,entry,entry_dict)

    @router.get('/api/v1/account/worktime/months/{year}/{month}')
    def own_month(year:int,month:int,user:User=Depends(require_account),db:Session=Depends(database_session)):
        ready(db,user)
        return user_overview(db,target(db,user.id),year,month,entry_dict,month_summary)

    @router.post('/api/v1/account/worktime/entries',status_code=201)
    def own_entry(item:EntryIn,tasks:BackgroundTasks,user:User=Depends(require_account),db:Session=Depends(database_session)):
        ready(db,user)
        return create(db,user,target(db,user.id),item,tasks)

    @router.get('/api/v1/admin/worktime/users')
    def users(viewer:User=Depends(require_admin),db:Session=Depends(database_session)):
        result=[]
        for user in db.scalars(select(User).where(User.role.in_(('tf','staff'))).order_by(User.username)):
            p=db.get(TfProfile,user.id) if user.role=='tf' else db.get(StaffProfile,user.id)
            if p: result.append({'id':user.id,'role':user.role,'first_name':p.first_name,'last_name':p.last_name,
                                 'personnel_number':p.personnel_number if user.role=='tf' else p.cost_center})
        return result

    def change_time(db,actor,entry_id,data,owner_id=None):
        owner=db.scalar(select(WorkMonth.tf_user_id).join(WorkEntry).where(WorkEntry.id==entry_id))
        if owner is None or (owner_id is not None and owner!=owner_id):raise HTTPException(404,'Eintrag nicht gefunden')
        db.scalar(select(User).where(User.id==owner).with_for_update())
        user=target(db,owner)
        if owner_id is None and user.role=='tf':
            raise HTTPException(422,'Tf-Korrekturen bitte über den bestehenden Korrektureinstieg mit E-Mail vornehmen')
        entry=db.scalar(select(WorkEntry).where(WorkEntry.id==entry_id).with_for_update())
        if entry.kind not in WORK_KINDS:raise HTTPException(422,'Diese Erfassungsart enthält keine editierbare Arbeitszeit')
        assert_unlocked(db,entry_id)
        if data.expected_updated_at.tzinfo or data.expected_updated_at!=entry.updated_at:
            raise HTTPException(409,'Eintrag wurde inzwischen geändert. Bitte neu laden.')
        if user.role=='tf' and db.scalar(select(WorkTimeChange.id).where(WorkTimeChange.entry_id==entry_id).limit(1)):
            raise HTTPException(409,'Administrativ korrigierte Zeiten können nur durch die Verwaltung geändert werden')
        try:
            item=EntryIn.model_validate(dict(entry_dict(entry),start=data.start,end=data.end,**({"end_date":data.end_date} if "end_date" in data.model_fields_set else {})))
        except ValidationError as exc:raise HTTPException(422,exc.errors()[0]['msg']) from exc
        reason=data.reason.strip()
        if not reason:raise HTTPException(422,'Änderungsgrund erforderlich')
        old=(entry.start_time,entry.end_time,entry.explicit_end_date)
        entry.start_time,entry.end_time=item.start.strftime('%H:%M'),item.end.strftime('%H:%M')
        set_end_date(entry,item.end_date)
        if old==(entry.start_time,entry.end_time,entry.explicit_end_date):return {'changed':False}
        entry.updated_at=now_utc()
        try:
            validate_no_overlap(db,owner,entry)
            db.flush()
            check_periods(db,user,entry,entry_dict,month_summary)
        except ValueError as exc:db.rollback();raise HTTPException(409,str(exc)) from exc
        db.add(WorkEntryAudit(entry_id=entry_id,actor_id=actor.id,action='manual_updated',reason=reason))
        db.commit();return {'changed':True}

    @router.patch('/api/v1/account/worktime/entries/{entry_id}')
    def own_edit(entry_id:int,data:TimeEdit,user:User=Depends(require_account),db:Session=Depends(database_session)):
        ready(db,user)
        return change_time(db,user,entry_id,data,user.id)

    @router.patch('/api/v1/admin/worktime/entries/{entry_id}')
    def staff_edit(entry_id:int,data:TimeEdit,actor:User=Depends(require_admin),db:Session=Depends(database_session)):
        return change_time(db,actor,entry_id,data)

    @router.get('/api/v1/admin/worktime/users/{user_id}/months/{year}/{month}')
    def any_month(user_id:int,year:int,month:int,viewer:User=Depends(require_admin),db:Session=Depends(database_session)):
        result=user_overview(db,target(db,user_id),year,month,entry_dict,month_summary)
        if result['month']['planning']:redact_plan(db,viewer,result['month'])
        return result

    @router.post('/api/v1/admin/worktime/users/{user_id}/entries',status_code=201)
    def any_entry(user_id:int,item:EntryIn,tasks:BackgroundTasks,actor:User=Depends(require_admin),db:Session=Depends(database_session)):
        return create(db,actor,target(db,user_id),item,tasks)

    @router.put('/api/v1/admin/worktime/entries/{entry_id}/lock')
    def lock(entry_id:int,data:LockInput,actor:User=Depends(require_admin),db:Session=Depends(database_session)):
        demand(db,actor,'worktime',2 if data.locked else 3)
        owner=db.scalar(select(WorkMonth.tf_user_id).join(WorkEntry).where(WorkEntry.id==entry_id))
        if owner is None:raise HTTPException(404,'Eintrag nicht gefunden')
        db.scalar(select(User).where(User.id==owner).with_for_update())
        entry=db.scalar(select(WorkEntry).where(WorkEntry.id==entry_id).with_for_update())
        if data.expected_updated_at.tzinfo or data.expected_updated_at!=entry.updated_at:
            raise HTTPException(409,'Eintrag wurde inzwischen geändert. Bitte neu laden.')
        reason=data.reason.strip()
        if not reason:raise HTTPException(422,'Begründung erforderlich')
        item=db.get(WorkEntryLock,entry_id)
        if not item:item=WorkEntryLock(entry_id=entry_id);db.add(item)
        item.locked,item.actor_id,item.reason,item.updated_at=data.locked,actor.id,reason,now_utc()
        entry.updated_at=now_utc()
        db.add(WorkEntryAudit(entry_id=entry_id,actor_id=actor.id,action='locked' if data.locked else 'unlocked',reason=reason))
        db.commit()
        db.refresh(entry)
        return entry_view(db,entry,entry_dict)

    @router.get('/api/v1/admin/worktime/users/{user_id}/audit')
    def audit(user_id:int,viewer:User=Depends(require_admin),db:Session=Depends(database_session)):
        target(db,user_id)
        items=db.scalars(select(WorkEntryAudit).join(WorkEntry).join(WorkMonth).where(WorkMonth.tf_user_id==user_id)
                        .order_by(WorkEntryAudit.id.desc()).limit(100)).all()
        return [{'entry_id':a.entry_id,'actor_id':a.actor_id,'action':a.action,'reason':a.reason,
                 'created_at':a.created_at.isoformat()} for a in items]

    return router
