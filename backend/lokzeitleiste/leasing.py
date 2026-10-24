"""Leasing company master data and vehicle assignments, without altering legacy columns."""
import json
from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel,Field,EmailStr,TypeAdapter,field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .db import database_session
from .models import LeasingCompany,VehicleLeasing,RailwayVehicle

COUNTRIES=json.loads((Path(__file__).parent/'accounts/countries.json').read_text())
class CompanyInput(BaseModel):
    company:str=Field(min_length=1,max_length=200)
    contact:str=Field(default='',max_length=200)
    street:str=Field(default='',max_length=255)
    postal_code:str=Field(default='',max_length=7)
    city:str=Field(default='',max_length=200)
    country:str='DE'
    email:str=Field(default='',max_length=254)
    phone:str=Field(default='',max_length=60)
    mobile:str=Field(default='',max_length=60)
    hotline:str=Field(default='',max_length=60)
    notes:str=Field(default='',max_length=1000)
    @field_validator('*',mode='before')
    @classmethod
    def trim(cls,value):return value.strip() if isinstance(value,str) else value
    @field_validator('country')
    @classmethod
    def country_code(cls,value):
        if value not in COUNTRIES:raise ValueError('Bitte ein gültiges Land auswählen.')
        return value
    @field_validator('email')
    @classmethod
    def email_format(cls,value):return str(TypeAdapter(EmailStr).validate_python(value)) if value else ''
class CompanyUpdate(CompanyInput):
    expected_revision:int=Field(ge=1)
def view(row):return dict(id=row.id,revision=row.revision,**{key:getattr(row,key) for key in CompanyInput.model_fields})
def seed_and_migrate(db):
    companies={row.company.casefold():row for row in db.scalars(select(LeasingCompany))}
    seeded=db.scalar(select(LeasingCompany).where(LeasingCompany.seed_key=='railpool-demo'))
    if seeded is None and 'railpool' in companies:
        companies['railpool'].seed_key='railpool-demo'
    if seeded is None and 'railpool' not in companies:
        row=LeasingCompany(**CompanyInput(company='Railpool',contact='Hans Zimmer',street='Teststr. 123A',postal_code='12345',city='Musterort',email='railpool@ctl-software.io-goerlitz.eu',phone='0123-1234567',mobile='+49-171-1234567',hotline='0800-1234567',notes='Testdatensatz').model_dump(),revision=1,seed_key='railpool-demo')
        db.add(row);db.flush();companies['railpool']=row
    for vehicle in db.scalars(select(RailwayVehicle)):
        name=vehicle.lessor.strip()
        if not name or db.get(VehicleLeasing,vehicle.id):continue
        row=companies.get(name.casefold())
        if row is None:
            row=LeasingCompany(**CompanyInput(company=name,hotline=vehicle.hotline).model_dump(),revision=1);db.add(row);db.flush();companies[name.casefold()]=row
        db.add(VehicleLeasing(vehicle_id=vehicle.id,company_id=row.id))
def assigned_company(db,vehicle_id):
    link=db.get(VehicleLeasing,vehicle_id)
    return db.get(LeasingCompany,link.company_id) if link else None

def create_router(require_admin):
    router=APIRouter()
    @router.get('/admin/leasing')
    def page():return FileResponse(Path(__file__).parent/'static/leasing.html')
    @router.get('/admin/leasing.js')
    def script():return FileResponse(Path(__file__).parent/'static/leasing.js',media_type='text/javascript',headers={'Cache-Control':'no-cache'})
    @router.get('/api/v1/admin/leasing/countries',dependencies=[Depends(require_admin)])
    def countries():return COUNTRIES
    @router.get('/api/v1/admin/leasing',dependencies=[Depends(require_admin)])
    def listing(db:Session=Depends(database_session)):return [view(row) for row in db.scalars(select(LeasingCompany).order_by(LeasingCompany.company,LeasingCompany.id))]
    def save(db,row):
        try:db.commit()
        except IntegrityError as exc:
            db.rollback();raise HTTPException(409,'Diese Lok-Leasing-Firma ist bereits vorhanden.') from exc
        return view(row)
    @router.post('/api/v1/admin/leasing',status_code=201,dependencies=[Depends(require_admin)])
    def create(data:CompanyInput,db:Session=Depends(database_session)):
        row=LeasingCompany(**data.model_dump(),revision=1);db.add(row);return save(db,row)
    @router.put('/api/v1/admin/leasing/{company_id}',dependencies=[Depends(require_admin)])
    def update(company_id:int,data:CompanyUpdate,db:Session=Depends(database_session)):
        row=db.scalar(select(LeasingCompany).where(LeasingCompany.id==company_id).with_for_update())
        if not row:raise HTTPException(404,'Lok-Leasing-Firma nicht gefunden.')
        if row.revision!=data.expected_revision:raise HTTPException(409,'Datensatz wurde geändert. Bitte neu laden.')
        for key,value in data.model_dump(exclude={'expected_revision'}).items():setattr(row,key,value)
        row.revision+=1;return save(db,row)
    return router
