"""Private, per-driver station contacts and station plans."""
import json
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter,Depends,HTTPException,File,Form,UploadFile,Query
from fastapi.responses import FileResponse,Response
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import select,or_,case
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db import database_session
from .models import User,RailwayStation,TfStation,TfStationPlan,TfStationNotes
from .tf_portal import driver_dependency
from .work_reports.receipts import MAX_FILE,validate_receipt


class StationContact(BaseModel):
    category:Literal['landline','mobile','bada','long_dial','local_radio']
    label:str=Field(min_length=1,max_length=100)
    number:str=Field(min_length=1,max_length=60)

    @field_validator('label','number')
    @classmethod
    def clean(cls,value):
        value=value.strip()
        if not value or any(ord(c)<32 or ord(c)==127 for c in value):
            raise ValueError('Bezeichnung und Nummer erforderlich.')
        return value


NOTE_FIELDS=('locomotive_parking','train_securing','special_features')

class StationNotes(BaseModel):
    locomotive_parking:str=Field(default='',max_length=120)
    train_securing:str=Field(default='',max_length=120)
    special_features:str=Field(default='',max_length=1024)


def notes_view(db,model,key):
    row=db.get(model,key)
    return {field:getattr(row,field) if row else '' for field in NOTE_FIELDS}


def save_notes(db,station_id,data):
    fields=set(NOTE_FIELDS)&data.model_fields_set
    if not fields:return
    row=db.get(TfStationNotes,station_id)
    if not row:row=TfStationNotes(station_id=station_id);db.add(row)
    for field in fields:setattr(row,field,getattr(data,field))


class StationCreate(StationNotes):
    code:str=Field(min_length=1,max_length=10)
    contacts:list[StationContact]=Field(default_factory=list,max_length=100)

    @field_validator('code')
    @classmethod
    def code_clean(cls,value):return value.strip().upper()


class StationUpdate(StationNotes):
    expected_revision:int=Field(ge=1)
    contacts:list[StationContact]=Field(default_factory=list,max_length=100)


def contacts_json(contacts):
    value=json.dumps([row.model_dump() for row in contacts],ensure_ascii=False)
    if len(value.encode('utf8'))>60000:
        raise HTTPException(422,'Zu viele Kontaktdaten für einen Bahnhof.')
    return value


def create_router(require_account):
    router=APIRouter()
    driver=driver_dependency(require_account)

    def owned(db,user,station_id,lock=False):
        if lock:db.scalar(select(User).where(User.id==user.id).with_for_update())
        query=select(TfStation).where(TfStation.id==station_id,TfStation.owner_id==user.id)
        row=db.scalar(query.with_for_update() if lock else query)
        if not row:raise HTTPException(404,'Bahnhofseintrag nicht gefunden.')
        return row

    def check_revision(row,revision):
        if row.revision!=revision:
            raise HTTPException(409,'Bahnhofseintrag wurde geändert. Bitte neu laden.')

    def view(db,row):
        plan=db.get(TfStationPlan,row.id)
        return dict(**notes_view(db,TfStationNotes,row.id),id=row.id,code=row.code,name=row.name,contacts=json.loads(row.contacts_json),revision=row.revision,
                    plan=dict(filename=plan.filename,mime_type=plan.mime_type) if plan else None)

    @router.get('/tf/stations.js')
    def script():
        return FileResponse(Path(__file__).parent/'static'/'stations.js',media_type='text/javascript',headers={'Cache-Control':'no-cache'})

    @router.get('/api/v1/tf/stations/catalog')
    def search_catalog(q:str=Query(min_length=1,max_length=255),user:User=Depends(driver),db:Session=Depends(database_session)):
        query=q.strip().upper()
        if not query:return []
        escaped=query.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        rows=db.scalars(select(RailwayStation).where(or_(RailwayStation.code.ilike(escaped+'%',escape='\\'),
            RailwayStation.name.ilike('%'+escaped+'%',escape='\\'))).order_by(
                case((RailwayStation.code==query,0),(RailwayStation.code.ilike(escaped+'%',escape='\\'),1),else_=2),RailwayStation.code).limit(30))
        return [dict(code=row.code,name=row.name) for row in rows]

    @router.get('/api/v1/tf/stations')
    def listing(q:str=Query(default='',max_length=255),user:User=Depends(driver),db:Session=Depends(database_session)):
        query=select(TfStation).where(TfStation.owner_id==user.id)
        value=q.strip().upper().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        if value:query=query.where(or_(TfStation.code.ilike('%'+value+'%',escape='\\'),TfStation.name.ilike('%'+value+'%',escape='\\')))
        return [dict(id=row.id,code=row.code,name=row.name,revision=row.revision) for row in db.scalars(query.order_by(TfStation.code,TfStation.id))]

    @router.post('/api/v1/tf/stations',status_code=201)
    def create(data:StationCreate,user:User=Depends(driver),db:Session=Depends(database_session)):
        db.scalar(select(User).where(User.id==user.id).with_for_update())
        station=db.get(RailwayStation,data.code)
        if not station:raise HTTPException(422,'Bitte einen Bahnhof aus den Suchvorschlägen auswählen.')
        existing=db.scalar(select(TfStation).where(TfStation.owner_id==user.id,TfStation.code==station.code).with_for_update())
        if existing:raise HTTPException(409,'Bahnhof ist bereits in Ihrer Liste.')
        row=TfStation(owner_id=user.id,code=station.code,name=station.name,contacts_json=contacts_json(data.contacts),revision=1)
        db.add(row)
        db.flush();save_notes(db,row.id,data)
        try:db.commit()
        except IntegrityError as exc:
            db.rollback();raise HTTPException(409,'Bahnhof ist bereits in Ihrer Liste.') from exc
        return view(db,row)

    @router.get('/api/v1/tf/stations/{station_id}')
    def details(station_id:int,user:User=Depends(driver),db:Session=Depends(database_session)):
        return view(db,owned(db,user,station_id))

    @router.put('/api/v1/tf/stations/{station_id}')
    def edit(station_id:int,data:StationUpdate,user:User=Depends(driver),db:Session=Depends(database_session)):
        row=owned(db,user,station_id,True);check_revision(row,data.expected_revision)
        row.contacts_json=contacts_json(data.contacts);save_notes(db,row.id,data);row.revision+=1;db.commit()
        return view(db,row)

    @router.delete('/api/v1/tf/stations/{station_id}')
    def remove(station_id:int,expected_revision:int=Query(ge=1),user:User=Depends(driver),db:Session=Depends(database_session)):
        row=owned(db,user,station_id,True);check_revision(row,expected_revision)
        plan=db.get(TfStationPlan,row.id)
        if plan:db.delete(plan);db.flush()
        db.delete(row);db.commit();return {'ok':True}

    @router.put('/api/v1/tf/stations/{station_id}/plan')
    async def upload_plan(station_id:int,expected_revision:int=Form(ge=1),file:UploadFile=File(...),
                          user:User=Depends(driver),db:Session=Depends(database_session)):
        row=owned(db,user,station_id,True);check_revision(row,expected_revision)
        content=await file.read(MAX_FILE+1)
        if not content or len(content)>MAX_FILE:raise HTTPException(413,'Dokument darf höchstens 10 MB groß sein.')
        try:filename,mime,_=validate_receipt(file.filename,content)
        except ValueError as exc:raise HTTPException(422,'Bahnhofsplan muss eine gültige PDF-, JPEG- oder PNG-Datei sein.') from exc
        plan=db.get(TfStationPlan,row.id)
        if not plan:plan=TfStationPlan(station_id=row.id);db.add(plan)
        plan.filename=filename;plan.mime_type=mime;plan.content=content;row.revision+=1;db.commit()
        return view(db,row)

    @router.get('/api/v1/tf/stations/{station_id}/plan')
    def download_plan(station_id:int,user:User=Depends(driver),db:Session=Depends(database_session)):
        row=owned(db,user,station_id);plan=db.get(TfStationPlan,row.id)
        if not plan:raise HTTPException(404,'Kein Bahnhofsplan vorhanden.')
        return Response(plan.content,media_type=plan.mime_type,headers={
            'Content-Disposition':"attachment; filename*=UTF-8''"+quote(plan.filename,safe=''),
            'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})

    @router.delete('/api/v1/tf/stations/{station_id}/plan')
    def remove_plan(station_id:int,expected_revision:int=Query(ge=1),user:User=Depends(driver),db:Session=Depends(database_session)):
        row=owned(db,user,station_id,True);check_revision(row,expected_revision)
        plan=db.get(TfStationPlan,row.id)
        if plan:db.delete(plan)
        row.revision+=1;db.commit();return view(db,row)

    from .station_sharing import create_router as sharing_router
    router.include_router(sharing_router(driver))
    return router
