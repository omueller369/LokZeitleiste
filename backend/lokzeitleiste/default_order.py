"""Persistent, revision-checked selection ordering; no changes to stable value IDs."""
import json,re
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import BaseModel,Field,model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .db import database_session
from .models import AppDefaultOrder,AppDefaultValue,LocoHandoverDefault,EmailDomain

def ordered(db,scope,rows):
    rows=list(rows);order=db.get(AppDefaultOrder,scope)
    if not order:return rows
    ranks={value:index for index,value in enumerate(json.loads(order.ids_json))}
    return sorted(rows,key=lambda row:ranks.get(row.id,len(ranks)))
def ordered_loco(db,rows):
    rows=list(rows);result=[]
    for kind in ('recipient','pzb','category'):
        result+=ordered(db,kind,[r for r in rows if r.kind==kind])
    for parent in dict.fromkeys(r.parent_id for r in rows if r.kind=='damage'):
        result+=ordered(db,'damage:'+str(parent),[r for r in rows if r.kind=='damage' and r.parent_id==parent])
    return result

def scope_rows(db,scope):
    if scope in ('reason','cause'):
        return list(db.scalars(select(AppDefaultValue).where(AppDefaultValue.category==scope).order_by(AppDefaultValue.id)))
    if scope=='email-domains':return list(db.scalars(select(EmailDomain).order_by(EmailDomain.name,EmailDomain.id)))
    if scope in ('recipient','pzb','category'):
        query=select(LocoHandoverDefault).where(LocoHandoverDefault.kind==scope)
    elif re.fullmatch(r'damage:[1-9][0-9]*',scope):
        query=select(LocoHandoverDefault).where(LocoHandoverDefault.kind=='damage',LocoHandoverDefault.parent_id==int(scope.split(':')[1]))
    else:raise HTTPException(422,'Ungültige Sortierliste.')
    return list(db.scalars(query.order_by(LocoHandoverDefault.label,LocoHandoverDefault.id)))
class OrderInput(BaseModel):
    ids:list[int]=Field(min_length=3,max_length=10000)
    expected_revision:int=Field(ge=0)
    @model_validator(mode='after')
    def unique(self):
        if len(self.ids)!=len(set(self.ids)):raise ValueError('Doppelte Einträge sind nicht zulässig.')
        return self

def create_router(require_admin):
    router=APIRouter()
    @router.get('/admin/default-sort.js')
    def script():return FileResponse(Path(__file__).parent/'static/default-sort.js',media_type='text/javascript',headers={'Cache-Control':'no-cache'})
    @router.get('/api/v1/admin/app-defaults/order/{scope}',dependencies=[Depends(require_admin)])
    def get_order(scope:str,db:Session=Depends(database_session)):
        rows=ordered(db,scope,scope_rows(db,scope));record=db.get(AppDefaultOrder,scope)
        return dict(ids=[r.id for r in rows],revision=record.revision if record else 0)
    @router.put('/api/v1/admin/app-defaults/order/{scope}',dependencies=[Depends(require_admin)])
    def save_order(scope:str,data:OrderInput,db:Session=Depends(database_session)):
        # Serialise concurrent reorders, also when no order record exists yet.
        rows=scope_rows(db,scope)
        if not rows or set(data.ids)!={r.id for r in rows}:raise HTTPException(409,'Liste wurde geändert. Bitte neu laden.')
        record=db.scalar(select(AppDefaultOrder).where(AppDefaultOrder.scope==scope).with_for_update())
        if data.expected_revision!=(record.revision if record else 0):raise HTTPException(409,'Sortierung wurde geändert. Bitte neu laden.')
        if record:record.ids_json=json.dumps(data.ids);record.revision+=1
        else:record=AppDefaultOrder(scope=scope,ids_json=json.dumps(data.ids),revision=1);db.add(record)
        try:db.commit()
        except IntegrityError as exc:
            db.rollback();raise HTTPException(409,'Sortierung wurde geändert. Bitte neu laden.') from exc
        return dict(ids=data.ids,revision=record.revision)
    return router
