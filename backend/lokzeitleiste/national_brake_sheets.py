"""Private national freight brake sheets; no mail dispatch endpoints."""
import json,re
from datetime import date
from decimal import Decimal,ROUND_CEILING
from pathlib import Path
from typing import Literal
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse,Response
from pydantic import BaseModel,Field,ValidationError,field_validator,model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import database_session
from .models import NationalBrakeSheetDraft,User,TfProfile,now_utc
from .tf_portal import driver_dependency
from .brake_sheets import Sheet as InternationalSheet,Loco,calculate as international_calculate

class Train(BaseModel):
    number:str=''
    station:str=Field(default='',max_length=16)
    @field_validator('number')
    @classmethod
    def number_format(cls,v):
        if v and not re.fullmatch('[0-9]{5}',v):raise ValueError('Zugnummer benötigt genau fünf Ziffern.')
        return v
    @field_validator('station')
    @classmethod
    def station_format(cls,v):
        v=v.strip().upper()
        if v and not re.fullmatch('[A-Z0-9][A-Z0-9 -]{0,15}',v):raise ValueError('Betriebsstelle nur als DS100-Kürzel eingeben.')
        return v
class Vehicle(BaseModel):
    vehicle_id:int=Field(gt=0)
    vehicle_revision:int=Field(ge=1)
class Speed(BaseModel):
    lower:bool=False
    value:int|None=Field(default=None,ge=0,le=5000,strict=True)
    @model_validator(mode='after')
    def disabled(self):
        if not self.lower:self.value=None
        return self
class Sheet(BaseModel):
    departure_date:date|None=None
    trains:list[Train]=Field(default_factory=lambda:[Train()],min_length=1,max_length=20)
    locos:list[Vehicle]=Field(default_factory=list,max_length=2)
    brake_mode:Literal['G','P','R']='G'
    wagon_weight:int|None=Field(default=None,ge=0,le=5000,strict=True)
    wagon_brake:int|None=Field(default=None,ge=0,le=5000,strict=True)
    wagon_axles:int|None=Field(default=None,ge=0,le=5000,strict=True)
    required_percent:int|None=Field(default=None,ge=0,le=5000,strict=True)
    last_vehicle:str=''
    brakes_single:int|None=Field(default=None,ge=0,le=5000,strict=True)
    brakes_multi:int|None=Field(default=None,ge=0,le=5000,strict=True)
    brakes_d:int|None=Field(default=None,ge=0,le=5000,strict=True)
    brakes_k:int|None=Field(default=None,ge=0,le=5000,strict=True)
    brakes_matrossow:int|None=Field(default=None,ge=0,le=5000,strict=True)
    wagon_length:int|None=Field(default=None,ge=0,le=5000,strict=True)
    braked_axles:int|None=Field(default=None,ge=0,le=5000,strict=True)
    speeds:list[Speed]=Field(default_factory=lambda:[Speed(),Speed(),Speed()],min_length=3,max_length=3)
    dangerous:bool=True
    extra:bool=False
    extra_text:str=Field(default='',max_length=256)
    @field_validator('last_vehicle')
    @classmethod
    def last_number(cls,v):
        if v and not re.fullmatch('[0-9]{12}',v):raise ValueError('Letztes Fahrzeug benötigt zwölf Ziffern.')
        return v
    @model_validator(mode='after')
    def unique(self):
        if len({v.vehicle_id for v in self.locos})!=len(self.locos):raise ValueError('Tfz wurde doppelt ausgewählt.')
        if not self.extra:self.extra_text=''
        return self
class Save(BaseModel):
    expected_revision:int=Field(ge=0)
    sheet:Sheet
class Revision(BaseModel):
    expected_revision:int=Field(ge=1)

def calculate(db,sheet):
    source=international_calculate(db,InternationalSheet(brake_mode='G+P' if sheet.brake_mode=='G' else sheet.brake_mode,locos=[Loco(**v.model_dump()) for v in sheet.locos]))
    lines=source['lines'];a=source['a']
    axles=sum(v['axle_count'] for v in lines) if lines and all(v['axle_count'] is not None for v in lines) else None
    loco=dict(weight=a['weight'],brake=a['brake'],axles=axles,length=a['length'])
    wagon=dict(weight=sheet.wagon_weight,brake=sheet.wagon_brake,axles=sheet.wagon_axles,length=sheet.wagon_length)
    totals={k:(loco[k]+wagon[k] if loco[k] is not None and wagon[k] is not None else None) for k in loco}
    available=int(totals['brake']*100/totals['weight']) if totals['brake'] is not None and totals['weight'] is not None and totals['weight']>0 else None
    delta=available-sheet.required_percent if available is not None and sheet.required_percent is not None else None
    missing=[]
    if not lines:missing.append('Triebfahrzeug')
    for i,line in enumerate(lines):
        for k,label in [('weight_kg','Gewicht'),('brake_weight','Bremsgewicht'),('axle_count','Radsätze'),('length_m','Länge')]:
            if line[k] is None:missing.append(f'Tfz {i+1}: {label} in Stammdaten ergänzen')
    if sheet.departure_date is None:missing.append('Datum')
    if not sheet.trains[0].number:missing.append('Erste Zugnummer')
    for i,t in enumerate(sheet.trains):
        if t.number and not t.station:missing.append(f'DS100 zur Zugnummer {i+1}')
        if t.station and not t.number:missing.append(f'Zugnummer {i+1}')
    for key,label in [('wagon_weight','Wagenzuggewicht'),('wagon_brake','Wagenzug-Bremsgewicht'),('wagon_axles','Wagenzug-Achszahl'),('required_percent','Mindestbremshundertstel'),('wagon_length','Wagenzuglänge'),('braked_axles','Gebremste Achsen')]:
        if getattr(sheet,key) is None:missing.append(label)
    for i,speed in enumerate(sheet.speeds):
        if speed.lower and speed.value is None:missing.append(f'Geschwindigkeit in Spalte {i+4}')
    return dict(loco=loco,wagon=wagon,total=totals,available=available,missing=delta if delta is not None and delta<0 else '/' if delta is not None else None,required_axles=sheet.wagon_axles*9//10 if sheet.wagon_axles is not None else None,preview_missing=missing)

def create_router(require_account):
    router=APIRouter();driver=driver_dependency(require_account);base='/api/v1/tf/national-brake-sheets';static=Path(__file__).parent/'static'
    @router.get('/tf/national-brake-sheet.js')
    def script():return FileResponse(static/'national-brake-sheet.js',media_type='text/javascript',headers={'Cache-Control':'no-cache'})
    @router.get('/tf/national-brake-sheet.css')
    def style():return FileResponse(static/'national-brake-sheet.css',media_type='text/css',headers={'Cache-Control':'no-cache'})
    def owned(db,user,id):
        row=db.scalar(select(NationalBrakeSheetDraft).where(NationalBrakeSheetDraft.id==str(id),NationalBrakeSheetDraft.owner_id==user.id).with_for_update())
        if not row:raise HTTPException(404,'Deutscher Bremszettel nicht gefunden.')
        return row
    def view(row):return dict(id=row.id,revision=row.revision,sheet=json.loads(row.payload_json),calculation=json.loads(row.calculation_json),created_by_name=row.created_by_name,created_at=row.created_at.isoformat()+'Z')
    @router.get(base)
    def listing(user=Depends(driver),db:Session=Depends(database_session)):
        return [dict(id=r.id,revision=r.revision,updated_at=r.updated_at,departure_date=json.loads(r.payload_json)['departure_date'],trains=json.loads(r.payload_json)['trains']) for r in db.scalars(select(NationalBrakeSheetDraft).where(NationalBrakeSheetDraft.owner_id==user.id).order_by(NationalBrakeSheetDraft.updated_at.desc()))]
    @router.post(base+'/calculate')
    def calc(data:Sheet,user=Depends(driver),db:Session=Depends(database_session)):return calculate(db,data)
    @router.get(base+'/{id}')
    def detail(id:UUID,user=Depends(driver),db:Session=Depends(database_session)):return view(owned(db,user,id))
    @router.put(base+'/{id}')
    def save(id:UUID,data:Save,user=Depends(driver),db:Session=Depends(database_session)):
        db.scalar(select(User).where(User.id==user.id).with_for_update());row=db.get(NationalBrakeSheetDraft,str(id))
        if row and row.owner_id!=user.id:raise HTTPException(404,'Bremszettel nicht gefunden.')
        if (row.revision if row else 0)!=data.expected_revision:raise HTTPException(409,'Entwurf wurde auf einem anderen Gerät geändert. Bitte neu laden.')
        result=calculate(db,data.sheet)
        if not row:
            profile=db.get(TfProfile,user.id)
            if not profile:raise HTTPException(404,'TF nicht gefunden.')
            row=NationalBrakeSheetDraft(id=str(id),owner_id=user.id,revision=0,created_at=now_utc(),created_by_name=(profile.first_name+' '+profile.last_name).strip());db.add(row)
        row.payload_json=data.sheet.model_dump_json();row.calculation_json=json.dumps(jsonable_encoder(result));row.revision+=1;row.updated_at=now_utc();db.commit();return view(row)
    def ready(db,user,id,data):
        row=owned(db,user,id)
        if row.revision!=data.expected_revision:raise HTTPException(409,'Entwurf wurde geändert. Bitte neu laden.')
        try:sheet=Sheet.model_validate_json(row.payload_json)
        except ValidationError as exc:raise HTTPException(422,'Bitte den Entwurf laden und die Zugparameter als ganze Zahlen von 0 bis 5000 korrigieren.') from exc
        result=calculate(db,sheet)
        if result['preview_missing']:raise HTTPException(422,'Bitte ergänzen: '+', '.join(result['preview_missing']))
        return row,sheet,result
    @router.post(base+'/{id}/preview')
    def preview(id:UUID,data:Revision,user=Depends(driver),db:Session=Depends(database_session)):
        row,sheet,result=ready(db,user,id,data)
        from .national_brake_image import render
        try:content=render(sheet,result,row.created_by_name,image=True)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        return Response(content,media_type='image/png',headers={'Cache-Control':'no-store'})
    @router.post(base+'/{id}/archive')
    def archive(id:UUID,data:Revision,user=Depends(driver),db:Session=Depends(database_session)):
        row,sheet,result=ready(db,user,id,data)
        from .national_brake_image import render
        from .documents.storage import generated
        try:pdf=render(sheet,result,row.created_by_name)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        d=sheet.departure_date;n=sheet.trains[0].number;name=f'Bremszettel-DE-{n}-{d.isoformat()}.PDF'
        path=f'Dokumente/Zugfahrten/{d.year:04}/{d.month:02}/{d.day:02}/{n}/{name}'
        document=generated(db,user,path,pdf,'national-brake-sheet:'+row.id);db.commit()
        return dict(filename=document.display_name,document_path=document.relative_path,download_url='/api/v1/documents/download?path='+__import__('urllib.parse',fromlist=['quote']).quote(document.relative_path,safe=''))
    return router
