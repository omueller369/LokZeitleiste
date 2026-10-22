"""Versioned app vocabulary. Stable keys preserve historical report semantics."""
import json
from pathlib import Path
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter,Depends,HTTPException,Query
from fastapi.responses import FileResponse
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .db import database_session
from .models import AppDefaultValue as Value,AppDefaultSeed,DutyReport,TrainGpsRecording
from .tf_portal import driver_dependency


def historical_values(db):
    result=set()
    for raw in db.scalars(select(DutyReport.payload_json)):
        for train in json.loads(raw).get('train_journeys',[]):
            for event in train.get('events',[]):
                for category,field in [('reason','reason'),('cause','cause')]:
                    if event.get(field):result.add((category,event[field]))
    for raw in db.scalars(select(TrainGpsRecording.payload_json)):
        for reason in json.loads(raw).get('reasons',{}).values():
            if reason.get('reason'):result.add(('reason',reason['reason']))
    if ('cause','CTL Logistics DE') in result:result.add(('cause','CTL'))
    return result


def ensure_defaults(db):
    if db.get(AppDefaultSeed,1):return
    from .work_reports.schemas import REASONS
    used=historical_values(db)
    defaults=[('reason',value,True) for value in REASONS]+[('cause',value,True) for value in ('CTL','DB InfraGo','Dritte Stelle','sonstiges')]
    known={(kind,value) for kind,value,_ in defaults}
    defaults += [(kind,value,False) for kind,value in sorted(used-known)]
    db.add(AppDefaultSeed(id=1))
    for kind,value,active in defaults:
        db.add(Value(category=kind,value=value,label=value,label_key=value.casefold(),active=active,ever_used=(kind,value) in used,revision=1))
    try:db.commit()
    except IntegrityError:
        db.rollback()
        if not db.get(AppDefaultSeed,1):raise


def use_value(db,category,value,previous=None):
    # Match historical CTL DE to its current key without rewriting report snapshots.
    canonical='CTL' if category=='cause' and value=='CTL Logistics DE' else value
    row=db.scalar(select(Value).where(Value.category==category,Value.value==canonical).with_for_update())
    if not row or (not row.active and value!=previous):raise HTTPException(422,'Auswahlwert ist nicht mehr verfügbar. Bitte neu auswählen.')
    row.ever_used=True
    return row


def use_journeys(db,journeys,previous=()):
    ensure_defaults(db)
    old={(str(train['id']),str(event['id'])):event for train in previous for event in train.get('events',[])}
    # A consistent order also serializes use/deletion of shared values.
    selections=[]
    for train in journeys:
        for event in train.events:
            prior=old.get((str(train.id),str(event.id)),{})
            selections += [(category,getattr(event,category),prior.get(category)) for category in ('cause','reason')]
    labels={}
    for category,value,previous_value in sorted(selections,key=lambda item:(item[0],item[1])):labels[category,value]=use_value(db,category,value,previous_value).label
    for train in journeys:
        for event in train.events:
            prior=old.get((str(train.id),str(event.id)),{})
            for category in ('reason','cause'):
                label=prior.get(category+'_label') if prior.get(category)==getattr(event,category) else None
                setattr(event,category+'_label',label or labels[category,getattr(event,category)])

class ValueInput(BaseModel):
    label:str=Field(min_length=1,max_length=200)
    active:bool=True
    @field_validator('label')
    @classmethod
    def trim(cls,value):
        value=value.strip()
        if not value:raise ValueError('Bezeichnung ist erforderlich.')
        return value
class ValueUpdate(ValueInput):
    expected_revision:int=Field(ge=1)


def view(row):return dict(id=row.id,category=row.category,value=row.value,label=row.label,active=row.active,used=row.ever_used,revision=row.revision)


def create_router(require_admin,require_account):
    router=APIRouter();driver=driver_dependency(require_account)
    @router.get('/admin/app-defaults')
    def page():return FileResponse(Path(__file__).parent/'static'/'app-defaults.html')
    @router.get('/admin/app-defaults.js')
    def script():return FileResponse(Path(__file__).parent/'static'/'app-defaults.js',media_type='text/javascript',headers={'Cache-Control':'no-cache'})
    @router.get('/api/v1/tf/app-defaults')
    def choices(user=Depends(driver),db:Session=Depends(database_session)):
        ensure_defaults(db)
        return [view(row) for row in db.scalars(select(Value).order_by(Value.id))]
    @router.get('/api/v1/admin/app-defaults',dependencies=[Depends(require_admin)])
    def listing(db:Session=Depends(database_session)):
        ensure_defaults(db)
        return [view(row) for row in db.scalars(select(Value).order_by(Value.id))]
    def commit(db,row):
        try:db.commit()
        except IntegrityError as exc:
            db.rollback();raise HTTPException(409,'Bezeichnung ist bereits vorhanden.') from exc
        return view(row)
    @router.post('/api/v1/admin/app-defaults/{category}',status_code=201,dependencies=[Depends(require_admin)])
    def create(category:Literal['reason','cause'],data:ValueInput,db:Session=Depends(database_session)):
        ensure_defaults(db)
        row=Value(category=category,value='custom-'+uuid4().hex[:24],label=data.label,label_key=data.label.casefold(),active=data.active,ever_used=False,revision=1);db.add(row)
        return commit(db,row)
    @router.put('/api/v1/admin/app-defaults/value/{value_id}',dependencies=[Depends(require_admin)])
    def update(value_id:int,data:ValueUpdate,db:Session=Depends(database_session)):
        row=db.scalar(select(Value).where(Value.id==value_id).with_for_update())
        if not row:raise HTTPException(404,'Auswahlwert nicht gefunden.')
        if row.revision!=data.expected_revision:raise HTTPException(409,'Auswahlwert wurde geändert. Bitte neu laden.')
        row.label=data.label;row.label_key=data.label.casefold();row.active=data.active;row.revision+=1
        return commit(db,row)
    @router.delete('/api/v1/admin/app-defaults/value/{value_id}',dependencies=[Depends(require_admin)])
    def remove(value_id:int,expected_revision:int=Query(ge=1),db:Session=Depends(database_session)):
        row=db.scalar(select(Value).where(Value.id==value_id).with_for_update())
        if not row:raise HTTPException(404,'Auswahlwert nicht gefunden.')
        if row.revision!=expected_revision:raise HTTPException(409,'Auswahlwert wurde geändert. Bitte neu laden.')
        if row.ever_used or (row.category,row.value) in historical_values(db):
            raise HTTPException(409,'Bereits verwendete Werte können nur deaktiviert werden.')
        db.delete(row);db.commit();return {'ok':True}
    return router
