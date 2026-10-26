"""Private brake-sheet drafts and calculations according to the agreed DE/PL form rules."""
import json,re
from datetime import date
from decimal import Decimal,ROUND_CEILING
from pathlib import Path
from typing import Literal
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import FileResponse,Response
from pydantic import BaseModel,Field,field_validator,model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import database_session
from .models import BrakeSheetDraft,RailwayVehicle,VehicleRetirement,TfProfile,User,now_utc
from .tf_portal import driver_dependency
from .vehicles import vehicle_view,is_retired

class Country(BaseModel):
    country:Literal['DE','PL']|None=None
    category:Literal['G','P']|None=None
    vmax:Literal[80,90,100,110,120]=100
class Loco(BaseModel):
    vehicle_id:int=Field(gt=0)
    vehicle_revision:int=Field(ge=1)
    position:Literal['G','P','R']='G'
    note:str=Field(default='',max_length=20)
    manual_brake:Decimal|None=Field(default=None,ge=0,le=9999,decimal_places=3,allow_inf_nan=False)
class WagonValues(BaseModel):
    count:int|None=Field(default=None,ge=1,le=50,strict=True)
    length:Decimal|None=Field(default=None,ge=10,le=720,decimal_places=3,allow_inf_nan=False)
    holding:Decimal|None=Field(default=None,ge=0,max_digits=15,decimal_places=3,allow_inf_nan=False)
    brake:Decimal|None=Field(default=None,ge=100,le=5000,decimal_places=3,allow_inf_nan=False)
    weight:Decimal|None=Field(default=None,ge=100,le=5000,decimal_places=3,allow_inf_nan=False)
class Sheet(BaseModel):
    issuer:Literal['CTL DE','CTL PL']|None=None
    train_numbers:list[str]=Field(default_factory=lambda:['',''],min_length=1,max_length=20)
    departure_date:date|None=None
    station_from:str=Field(default='',max_length=270)
    station_to:str=Field(default='',max_length=270)
    countries:list[Country]=Field(default_factory=lambda:[Country() for _ in range(4)],min_length=4,max_length=4)
    remarks:str=Field(default='',max_length=500)
    special:str=Field(default='',max_length=500)
    dangerous:bool=True
    exceptional:bool=False
    restrictions:bool=False
    waste:bool=False
    class_de:Literal['D3','D4']|None=None
    class_pl:Literal['C','D']|None=None
    brake_mode:Literal['G','P','G+P','LL+P','R']='G'
    section_from:str=Field(default='',max_length=270)
    section_to:str=Field(default='',max_length=270)
    first_vehicle:str=''
    last_vehicle:str=''
    second_from:str=Field(default='',max_length=270)
    second_to:str=Field(default='',max_length=270)
    second_first_vehicle:str=''
    second_last_vehicle:str=''
    locos:list[Loco]=Field(default_factory=list,max_length=5)
    wagon:WagonValues=Field(default_factory=WagonValues)
    holding_loco:Decimal|None=Field(default=None,ge=0,le=9999,decimal_places=3,allow_inf_nan=False)
    holding_unit:Literal['t','kN']|None=None
    required_percent:int|None=Field(default=None,ge=50,le=150,strict=True)

    @field_validator('train_numbers')
    @classmethod
    def numbers(cls,values):
        if any(v and not re.fullmatch(r'[0-9]{5}',v) for v in values):raise ValueError('Zugnummern müssen aus fünf Ziffern bestehen.')
        return values
    @field_validator('first_vehicle','last_vehicle','second_first_vehicle','second_last_vehicle')
    @classmethod
    def number(cls,value):
        if value and not re.fullmatch(r'[0-9]{12}',value):raise ValueError('Fahrzeugnummer muss aus zwölf Ziffern bestehen.')
        return value
    @model_validator(mode='after')
    def rules(self):
        self.section_from=self.station_from;self.section_to=self.station_to
        if self.second_from or self.second_to or self.second_first_vehicle or self.second_last_vehicle:raise ValueError('Der zweite Gültigkeitsabschnitt bleibt vorerst leer.')
        if self.class_de=='D4':self.class_pl='D'
        if len({x.vehicle_id for x in self.locos})!=len(self.locos):raise ValueError('Triebfahrzeug ist bereits ausgewählt.')
        return self
class Save(BaseModel):
    expected_revision:int=Field(ge=0)
    sheet:Sheet

def public_vehicle(row):
    data=vehicle_view(row)
    keys=('id','revision','vehicle_number','series','name','length_m','weight_kg','axle_count','brake_shoe','brake_g','brake_g_25','brake_p','brake_r','spring_brake','spring_unit','status','status_label')
    return {k:data[k] for k in keys}

def calculate(db,data):
    lines=[]
    for item in data.locos:
        row=db.get(RailwayVehicle,item.vehicle_id)
        if not row or is_retired(db,row.id):raise HTTPException(422,'Ein ausgewähltes Triebfahrzeug steht nicht mehr zur Verfügung.')
        if row.revision!=item.vehicle_revision:raise HTTPException(409,'Tfz-Stammdaten wurden geändert. Bitte die Fahrzeugauswahl aktualisieren.')
        v=public_vehicle(row);mode=data.brake_mode
        position='G' if mode in ('G','G+P') else mode if mode in ('P','R') else item.position
        brake=Decimal(v['brake_g_25'] if mode=='G+P' else v['brake_'+position.lower()]) if mode!='LL+P' else item.manual_brake
        lines.append(dict(**v,position=position,brake_weight=brake,note=item.note))
    def total(key,scale=1):
        if not lines or any(v[key] is None for v in lines):return None
        return sum((Decimal(str(v[key])) for v in lines),Decimal(0))/scale
    a=dict(count=len(lines),length=total('length_m'),holding=data.holding_loco,brake=total('brake_weight'),weight=total('weight_kg',1000))
    if a['length'] is not None:a['length']=a['length'].to_integral_value(rounding=ROUND_CEILING)
    b=data.wagon.model_dump();summed={key:(value+Decimal(b[key] or 0) if value is not None else None) for key,value in a.items()}
    if data.holding_loco is None and b['holding'] is not None:summed['holding']=Decimal(b['holding'])
    if not data.holding_unit:summed['holding']=None
    available=int(summed['brake']*100/summed['weight']) if summed['brake'] is not None and summed['weight'] is not None and summed['weight']>0 else None
    difference=available-data.required_percent if available is not None and data.required_percent is not None else None
    result=dict(lines=lines,a=a,b=b,total=summed,available=available,required=data.required_percent,missing=difference if difference is not None and difference<0 else '/' if difference is not None else None,cast_iron='/')

    result['preview_missing']=preview_missing(data,result)
    return result

def preview_missing(data,result):
    missing=[]
    for key,label in [('issuer','1. Aussteller-EVU'),('departure_date','3. Abfahrtsdatum'),('station_from','4a. Gültig ab Bahnhof'),('station_to','4b. Gültig bis Bahnhof'),('class_de','14. Streckenklasse DE'),('class_pl','14. Streckenklasse PL'),('first_vehicle','Erstes Fahrzeug'),('last_vehicle','Letztes Fahrzeug'),('required_percent','25. Erforderliche Bremshundertstel')]:
        value=getattr(data,key)
        if value is None or isinstance(value,str) and not value.strip():missing.append(label)
    if not data.train_numbers[0]:missing.append('DE-Zugnummer')
    for i,c in enumerate(data.countries):
        if i<2 or c.country or c.category:
            if not c.country or not c.category:missing.append('Ländercode / Zugkategorie '+str(i+1))
    if not result['lines']:missing.append('Triebfahrzeug')
    for i,line in enumerate(result['lines']):
        for key,label in [('series','Baureihe'),('length_m','LüP'),('weight_kg','Gesamtgewicht'),('axle_count','Anzahl Radsätze'),('brake_shoe','Bremssohlenart'),('brake_weight','Bremsgewicht')]:
            if line[key] is None or line[key]=='':missing.append('Tfz '+str(i+1)+': '+label)
    for key,label in [('count','19b'),('length','20b'),('brake','22b'),('weight','23b')]:
        if getattr(data.wagon,key) is None:missing.append(label)
    if (data.holding_loco is not None or data.wagon.holding is not None) and not data.holding_unit:missing.append('Einheit Festhaltekraft')
    return missing

class PreviewRequest(BaseModel):
    expected_revision:int=Field(ge=1)

def create_router(require_account):
    router=APIRouter();driver=driver_dependency(require_account);static=Path(__file__).parent/'static'
    @router.get('/tf/brake-sheet.js')
    def script():return FileResponse(static/'brake-sheet.js',media_type='text/javascript',headers={'Cache-Control':'no-cache'})
    @router.get('/tf/brake-sheet.css')
    def style():return FileResponse(static/'brake-sheet.css',media_type='text/css',headers={'Cache-Control':'no-cache'})
    @router.get('/api/v1/tf/brake-sheets/vehicles')
    def vehicles(user=Depends(driver),db:Session=Depends(database_session)):
        return [public_vehicle(r) for r in db.scalars(select(RailwayVehicle).where(~RailwayVehicle.id.in_(select(VehicleRetirement.vehicle_id))).order_by(RailwayVehicle.vehicle_number))]
    @router.post('/api/v1/tf/brake-sheets/calculate')
    def preview(data:Sheet,user=Depends(driver),db:Session=Depends(database_session)):return calculate(db,data)
    @router.get('/api/v1/tf/brake-sheets')
    def listing(user=Depends(driver),db:Session=Depends(database_session)):
        return [dict(id=r.id,revision=r.revision,updated_at=r.updated_at,train_numbers=json.loads(r.payload_json)['train_numbers']) for r in db.scalars(select(BrakeSheetDraft).where(BrakeSheetDraft.owner_id==user.id).order_by(BrakeSheetDraft.updated_at.desc()))]
    def creation(row):return dict(created_at=row.created_at.isoformat()+'Z',created_by_name=row.created_by_name)
    def owned(db,user,id):
        row=db.scalar(select(BrakeSheetDraft).where(BrakeSheetDraft.id==str(id),BrakeSheetDraft.owner_id==user.id).with_for_update())
        if not row:raise HTTPException(404,'Bremszettel nicht gefunden.')
        return row
    @router.get('/api/v1/tf/brake-sheets/{id}')
    def detail(id:UUID,user=Depends(driver),db:Session=Depends(database_session)):
        row=owned(db,user,id)
        return dict(id=row.id,revision=row.revision,sheet=json.loads(row.payload_json),calculation=json.loads(row.calculation_json),**creation(row))
    @router.post('/api/v1/tf/brake-sheets/{id}/preview')
    def image_preview(id:UUID,data:PreviewRequest,user=Depends(driver),db:Session=Depends(database_session)):
        row=owned(db,user,id)
        if row.revision!=data.expected_revision:raise HTTPException(409,'Bremszettel wurde auf einem anderen Gerät geändert. Bitte neu laden.')
        sheet=Sheet.model_validate_json(row.payload_json);result=calculate(db,sheet)
        if result['preview_missing']:raise HTTPException(422,'Bitte Pflichtangaben ergänzen: '+', '.join(result['preview_missing']))
        from .brake_sheet_image import render
        try:content=render(sheet,result,row.created_at,row.created_by_name)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        return Response(content,media_type='image/png',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Content-Disposition':'inline; filename="bremszettel-vorschau.png"'})
    @router.put('/api/v1/tf/brake-sheets/{id}')
    def save(id:UUID,data:Save,user=Depends(driver),db:Session=Depends(database_session)):
        from fastapi.encoders import jsonable_encoder
        db.scalar(select(User).where(User.id==user.id).with_for_update())
        row=db.get(BrakeSheetDraft,str(id))
        if row and row.owner_id!=user.id:raise HTTPException(404,'Bremszettel nicht gefunden.')
        if (row.revision if row else 0)!=data.expected_revision:raise HTTPException(409,'Bremszettel wurde auf einem anderen Gerät geändert. Bitte neu laden.')
        result=calculate(db,data.sheet)
        if not row:
            profile=db.get(TfProfile,user.id)
            if not profile:raise HTTPException(404,'Tf nicht gefunden.')
            row=BrakeSheetDraft(id=str(id),owner_id=user.id,revision=0,created_at=now_utc(),created_by_name=(profile.first_name+' '+profile.last_name).strip());db.add(row)
        row.payload_json=data.sheet.model_dump_json();row.calculation_json=json.dumps(jsonable_encoder(result));row.revision+=1;row.updated_at=now_utc();db.commit()
        return dict(id=row.id,revision=row.revision,sheet=data.sheet.model_dump(),calculation=result,**creation(row))
    return router
