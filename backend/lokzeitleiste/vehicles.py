"""Administrative railway vehicles; status codes/colors are reusable by future TF views."""
import re
from datetime import date
from pathlib import Path
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Query
from fastapi.responses import FileResponse
from pydantic import BaseModel,Field,field_validator,model_validator
from sqlalchemy import select,or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session,object_session
from .db import database_session
from .models import RailwayVehicle,VehicleRetirement,VehicleLeasing,LeasingCompany,now_utc
from .leasing import assigned_company,view as company_view

VEHICLE_STATUSES={
    'ready':('Einsatzbereit','#d9f2df'),
    'unavailable':('Nicht einsatzbereit','#ffdada'),
    'limited':('Eingeschränkt einsatzbereit','#fff0b3'),
}

class VehicleInput(BaseModel):
    vehicle_number:str
    status:Literal['ready','unavailable','limited']='ready'
    status_note:str=Field(default='',max_length=1024)
    series:str=Field(default='',max_length=120)
    leasing_company_id:int|None=Field(default=None,ge=1)
    lessor:str=Field(default='',max_length=200)
    hotline:str=Field(default='',max_length=60)
    name:str=Field(default='',max_length=120)
    brake_r:int=Field(default=0,ge=0,le=999,strict=True)
    brake_p:int=Field(default=0,ge=0,le=999,strict=True)
    brake_g:int=Field(default=0,ge=0,le=999,strict=True)
    spring_brake:int=Field(default=0,ge=0,le=999,strict=True)
    spring_unit:Literal['t','kN']='t'
    next_revision:date|None=None
    mileage:int=Field(default=0,ge=0,le=9999999,strict=True)
    notes:str=Field(default='',max_length=4096)

    @field_validator('vehicle_number')
    @classmethod
    def number(cls,value):
        number=re.sub(r'[\s-]','',value)
        if not re.fullmatch(r'[0-9]{12}',number):raise ValueError('Fahrzeugnummer muss 12 Ziffern im Format 00 00 0000 000-0 enthalten.')
        return f'{number[:2]} {number[2:4]} {number[4:8]} {number[8:11]}-{number[11]}'

    @model_validator(mode='after')
    def operational_status(self):
        self.status_note=self.status_note.strip()
        if self.status!='ready' and not self.status_note:raise ValueError('Grund oder Einschränkung ist erforderlich.')
        if self.status=='ready':self.status_note=''
        return self

class RetirementInput(BaseModel):
    retired:bool
    expected_revision:int=Field(ge=1)


class VehicleUpdate(VehicleInput):
    expected_revision:int=Field(ge=1)


def is_retired(db,vehicle_id):
    return db.get(VehicleRetirement,vehicle_id) is not None


def vehicle_view(row):
    values={field:getattr(row,field) for field in VehicleInput.model_fields if field!='leasing_company_id'}
    db=object_session(row);company=assigned_company(db,row.id) if db else None
    values['retired']=is_retired(db,row.id) if db else False
    values.update(leasing_company_id=company.id if company else None,leasing_company=company_view(company) if company else None)
    if company:values.update(lessor=company.company,hotline=company.hotline,leasing_email=company.email)
    values['next_revision']=row.next_revision.isoformat() if row.next_revision else None
    label,color=VEHICLE_STATUSES[row.status]
    return dict(values,id=row.id,revision=row.revision,updated_at=row.updated_at.isoformat(),
                brake_g_25=row.brake_g*75//100,status_label=label,status_color=color)


def find_vehicles(db,q="",status=None,include_retired=True):
    query=select(RailwayVehicle)
    if not include_retired:query=query.where(~RailwayVehicle.id.in_(select(VehicleRetirement.vehicle_id)))
    if q.strip():
        text=q.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        query=query.where(or_(*[field.ilike('%'+text+'%',escape='\\') for field in [RailwayVehicle.vehicle_number,RailwayVehicle.name,RailwayVehicle.series,RailwayVehicle.lessor]], RailwayVehicle.id.in_(select(VehicleLeasing.vehicle_id).join(LeasingCompany,VehicleLeasing.company_id==LeasingCompany.id).where(LeasingCompany.company.ilike('%'+text+'%',escape='\\')))))
    if status:query=query.where(RailwayVehicle.status==status)
    return db.scalars(query.order_by(RailwayVehicle.vehicle_number)).all()


def create_router(require_admin):
    router=APIRouter()
    @router.get('/admin/vehicles')
    def page():return FileResponse(Path(__file__).parent/'static'/'vehicles.html')
    @router.get('/admin/vehicles.js')
    def script():return FileResponse(Path(__file__).parent/'static'/'vehicles.js',media_type='text/javascript',headers={'Cache-Control':'no-cache'})

    @router.get('/api/v1/admin/vehicles',dependencies=[Depends(require_admin)])
    def listing(q:str=Query(default='',max_length=200),status:Literal['ready','unavailable','limited']|None=None,db:Session=Depends(database_session)):
        return [vehicle_view(row) for row in find_vehicles(db,q,status)]

    @router.get('/api/v1/admin/vehicles/{vehicle_id}',dependencies=[Depends(require_admin)])
    def details(vehicle_id:int,db:Session=Depends(database_session)):
        row=db.get(RailwayVehicle,vehicle_id)
        if not row:raise HTTPException(404,'Triebfahrzeug nicht gefunden.')
        return vehicle_view(row)

    def assign(db,row,company_id):
        company=db.get(LeasingCompany,company_id) if company_id else None
        if company_id and not company:raise HTTPException(422,'Lok-Leasing-Firma nicht gefunden.')
        try:db.flush()
        except IntegrityError as exc:
            db.rollback();raise HTTPException(409,'Fahrzeugnummer ist bereits vorhanden.') from exc
        link=db.get(VehicleLeasing,row.id)
        if company:
            if link:link.company_id=company.id
            else:db.add(VehicleLeasing(vehicle_id=row.id,company_id=company.id))
            row.lessor=company.company;row.hotline=company.hotline
        elif link:
            db.delete(link);row.lessor='';row.hotline=''

    def commit(db,row):
        try:db.commit()
        except IntegrityError as exc:
            db.rollback();raise HTTPException(409,'Fahrzeugnummer ist bereits vorhanden.') from exc
        return vehicle_view(row)

    @router.post('/api/v1/admin/vehicles',status_code=201,dependencies=[Depends(require_admin)])
    def create(data:VehicleInput,db:Session=Depends(database_session)):
        row=RailwayVehicle(**data.model_dump(exclude={'leasing_company_id'}),revision=1,updated_at=now_utc());db.add(row)
        assign(db,row,data.leasing_company_id)
        return commit(db,row)

    @router.put('/api/v1/admin/vehicles/{vehicle_id}',dependencies=[Depends(require_admin)])
    def update(vehicle_id:int,data:VehicleUpdate,db:Session=Depends(database_session)):
        row=db.scalar(select(RailwayVehicle).where(RailwayVehicle.id==vehicle_id).with_for_update())
        if not row:raise HTTPException(404,'Triebfahrzeug nicht gefunden.')
        if row.revision!=data.expected_revision:raise HTTPException(409,'Triebfahrzeug wurde geändert. Bitte neu laden.')
        for field,value in data.model_dump(exclude={'expected_revision','leasing_company_id'}).items():setattr(row,field,value)
        if 'leasing_company_id' in data.model_fields_set:assign(db,row,data.leasing_company_id)
        row.revision+=1;row.updated_at=now_utc();return commit(db,row)
    @router.put('/api/v1/admin/vehicles/{vehicle_id}/retirement',dependencies=[Depends(require_admin)])
    def retirement(vehicle_id:int,data:RetirementInput,db:Session=Depends(database_session)):
        row=db.scalar(select(RailwayVehicle).where(RailwayVehicle.id==vehicle_id).with_for_update())
        if not row:raise HTTPException(404,'Triebfahrzeug nicht gefunden.')
        if row.revision!=data.expected_revision:raise HTTPException(409,'Triebfahrzeug wurde geändert. Bitte neu laden.')
        retired=db.get(VehicleRetirement,vehicle_id)
        if data.retired and not retired:db.add(VehicleRetirement(vehicle_id=vehicle_id))
        elif not data.retired and retired:db.delete(retired)
        row.revision+=1;row.updated_at=now_utc()
        return commit(db,row)
    return router
