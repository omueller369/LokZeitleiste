"""Private brake-sheet drafts and calculations according to the agreed DE/PL form rules."""
from .localization import source as _text_source, text as _localized_text
from .i18n import request_language
import json,re
from datetime import date
from decimal import Decimal,ROUND_CEILING
from pathlib import Path
from typing import Literal
from uuid import UUID,uuid5
from fastapi import APIRouter,Depends,HTTPException,UploadFile,File,Form
from .wagon_import import WagonImport, ImportError as WagonImportError, parse as parse_wagons, MAX_UPLOAD
from fastapi.responses import FileResponse,Response
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel,Field,field_validator,model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import database_session
from .models import BrakeSheetDraft,RailwayVehicle,VehicleRetirement,TfProfile,User,now_utc
from .tf_portal import driver_dependency
from .signatures import signature_for,signature_position_for
from .vehicles import vehicle_view,is_retired

from .towed_locomotives import TowedLoco,TowError,ERRORS as TOW_ERRORS,plan as tow_plan,compose as tow_compose,sections as tow_sections

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
    wagon_import:WagonImport|None=None
    towed:list[TowedLoco]=Field(default_factory=list,max_length=49)
    final_station:str=Field(default="",max_length=270)
    section_parent:UUID|None=None
    section_index:int=Field(default=0,ge=0,le=49)
    section_superseded:bool=False
    holding_loco:Decimal|None=Field(default=None,ge=0,le=9999,decimal_places=3,allow_inf_nan=False)
    holding_unit:Literal['t','kN']|None=None
    required_percent:int|None=Field(default=None,ge=50,le=150,strict=True)

    @field_validator('train_numbers')
    @classmethod
    def numbers(cls,values):
        if any(v and not re.fullmatch(r'[0-9]{5}',v) for v in values):raise ValueError(_text_source('server_brake_sheets.text_584f0849dc4f'))
        return values
    @field_validator('first_vehicle','last_vehicle','second_first_vehicle','second_last_vehicle')
    @classmethod
    def number(cls,value):
        if value and not re.fullmatch(r'[0-9]{12}',value):raise ValueError(_text_source('server_brake_sheets.text_46262d84dc20'))
        return value
    @model_validator(mode='after')
    def rules(self):
        if self.towed and not self.section_parent:
            self.final_station=self.final_station or self.station_to
            try:self.station_to=tow_plan(self)[0]
            except TowError as error:raise ValueError(_text_source(TOW_ERRORS[str(error)])) from error
        elif not self.towed and not self.section_parent and self.final_station:
            self.station_to=self.final_station;self.final_station=''
            if self.wagon_import:self.first_vehicle=self.wagon_import.rows[0].number;self.last_vehicle=self.wagon_import.rows[-1].number
        self.section_from=self.station_from;self.section_to=self.station_to
        if self.second_from or self.second_to or self.second_first_vehicle or self.second_last_vehicle:raise ValueError(_text_source('server_brake_sheets.text_63cfe4faae33'))
        if len({x.vehicle_id for x in self.locos})!=len(self.locos):raise ValueError(_text_source('server_brake_sheets.text_0bcfde1957a7'))
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
        if not row or is_retired(db,row.id):raise HTTPException(422,_text_source('server_brake_sheets.text_8886bd616bcb'))
        if row.revision!=item.vehicle_revision:raise HTTPException(409,_text_source('server_brake_sheets.text_b2337546555c'))
        v=public_vehicle(row);mode=data.brake_mode
        position='G' if mode in ('G','G+P') else mode if mode in ('P','R') else item.position
        brake=Decimal(v['brake_g_25'] if mode=='G+P' else v['brake_'+position.lower()]) if mode!='LL+P' else item.manual_brake
        lines.append(dict(**v,position=position,brake_weight=brake,note=item.note))
    def total(key,scale=1):
        if not lines or any(v[key] is None for v in lines):return None
        return sum((Decimal(str(v[key])) for v in lines),Decimal(0))/scale
    a=dict(count=len(lines),length=total('length_m'),holding=data.holding_loco,brake=total('brake_weight'),weight=total('weight_kg',1000))
    if a['length'] is not None:a['length']=a['length'].to_integral_value(rounding=ROUND_CEILING)
    b=data.wagon.model_dump()
    towed=[];remarks=data.remarks
    if data.towed or data.section_parent:
        try:
            values,ordered,towed,remarks=tow_compose(db,data,public_vehicle);b.update(values)
            data.first_vehicle=ordered[0]['number'];data.last_vehicle=ordered[-1]['number']
        except TowError as error:raise HTTPException(422,_text_source(TOW_ERRORS[str(error)])) from error
        except WagonImportError as error:raise HTTPException(422,_text_source(IMPORT_ERRORS[str(error)])) from error
    elif data.wagon_import:
        try:b.update(data.wagon_import.values(data.brake_mode))
        except WagonImportError as error:raise HTTPException(422, _text_source(IMPORT_ERRORS[str(error)])) from error
    summed={key:(value+Decimal(b[key] or 0) if value is not None else None) for key,value in a.items()}
    if data.holding_loco is None and b['holding'] is not None:summed['holding']=Decimal(b['holding'])
    if not data.holding_unit:summed['holding']=None
    available=int(summed['brake']*100/summed['weight']) if summed['brake'] is not None and summed['weight'] is not None and summed['weight']>0 else None
    difference=available-data.required_percent if available is not None and data.required_percent is not None else None
    result=dict(lines=lines,a=a,b=b,total=summed,available=available,required=data.required_percent,missing=difference if difference is not None and difference<0 else '/' if difference is not None else None,cast_iron='/')

    result.update(towed=towed,remarks=remarks,station_to=data.station_to,final_station=data.final_station,first_vehicle=data.first_vehicle,last_vehicle=data.last_vehicle)
    if data.wagon_import and not data.towed and not data.section_parent:
        result['wagon_brake_breakdown']=data.wagon_import.brake_components(data.brake_mode)
    result['preview_missing']=preview_missing(data,result)
    if data.section_superseded:result['preview_missing'].append(_text_source(TOW_ERRORS['superseded']))
    return result

def preview_missing(data,result):
    missing=[]
    for key,label in [('issuer',_text_source('server_brake_sheets.text_65dbe918d2bf')),('departure_date',_text_source('server_brake_sheets.text_ecc994a1bd07')),('station_from',_text_source('server_brake_sheets.text_bd2a532a1cc3')),('station_to',_text_source('server_brake_sheets.text_b9aac3d6c30c')),('class_de',_text_source('server_brake_sheets.text_ef73d5882c79')),('class_pl',_text_source('server_brake_sheets.text_e177ffbeb9fa')),('first_vehicle',_text_source('server_brake_sheets.text_ef73da566a06')),('last_vehicle',_text_source('server_brake_sheets.text_ad360e437797')),('required_percent',_text_source('server_brake_sheets.text_a3d2a62766ce'))]:
        value=getattr(data,key)
        if value is None or isinstance(value,str) and not value.strip():missing.append(label)
    if not data.train_numbers[0]:missing.append(_text_source('server_brake_sheets.text_eec21d1fe37f'))
    for i,c in enumerate(data.countries):
        if i<2 or c.country or c.category:
            if not c.country or not c.category:missing.append(_text_source('server_brake_sheets.text_7ddf4cdaa6b4')+str(i+1))
    if not result['lines']:missing.append(_text_source('server_brake_sheets.text_9de2ca1927a7'))
    for i,line in enumerate(result['lines']):
        for key,label in [('series',_text_source('server_brake_sheets.text_7c1c344e8ca2')),('length_m',_text_source('server_brake_sheets.text_8d0eb9bb08e7')),('weight_kg',_text_source('server_brake_sheets.text_a6dc8d473148')),('axle_count',_text_source('server_brake_sheets.text_f69432a09518')),('brake_shoe',_text_source('server_brake_sheets.text_8b8c10d71e16')),('brake_weight',_text_source('server_brake_sheets.text_7417d0f1038a'))]:
            if line[key] is None or line[key]=='':missing.append(_text_source('server_brake_sheets.text_4c3c7e125e1d')+str(i+1)+': '+label)
    for key,label in [('count','19b'),('length','20b'),('brake','22b'),('weight','23b')]:
        if result['b'][key] is None:missing.append(label)
    if (data.holding_loco is not None or data.wagon.holding is not None) and not data.holding_unit:missing.append(_text_source('server_brake_sheets.text_39a0dba1b85a'))
    return missing

IMPORT_ERRORS={'file': 'server_brake_sheets.text_57876c2d52fe', 'format': 'server_brake_sheets.text_fc74c531b994', 'missing_brake': 'server_brake_sheets.text_7c3ce0b4afb2', 'mode': 'server_brake_sheets.text_12846d32442d', 'range': 'server_brake_sheets.text_906e2fc6290d'}

def section_suffix(sheet,revision=None):
    return (f'-A{sheet.section_index+1:02d}'+(f'-R{revision}' if revision is not None else '')) if sheet.towed or sheet.section_parent else ''

def document_source(sheet,row):
    return 'brake-sheet:'+row.id+(':'+str(row.revision) if sheet.towed or sheet.section_parent else '')

class PreviewRequest(BaseModel):
    expected_revision:int=Field(ge=1)

def create_router(require_account):
    router=APIRouter();driver=driver_dependency(require_account);static=Path(__file__).parent/'static'
    @router.get('/tf/brake-sheet.js')
    def script():return FileResponse(static/'brake-sheet.js',media_type='text/javascript',headers={'Cache-Control':'no-cache'})
    @router.get('/tf/brake-sheet.css')
    def style():return FileResponse(static/'brake-sheet.css',media_type='text/css',headers={'Cache-Control':'no-cache'})
    @router.post('/api/v1/tf/brake-sheets/import-wagons')
    async def import_wagons(file:UploadFile=File(...),mode:str=Form('G'),user=Depends(driver)):
        content=await file.read(MAX_UPLOAD+1)
        await file.close()
        if not (file.filename or '').lower().endswith('.xlsx') or len(content)>MAX_UPLOAD:
            raise HTTPException(422,_text_source(IMPORT_ERRORS['file']))
        try:
            imported=await run_in_threadpool(parse_wagons,content)
            source=imported['wagon_import'];selected_mode=mode;notices=[]
            try:values=source.values(mode)
            except WagonImportError as error:
                detected=source.detected_mode()
                if str(error)!='missing_brake' or detected is None or detected==mode:raise
                selected_mode=detected;values=source.values(selected_mode)
                notices.append(_localized_text('server_brake_sheets.text_0ac0b51d459a',request_language.get(),detected=selected_mode,requested=mode))
            for difference in source.summary_differences():
                notice='server_brake_sheets.text_0b22cbff963e' if difference['computed'] is None else 'server_brake_sheets.text_a2d61c07db1c'
                notices.append(_localized_text(notice,request_language.get(),**difference))
        except WagonImportError as error:
            raise HTTPException(422,_text_source(IMPORT_ERRORS[str(error)])) from error
        choices=[]
        if source.detected_mode()=='G+P':
            for policy,choice_mode in [('all_g','G'),('mixed','G+P'),('unchanged','G+P')]:
                choice_source=source.model_copy(update={'brake_policy':policy})
                try:choice_values=choice_source.values(choice_mode)
                except WagonImportError as error:
                    choices.append(dict(policy=policy,error=_text_source(IMPORT_ERRORS[str(error)])))
                    continue
                choices.append(dict(policy=policy,brake_mode=choice_mode,wagon_import=choice_source,
                    wagon=choice_values,breakdown=choice_source.brake_components(choice_mode),
                    column_totals=choice_source.column_totals(choice_mode),
                    rows=[dict(number=row.number,position=choice_source.row_brake(row,index,choice_mode)[0],
                               brake=choice_source.row_brake(row,index,choice_mode)[1]) for index,row in enumerate(source.rows)]))
        return dict(**imported,wagon=values,brake_mode=selected_mode,requested_brake_mode=mode,notices=notices,
                    column_totals=source.column_totals(),choices=choices)
    @router.get('/api/v1/tf/brake-sheets/vehicles')
    def vehicles(user=Depends(driver),db:Session=Depends(database_session)):
        return [public_vehicle(r) for r in db.scalars(select(RailwayVehicle).where(~RailwayVehicle.id.in_(select(VehicleRetirement.vehicle_id))).order_by(RailwayVehicle.vehicle_number))]
    @router.post('/api/v1/tf/brake-sheets/calculate')
    def preview(data:Sheet,user=Depends(driver),db:Session=Depends(database_session)):return calculate(db,data)
    @router.get('/api/v1/tf/brake-sheets')
    def listing(user=Depends(driver),db:Session=Depends(database_session)):
        rows=[]
        for r in db.scalars(select(BrakeSheetDraft).where(BrakeSheetDraft.owner_id==user.id).order_by(BrakeSheetDraft.updated_at.desc())):
            payload=json.loads(r.payload_json)
            if payload.get('section_superseded'):continue
            rows.append(dict(id=r.id,revision=r.revision,updated_at=r.updated_at,train_numbers=payload['train_numbers'],station_from=payload.get('station_from',''),station_to=payload.get('station_to',''),section_parent=payload.get('section_parent'),section_index=payload.get('section_index',0)))
        return rows
    def creation(row):return dict(created_at=row.created_at.isoformat()+'Z',created_by_name=row.created_by_name)
    def owned(db,user,id):
        row=db.scalar(select(BrakeSheetDraft).where(BrakeSheetDraft.id==str(id),BrakeSheetDraft.owner_id==user.id).with_for_update())
        if not row:raise HTTPException(404,_text_source('server_brake_sheets.text_c5d2307ed28b'))
        return row
    def section_links(db,user,row):
        payload=json.loads(row.payload_json);parent=payload.get('section_parent') or row.id;links=[]
        for candidate in db.scalars(select(BrakeSheetDraft).where(BrakeSheetDraft.owner_id==user.id)):
            value=json.loads(candidate.payload_json)
            if not value.get('section_superseded') and (candidate.id==parent or value.get('section_parent')==parent):
                links.append(dict(id=candidate.id,station_from=value.get('station_from',''),station_to=value.get('station_to',''),section_index=value.get('section_index',0)))
        return sorted(links,key=lambda v:v['section_index'])
    def sync_sections(db,user,row,sheet):
        active=set()
        if sheet.towed:
            try:
                _,ordered,_,_=tow_compose(db,sheet,public_vehicle)
                stages=tow_sections(sheet,ordered)
            except TowError as error:raise HTTPException(422,_text_source(TOW_ERRORS[str(error)])) from error
            for stage in stages[1:]:
                stage.section_parent=UUID(row.id)
                child_id=str(uuid5(UUID(row.id),'section:'+str(stage.section_index)+':'+stage.station_from+':'+stage.station_to))
                child=db.get(BrakeSheetDraft,child_id)
                if child and child.owner_id!=user.id:raise HTTPException(409,_text_source(TOW_ERRORS['readonly']))
                calculation=calculate(db,stage)
                if not child:
                    child=BrakeSheetDraft(id=child_id,owner_id=user.id,revision=0,created_at=row.created_at,created_by_name=row.created_by_name);db.add(child)
                from fastapi.encoders import jsonable_encoder
                child.payload_json=stage.model_dump_json();child.calculation_json=json.dumps(jsonable_encoder(calculation));child.revision+=1;child.updated_at=now_utc();active.add(child_id)
        for child in db.scalars(select(BrakeSheetDraft).where(BrakeSheetDraft.owner_id==user.id)):
            value=json.loads(child.payload_json)
            if value.get('section_parent')==row.id and child.id not in active and not value.get('section_superseded'):
                value['section_superseded']=True;child.payload_json=json.dumps(value);child.revision+=1;child.updated_at=now_utc()
    @router.get('/api/v1/tf/brake-sheets/{id}')
    def detail(id:UUID,user=Depends(driver),db:Session=Depends(database_session)):
        row=owned(db,user,id)
        return dict(id=row.id,revision=row.revision,sheet=json.loads(row.payload_json),calculation=json.loads(row.calculation_json),sections=section_links(db,user,row),**creation(row))
    @router.post('/api/v1/tf/brake-sheets/{id}/preview')
    def image_preview(id:UUID,data:PreviewRequest,user=Depends(driver),db:Session=Depends(database_session)):
        row=owned(db,user,id)
        if row.revision!=data.expected_revision:raise HTTPException(409,_text_source('server_brake_sheets.text_5a7be4591f8a'))
        sheet=Sheet.model_validate_json(row.payload_json);result=calculate(db,sheet)
        if result['preview_missing']:raise HTTPException(422,_text_source('server_brake_sheets.text_22306b124a93')+', '.join(result['preview_missing']))
        from .brake_sheet_image import render
        try:content=render(sheet,result,row.created_at,row.created_by_name,signature=signature_for(db,user),signature_position=signature_position_for(db,user))
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        return Response(content,media_type='image/png',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Content-Disposition':'inline; filename="bremszettel-vorschau.png"'})
    @router.post('/api/v1/tf/brake-sheets/{id}/archive')
    def archive(id:UUID,data:PreviewRequest,user=Depends(driver),db:Session=Depends(database_session)):
        row=owned(db,user,id)
        if row.revision!=data.expected_revision:raise HTTPException(409,_text_source('server_brake_sheets.text_5a7be4591f8a'))
        sheet=Sheet.model_validate_json(row.payload_json);result=calculate(db,sheet)
        if result['preview_missing']:raise HTTPException(422,_text_source('server_brake_sheets.text_22306b124a93')+', '.join(result['preview_missing']))
        from .brake_sheet_image import render_pdf
        from .documents.storage import generated
        from urllib.parse import quote
        try:content=render_pdf(sheet,result,row.created_at,row.created_by_name,signature=signature_for(db,user),signature_position=signature_position_for(db,user))
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        number=sheet.train_numbers[0];day=sheet.departure_date
        filename=f"{_text_source('server_brake_sheets.text_b1cc93fb59b2')}{number}-{day.isoformat()}{section_suffix(sheet,row.revision)}.PDF"
        document=generated(db,user,f'Dokumente/Zugfahrten/{day:%Y/%m/%d}/{number}/{filename}',content,document_source(sheet,row))
        db.commit()
        return dict(filename=document.display_name,document_path=document.relative_path,download_url='/api/v1/documents/download?path='+quote(document.relative_path,safe=''))
    @router.put('/api/v1/tf/brake-sheets/{id}')
    def save(id:UUID,data:Save,user=Depends(driver),db:Session=Depends(database_session)):
        from fastapi.encoders import jsonable_encoder
        db.scalar(select(User).where(User.id==user.id).with_for_update())
        row=db.get(BrakeSheetDraft,str(id))
        if row and row.owner_id!=user.id:raise HTTPException(404,_text_source('server_brake_sheets.text_c5d2307ed28b'))
        if (row.revision if row else 0)!=data.expected_revision:raise HTTPException(409,_text_source('server_brake_sheets.text_5a7be4591f8a'))
        if data.sheet.section_parent or row and json.loads(row.payload_json).get('section_parent'):raise HTTPException(409,_text_source(TOW_ERRORS['readonly']))
        data.sheet.section_index=0;data.sheet.section_superseded=False
        result=calculate(db,data.sheet)
        if not row:
            profile=db.get(TfProfile,user.id)
            if not profile:raise HTTPException(404,_text_source('server_brake_sheets.text_90407b4e449b'))
            row=BrakeSheetDraft(id=str(id),owner_id=user.id,revision=0,created_at=now_utc(),created_by_name=(profile.first_name+' '+profile.last_name).strip());db.add(row)
        row.payload_json=data.sheet.model_dump_json();row.calculation_json=json.dumps(jsonable_encoder(result));row.revision+=1;row.updated_at=now_utc();db.flush();sync_sections(db,user,row,data.sheet);db.commit()
        return dict(id=row.id,revision=row.revision,sheet=data.sheet.model_dump(),calculation=result,sections=section_links(db,user,row),**creation(row))
    return router
