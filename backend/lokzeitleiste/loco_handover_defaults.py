"""Administrative handover vocabulary, with category-owned damage locations."""
import re
from typing import Literal
from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel,Field,field_validator,EmailStr,TypeAdapter
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .db import database_session
from .models import LocoHandoverDefault as Value

Kind=Literal['recipient','pzb','category','damage']
BASE='/api/v1/admin/app-defaults/loco-handover'

class Input(BaseModel):
    label:str=Field(min_length=1,max_length=255)
    email:str=Field(default='',max_length=254)
    hotline_name:str=Field(default='',max_length=255)
    hotline_email:str=Field(default='',max_length=254)
    parent_id:int|None=Field(default=None,ge=1)
    @field_validator('label','email','hotline_name','hotline_email',mode='before')
    @classmethod
    def trim(cls,value):return value.strip() if isinstance(value,str) else value
    @field_validator('label')
    @classmethod
    def nonempty(cls,value):
        if not value:raise ValueError('Bezeichnung ist erforderlich.')
        return value
    @field_validator('email','hotline_email')
    @classmethod
    def valid_email(cls,value):
        if value:
            try:return str(TypeAdapter(EmailStr).validate_python(value))
            except ValueError:raise ValueError('Bitte eine gültige Emailadresse eingeben.')
        return value

class Update(Input):
    expected_revision:int=Field(ge=1)

def view(row):
    return {key:getattr(row,key) for key in ('id','kind','label','email','hotline_name','hotline_email','parent_id','revision')}

def apply(db,row,data):
    if row.kind=='category' and len(data.label)>100:raise HTTPException(422,'Kategorie darf maximal 100 Zeichen enthalten.')
    if row.kind=='recipient' and not data.email:raise HTTPException(422,'Emailadresse ist erforderlich.')
    if row.kind=='damage':
        parent=db.scalar(select(Value).where(Value.id==data.parent_id,Value.kind=='category').with_for_update())
        if not parent:raise HTTPException(422,'Bitte zuerst eine vorhandene Kategorie auswählen.')
    elif data.parent_id is not None:raise HTTPException(422,'Eine Kategoriezuordnung ist nur für Schadstellen zulässig.')
    row.label=data.label;row.label_key=data.label.casefold()
    row.parent_id=data.parent_id if row.kind=='damage' else None;row.scope_id=row.parent_id or 0
    row.email=data.email if row.kind=='recipient' else ''
    if row.kind=='category':
        if 'hotline_name' in data.model_fields_set:row.hotline_name=data.hotline_name
        if 'hotline_email' in data.model_fields_set:row.hotline_email=data.hotline_email
    else:row.hotline_name=row.hotline_email=''

def save(db,row):
    try:db.commit()
    except IntegrityError as exc:
        db.rollback();raise HTTPException(409,'Bezeichnung ist bereits vorhanden.') from exc
    return view(row)

def create_router(require_admin):
    router=APIRouter()
    @router.get('/admin/loco-handover-defaults.js',dependencies=[])
    def script():return FileResponse(Path(__file__).parent/'static'/'loco-handover-defaults.js',media_type='text/javascript',headers={'Cache-Control':'no-cache'})
    @router.get(BASE,dependencies=[Depends(require_admin)])
    def listing(db:Session=Depends(database_session)):
        return [view(row) for row in db.scalars(select(Value).order_by(Value.label,Value.id))]
    @router.post(BASE+'/{kind}',status_code=201,dependencies=[Depends(require_admin)])
    def create(kind:Kind,data:Input,db:Session=Depends(database_session)):
        row=Value(kind=kind,revision=1);apply(db,row,data);db.add(row);return save(db,row)
    @router.put(BASE+'/value/{value_id}',dependencies=[Depends(require_admin)])
    def update(value_id:int,data:Update,db:Session=Depends(database_session)):
        row=db.scalar(select(Value).where(Value.id==value_id).with_for_update())
        if not row:raise HTTPException(404,'Auswahlwert nicht gefunden.')
        if row.revision!=data.expected_revision:raise HTTPException(409,'Auswahlwert wurde geändert. Bitte neu laden.')
        apply(db,row,data);row.revision+=1;return save(db,row)
    return router
