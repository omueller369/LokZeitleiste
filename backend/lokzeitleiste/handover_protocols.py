"""Vehicle handover protocols with atomic attachment storage and snapshot details."""
import json,logging
from datetime import datetime
from typing import Literal
from urllib.parse import quote
from fastapi import APIRouter,Depends,HTTPException,Query,Form,File,UploadFile
from fastapi.responses import Response
from pydantic import BaseModel,Field,ValidationError,field_validator
from sqlalchemy import select,or_,case
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from .db import database_session
from .default_order import ordered
from .models import (RailwayVehicle,RailwayStation,LocoHandoverDefault,LocoHandoverProtocol as Protocol,
                     LocoHandoverAttachment as Attachment,LocoHandoverAttachmentChunk as Chunk,TfProfile,StaffProfile)
from .tf_portal import driver_dependency
from .vehicles import VEHICLE_STATUSES
from .work_reports.receipts import MAX_FILE,validate_receipt

CHUNK_SIZE=256*1024
log=logging.getLogger(__name__)

class ProtocolInput(BaseModel):
    occurred_at:datetime
    duty:Literal['keiner','V1','V3','A1','A1A','A2','A3']='keiner'
    train_number:str=Field(default='',pattern=r'^[0-9]{0,6}$')
    station_code:str=Field(min_length=1,max_length=10)
    notes:str=Field(default='',max_length=1000)
    recipient_id:int|None=Field(default=None,ge=1)
    meter_180:str=Field(default='',pattern=r'^[0-9]{0,8}$')
    meter_280:str=Field(default='',pattern=r'^[0-9]{0,8}$')
    mileage:str=Field(default='',pattern=r'^[0-9]{0,8}$')
    locomotive_data:bool=False
    @field_validator('occurred_at')
    @classmethod
    def local_time(cls,value):
        if value.tzinfo is not None:raise ValueError('Bitte lokale Datum/Uhrzeit ohne Zeitzone eingeben.')
        return value
    @field_validator('station_code')
    @classmethod
    def code(cls,value):return value.strip().upper()

from .vehicles import is_retired

def vehicle(db,vehicle_id):
    row=db.get(RailwayVehicle,vehicle_id)
    if not row or is_retired(db,vehicle_id):raise HTTPException(404,'Triebfahrzeug nicht gefunden.')
    return row

def protocol(db,vehicle_id,protocol_id):
    row=db.get(Protocol,protocol_id)
    if not row or row.vehicle_id!=vehicle_id:raise HTTPException(404,'Übergabeprotokoll nicht gefunden.')
    return row

def view(row):return dict(id=row.id,vehicle_id=row.vehicle_id,author_name=row.author_name,occurred_at=row.occurred_at.isoformat(timespec='minutes'),**{'locomotive_data':False,**json.loads(row.payload_json)})

def create_router(require_admin,require_account):
    router=APIRouter()
    def routes(prefix,access):
        sub=APIRouter(prefix=prefix)
        @sub.get('/recipients')
        def recipients(user=Depends(access),db:Session=Depends(database_session)):
            return [dict(id=r.id,label=r.label) for r in ordered(db,'recipient',db.scalars(select(LocoHandoverDefault).where(LocoHandoverDefault.kind=='recipient').order_by(LocoHandoverDefault.label,LocoHandoverDefault.id)))]
        @sub.get('/stations')
        def stations(q:str=Query(min_length=1,max_length=200),user=Depends(access),db:Session=Depends(database_session)):
            key=q.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
            if not key:return []
            return [dict(code=r.code,name=r.name) for r in db.scalars(select(RailwayStation).where(or_(RailwayStation.code.ilike(key+'%',escape='\\'),RailwayStation.name.ilike('%'+key+'%',escape='\\'))).order_by(case((RailwayStation.code==q.strip().upper(),0),else_=1),RailwayStation.code).limit(30))]
        @sub.get('/vehicles/{vehicle_id}/protocols')
        def listing(vehicle_id:int,user=Depends(access),db:Session=Depends(database_session)):
            vehicle(db,vehicle_id)
            return [view(r) for r in db.scalars(select(Protocol).where(Protocol.vehicle_id==vehicle_id).order_by(Protocol.occurred_at.desc(),Protocol.id.desc()))]
        @sub.post('/vehicles/{vehicle_id}/protocols',status_code=201)
        async def create(vehicle_id:int,payload:str=Form(max_length=10000),files:list[UploadFile]=File(default=[]),user=Depends(access),db:Session=Depends(database_session)):
            loco=vehicle(db,vehicle_id)
            try:data=ProtocolInput.model_validate_json(payload)
            except ValidationError as exc:raise HTTPException(422,'Bitte die Eingaben und Pflichtfelder prüfen.') from exc
            station=db.get(RailwayStation,data.station_code)
            if not station:raise HTTPException(422,'Bitte einen Bahnhof aus den Suchvorschlägen auswählen.')
            recipient=db.get(LocoHandoverDefault,data.recipient_id) if data.recipient_id else None
            if data.recipient_id and (not recipient or recipient.kind!='recipient'):raise HTTPException(422,'Bitte einen gültigen Meldungsempfänger auswählen.')
            if len(files)>10:raise HTTPException(422,'Maximal 10 Dateien pro Übergabeprotokoll.')
            attachments=[];total=0
            for file in files:
                content=await file.read(MAX_FILE+1);await file.close();total+=len(content)
                if total>30*1024*1024:raise HTTPException(422,'Dateien dürfen zusammen höchstens 30 MB groß sein.')
                try:name,mime,_=validate_receipt(file.filename,content)
                except ValueError as exc:raise HTTPException(422,str(exc)) from exc
                attachments.append((name,mime,content))
            profile=db.get(TfProfile,user.id) if user.role=='tf' else db.get(StaffProfile,user.id)
            author=(' '.join([profile.first_name,profile.last_name]).strip() if profile else ('Triebfahrzeugführer' if user.role=='tf' else user.username))
            snapshot=data.model_dump(mode='json',exclude={'occurred_at'})
            snapshot.update(station_name=station.name,recipient_name=recipient.label if recipient else '',recipient_email=recipient.email if recipient else '',vehicle_number=loco.vehicle_number,vehicle_status=loco.status,vehicle_status_label=VEHICLE_STATUSES[loco.status][0])
            try:
                row=Protocol(vehicle_id=vehicle_id,author_id=user.id,author_name=author,occurred_at=data.occurred_at,payload_json=json.dumps(snapshot,ensure_ascii=False));db.add(row);db.flush()
                for name,mime,content in attachments:
                    item=Attachment(protocol_id=row.id,filename=name,mime_type=mime,content=b'');db.add(item);db.flush()
                    for position,offset in enumerate(range(0,len(content),CHUNK_SIZE)):
                        db.add(Chunk(attachment_id=item.id,position=position,content=content[offset:offset+CHUNK_SIZE]))
                        db.flush()
                db.commit()
            except SQLAlchemyError as exc:
                db.rollback();log.error('Übergabeprotokoll konnte nicht gespeichert werden (Fahrzeug %s, Fehlerklasse %s).',vehicle_id,type(exc).__name__)
                raise HTTPException(503,'Speichern fehlgeschlagen. Protokoll und Dateien wurden nicht gespeichert. Bitte erneut versuchen.') from exc
            return view(row)
        @sub.get('/vehicles/{vehicle_id}/protocols/{protocol_id}')
        def details(vehicle_id:int,protocol_id:int,user=Depends(access),db:Session=Depends(database_session)):
            row=protocol(db,vehicle_id,protocol_id)
            return dict(**view(row),files=[dict(id=f.id,filename=f.filename,mime_type=f.mime_type) for f in db.scalars(select(Attachment).where(Attachment.protocol_id==protocol_id).order_by(Attachment.id))])
        @sub.get('/vehicles/{vehicle_id}/protocols/{protocol_id}/files/{file_id}')
        def download(vehicle_id:int,protocol_id:int,file_id:int,preview:bool=False,user=Depends(access),db:Session=Depends(database_session)):
            protocol(db,vehicle_id,protocol_id);file=db.get(Attachment,file_id)
            if not file or file.protocol_id!=protocol_id:raise HTTPException(404,'Datei nicht gefunden.')
            content=file.content or b''.join(db.scalars(select(Chunk.content).where(Chunk.attachment_id==file.id).order_by(Chunk.position)))
            disposition='inline' if preview and file.mime_type in ('image/jpeg','image/png') else 'attachment'
            return Response(content,media_type=file.mime_type,headers={'Content-Disposition':disposition+"; filename*=UTF-8''"+quote(file.filename,safe=''),'X-Content-Type-Options':'nosniff','Cache-Control':'no-store'})
        router.include_router(sub)
    routes('/api/v1/admin/loco-handover',require_admin)
    routes('/api/v1/tf/loco-handover',driver_dependency(require_account))
    return router
