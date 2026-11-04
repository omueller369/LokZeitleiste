"""Confirmed, atomic edits spanning multiple TFs and planning periods."""
from ..localization import source as _text_source
import hashlib,json
from datetime import date
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field,model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..db import database_session
from ..models import User,TfProfile
from ..accounts.tf_profiles import daily_minutes
from .schemas import ImportInput
from .service import get_month,apply_days,RevisionConflict
from .duties import resolve_shift,duty_info,driver_type
from .holidays import holiday_info

class Group(ImportInput):
    tf_id:int=Field(gt=0)
    year:int=Field(ge=2000,le=2100)
    @model_validator(mode='after')
    def same_year(self):
        if any(day.date.year!=self.year for day in self.days):raise ValueError(_text_source('server_planning_collective.text_defe74489865'))
        return self
class Batch(BaseModel):
    groups:list[Group]=Field(min_length=1,max_length=250)
    @model_validator(mode='after')
    def unique(self):
        if len({(g.tf_id,g.year) for g in self.groups})!=len(self.groups):raise ValueError(_text_source('server_planning_collective.text_86133ee8d921'))
        if sum(len(g.days) for g in self.groups)>10000:raise ValueError(_text_source('server_planning_collective.text_65b13b015723'))
        return self
class ConfirmedBatch(Batch):
    confirmed:Literal[True]
    confirmation:str=Field(min_length=64,max_length=64)


def prepare(db,data,lock=False):
    changes=[]
    for tf_id in sorted({g.tf_id for g in data.groups}):
        user=db.scalar(select(User).where(User.id==tf_id).with_for_update()) if lock else db.get(User,tf_id)
        if not user or user.role!='tf' or not db.get(TfProfile,tf_id):raise HTTPException(404,_text_source('server_planning_collective.text_a8c327fb1b2a'))
    for group in sorted(data.groups,key=lambda g:(g.tf_id,g.year)):
        profile=db.get(TfProfile,group.tf_id);months={m:get_month(db,group.tf_id,group.year,m) for m in sorted(group.expected_revisions)}
        if any(months[m]['revision']!=revision for m,revision in group.expected_revisions.items()):raise RevisionConflict(_text_source('server_planning_collective.text_69a979c93fbf'))
        standard_minutes=daily_minutes(db,group.tf_id);tf_type=driver_type(db,group.tf_id)
        for day in sorted(group.days,key=lambda d:d.date):
            old=months[day.date.month]['days'][day.date.day-1]
            shift=resolve_shift(db,group.tf_id,day.kind,day.shift,old['shift'],old['kind'],known_driver_type=tf_type)
            after=dict(kind=day.kind,shift=shift,note=day.note)
            before={key:old[key] for key in after}
            if before==after:continue
            info=holiday_info(day.date)
            changes.append(dict(tf_id=group.tf_id,name=profile.first_name+' '+profile.last_name,date=day.date.isoformat(),before=dict(before,target_minutes=old['target_minutes']),after=dict(after,target_minutes=duty_info(day.date,day.kind,shift,info['is_holiday'],standard_minutes)['target_minutes'])))
    canonical=dict(groups=[g.model_dump(mode='json') for g in data.groups],changes=changes)
    digest=hashlib.sha256(json.dumps(canonical,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return dict(changes=changes,confirmation=digest,changed_days=len(changes),tf_count=len({item['tf_id'] for item in changes}))


def create_router(require_admin):
    router=APIRouter(prefix='/api/v1/admin/planning/collective')
    @router.post('/preview')
    def preview(data:Batch,user=Depends(require_admin),db:Session=Depends(database_session)):
        try:return prepare(db,data)
        except RevisionConflict as exc:raise HTTPException(409,str(exc)) from exc
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    @router.post('/apply')
    def apply(data:ConfirmedBatch,user=Depends(require_admin),db:Session=Depends(database_session)):
        try:
            review=prepare(db,data,True)
            if review['confirmation']!=data.confirmation:raise RevisionConflict(_text_source('server_planning_collective.text_1b62fa7fbf2d'))
            changed=0
            for group in sorted(data.groups,key=lambda g:(g.tf_id,g.year)):
                changed+=apply_days(db,tf_id=group.tf_id,year=group.year,days=group.days,revisions=group.expected_revisions,admin_id=user.id,source='collective')
            db.commit()
            return dict(changed_days=changed,tf_count=review['tf_count'])
        except (RevisionConflict,IntegrityError) as exc:
            db.rollback();raise HTTPException(409,_text_source('server_planning_collective.text_4b01c0ac50a5')) from exc
        except ValueError as exc:
            db.rollback();raise HTTPException(422,str(exc)) from exc
    return router
