"""Ordered non-working locomotives and explicit drop-off sections for brake sheets."""
from collections import defaultdict
from decimal import Decimal, ROUND_CEILING
import re, unicodedata
from pydantic import BaseModel, Field
from typing import Literal
from .models import RailwayVehicle
from .vehicles import is_retired
from .localization import source, text
from .i18n import request_language

ERRORS = {'source': 'server_brake_sheets.text_125e0f35734b', 'positions': 'server_brake_sheets.text_83270cdf3d72', 'route': 'server_brake_sheets.text_71faf3e94a85', 'duplicate': 'server_brake_sheets.text_be76a8d9bb14', 'brakes': 'server_brake_sheets.text_2c84682009d9', 'dimensions': 'server_brake_sheets.text_cb9bac8ec7cc', 'readonly': 'server_brake_sheets.text_47d309426a1c', 'superseded': 'server_brake_sheets.text_62ef2abc71ed', 'revision': 'server_brake_sheets.text_b2337546555c', 'notice_limit': 'server_brake_sheets.text_08720ebebab9', 'notice': 'server_brake_sheets.text_2f1639602f6f'}

class TowError(ValueError):
    pass

class TowedLoco(BaseModel):
    vehicle_id: int = Field(gt=0)
    vehicle_revision: int = Field(ge=1)
    position: int = Field(ge=1,le=50,strict=True)
    brake_position: Literal['G','P','R']
    brake_weight: Decimal | None = Field(default=None,ge=0,le=1000,decimal_places=3,allow_inf_nan=False)
    count_g: bool | None = None
    destination: str = Field(min_length=1,max_length=270)
    stop_order: int = Field(default=1,ge=1,le=50,strict=True)
    length: Decimal | None = Field(default=None,gt=0,le=100,decimal_places=3,allow_inf_nan=False)
    weight: Decimal | None = Field(default=None,gt=0,le=1000,decimal_places=3,allow_inf_nan=False)


def station_key(value):
    name=value.split(' · ')[-1].strip()
    return ' '.join(unicodedata.normalize('NFKC',name).casefold().split())


def plan(data):
    final=data.final_station or data.station_to
    if not station_key(final): raise TowError('route')
    stops={};orders={}
    for item in data.towed:
        key=station_key(item.destination)
        if not key or key==station_key(data.station_from): raise TowError('route')
        if key==station_key(final):continue
        if key in stops and stops[key][0]!=item.stop_order:raise TowError('route')
        if item.stop_order in orders and orders[item.stop_order]!=key:raise TowError('route')
        stops[key]=(item.stop_order,item.destination.strip());orders[item.stop_order]=key
    return [v[1] for v in sorted(stops.values())]+[final]


def compose(db,data,public_vehicle):
    if not data.wagon_import:raise TowError('source')
    if data.brake_mode not in ('G','P','G+P'):raise TowError('source')
    imported=data.wagon_import
    if data.brake_mode in ('G','P'):imported.values(data.brake_mode)
    count=len(imported.rows)+len(data.towed)
    if count>50 or len({t.position for t in data.towed})!=len(data.towed) or any(t.position>count for t in data.towed):raise TowError('positions')
    if len({t.vehicle_id for t in data.towed})!=len(data.towed) or {t.vehicle_id for t in data.towed}&{t.vehicle_id for t in data.locos}:raise TowError('duplicate')
    by_position={};numbers={r.number for r in imported.rows}
    for item in data.towed:
        row=db.get(RailwayVehicle,item.vehicle_id)
        if not row or is_retired(db,row.id):raise TowError('dimensions')
        if row.revision!=item.vehicle_revision:raise TowError('revision')
        v=public_vehicle(row);number=re.sub(r'\D','',v['vehicle_number'])
        if len(number)!=12 or number in numbers:raise TowError('duplicate')
        numbers.add(number)
        length=item.length if item.length is not None else v['length_m']
        weight=item.weight if item.weight is not None else Decimal(v['weight_kg'])/1000 if v['weight_kg'] is not None else None
        if length is None or weight is None or Decimal(str(length))<=0 or Decimal(str(weight))<=0:raise TowError('dimensions')
        if item.brake_position=='G' and item.count_g is None:raise TowError('brakes')
        counted=not(item.brake_position=='G' and item.count_g is False)
        if counted and item.brake_weight is None:raise TowError('brakes')
        by_position[item.position]=dict(number=number,length=Decimal(str(length)),weight=Decimal(str(weight)),tow=item,brake=item.brake_weight if counted else Decimal(0))
    ordinary=iter(imported.rows);ordered=[]
    for position in range(1,count+1):
        if position in by_position:entry=by_position[position]
        else:
            row=next(ordinary);entry=dict(number=row.number,length=row.length,weight=row.weight,wagon=row)
        ordered.append(dict(entry,position=position))
    raw_length=sum((x['length'] for x in ordered),Decimal(0));raw_weight=sum((x['weight'] for x in ordered),Decimal(0))
    for given,measured in [(imported.length_total,sum((r.length for r in imported.rows),Decimal(0))),(imported.weight_total,sum((r.weight for r in imported.rows),Decimal(0)))]:
        if given is not None and given.to_integral_value(rounding=ROUND_CEILING)!=measured.to_integral_value(rounding=ROUND_CEILING):raise TowError('dimensions')
    total=Decimal(0);tows=[]
    for index,entry in enumerate(ordered):
        tow=entry.get('tow')
        if tow:mode,brake=tow.brake_position,entry['brake']
        else:mode,brake=imported.row_brake(entry['wagon'],index,data.brake_mode)
        if brake is None:raise TowError('brakes')
        policy=imported.active_policy(data.brake_mode)
        factor=Decimal('.75') if data.brake_mode=='G+P' and mode=='G' and policy!='unchanged' else Decimal('.95') if data.brake_mode=='G+P' and mode=='P' and raw_length>500 and policy!='unchanged' else Decimal(1)
        total+=brake*factor
        if tow:tows.append(dict(vehicle_id=tow.vehicle_id,number=entry['number'],position=index+1,brake_position=mode,brake_weight=brake*factor,destination=tow.destination))
    ceil=lambda v:int(v.to_integral_value(rounding=ROUND_CEILING))
    b=dict(count=count,length=ceil(raw_length),weight=ceil(raw_weight),brake=ceil(total))
    if not(10<=b['length']<=720 and 100<=b['weight']<=5000 and 100<=b['brake']<=5000):raise TowError('dimensions')
    groups=defaultdict(list);names={}
    for item in tows:
        key=station_key(item['destination'])
        if key!=station_key(data.final_station or data.station_to):groups[key].append(item['number']);names[key]=item['destination']
    notes=[text(ERRORS['notice'],request_language.get(),numbers=', '.join(groups[key]),station=names[key]) for key in sorted(groups)]
    remarks='\n'.join([part for part in [data.remarks.strip(),*notes] if part])
    if len(remarks)>500:raise TowError('notice_limit')
    return b,ordered,tows,remarks


def sections(data,ordered):
    """Keep original wagons; remove only locomotives reaching each ordered stop."""
    start=data.station_from;remaining=ordered;result=[]
    for index,end in enumerate(plan(data)):
        towed=[]
        for position,entry in enumerate(remaining,1):
            if entry.get('tow'):towed.append(entry['tow'].model_copy(update={'position':position}))
        stage=data.model_copy(deep=True,update={'station_from':start,'station_to':end,'section_from':start,'section_to':end,'towed':towed,'section_index':index,'section_superseded':False})
        stage.first_vehicle=remaining[0]['number'];stage.last_vehicle=remaining[-1]['number'];result.append(stage)
        remaining=[entry for entry in remaining if not(entry.get('tow') and station_key(entry['tow'].destination)==station_key(end))]
        start=end
    return result
