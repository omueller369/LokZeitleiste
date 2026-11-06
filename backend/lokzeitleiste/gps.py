"""Private browser-test GPS recordings and cached place-name/DS100 suggestions."""
from .localization import source as _text_source
import json,math,time,threading,urllib.request,urllib.parse,re,unicodedata
from datetime import timedelta
from pathlib import Path
from uuid import UUID
from typing import Annotated
from fastapi import APIRouter,Depends,HTTPException,Query
from fastapi.responses import FileResponse
from pydantic import BaseModel,Field,model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .db import database_session
from .models import User,RailwayStation,TrainGpsRecording,GpsStationCache,now_utc
from .tf_portal import driver_dependency
from .gps_analysis import analyse,distance

_finite=Annotated[float,Field(allow_inf_nan=False)]
class Point(BaseModel):
    t:int=Field(ge=946684800000,le=4133980800000)
    lat:_finite=Field(ge=-90,le=90)
    lon:_finite=Field(ge=-180,le=180)
    accuracy:_finite=Field(ge=0,le=100000)
    speed:_finite|None=Field(default=None,ge=0,le=200)
class StopEdit(BaseModel):
    station_input:str=Field(default='',max_length=270)
    station:dict[str,str]|None=None
    reason:str=Field(default='',max_length=64)
    detail:str=Field(default='',max_length=256)
    end:int|None=Field(default=None,ge=946684800000,le=4133980800000)
    manual_end:bool=False
    imported:bool=False
    deleted:bool=False

class ManualStop(BaseModel):
    key:str=Field(pattern=r'^manual-[0-9]{12,16}$',max_length=64)
    start:int=Field(ge=946684800000,le=4133980800000)
    end:int|None=Field(default=None,ge=946684800000,le=4133980800000)
    @model_validator(mode='after')
    def ordered(self):
        if self.end is not None and self.end<=self.start:raise ValueError(_text_source('server_gps.text_6d8354985870'))
        if self.key!='manual-'+str(self.start):raise ValueError(_text_source('server_gps.text_caf70142ca12'))
        return self

class Recording(BaseModel):
    train_number:str=Field(pattern=r'^[A-Za-z0-9]{1,12}$')
    points:list[Point]=Field(default_factory=list,max_length=20000)
    start_station:str|None=Field(default=None,max_length=10)
    end_station:str|None=Field(default=None,max_length=10)
    start_station_name:str=Field(default='',max_length=255)
    end_station_name:str=Field(default='',max_length=255)
    manual_stops:list[ManualStop]|None=Field(default=None,max_length=500)
    stop_edits:dict[str,StopEdit]|None=Field(default=None,max_length=1024)
    departure_applied:bool=False
    arrival_at:int|None=Field(default=None,ge=946684800000,le=4133980800000)
    ended:bool=True
    expected_revision:int=Field(default=0,ge=0)
    @model_validator(mode='after')
    def ordered(self):
        if any(b.t<=a.t for a,b in zip(self.points,self.points[1:])):raise ValueError(_text_source('server_gps.text_094ba7dcb28a'))
        if not self.points and not self.manual_stops:raise ValueError(_text_source('server_gps.text_da0bf51ad2de'))
        if self.manual_stops:
            if len({r.key for r in self.manual_stops})!=len(self.manual_stops):raise ValueError(_text_source('server_gps.text_f899e27a7248'))
            if sum(r.end is None for r in self.manual_stops)>1:raise ValueError(_text_source('server_gps.text_927e3ef652cc'))
            ordered=sorted(self.manual_stops,key=lambda r:r.start)
            if any(a.end is None or a.end>b.start for a,b in zip(ordered,ordered[1:])):raise ValueError(_text_source('server_gps.text_07743b7daef0'))
        if self.points and self.points[-1].t-self.points[0].t>48*3600_000:raise ValueError(_text_source('server_gps.text_7098ded12868'))
        return self
class StopReason(BaseModel):
    reason:str=Field(default='',max_length=64)
    detail:str=Field(default='',max_length=256)
    @model_validator(mode='after')
    def valid_detail(self):
        self.detail=self.detail.strip() if self.reason==_text_source('server_gps.text_69384a6be550') else ''
        if self.reason==_text_source('server_gps.text_69384a6be550') and not self.detail:raise ValueError(_text_source('server_gps.text_58f91be54d8a'))
        return self

class FreePlace(BaseModel):
    name:str=Field(min_length=1,max_length=255)

class Choices(BaseModel):
    expected_revision:int=Field(ge=1)
    stations:dict[str,str|FreePlace]=Field(default_factory=dict,max_length=1024)
    reasons:dict[str,StopReason]|None=Field(default=None,max_length=1024)
    selection:list[str]|None=Field(default=None,max_length=1024)

_lock=threading.Lock();_last_query=0

def osm_query(lat,lon,radius=3500):
    global _last_query
    # One small vicinity query per explicit request; cached for 30 days.
    if not _lock.acquire(blocking=False):raise HTTPException(429,_text_source('server_gps.text_9ba3a6373f57'))
    try:
        if time.monotonic()-_last_query<2:raise HTTPException(429,_text_source('server_gps.text_348b25b6d7f6'))
        _last_query=time.monotonic()
        query=f"[out:json][timeout:12];nwr(around:{radius},{lat:.5f},{lon:.5f}{_text_source('server_gps.text_90f858e75790')}"
        request=urllib.request.Request('https://overpass-api.de/api/interpreter',data=urllib.parse.urlencode({'data':query}).encode(),headers={'User-Agent':'LokZeitleiste-GPS-Browsertest/1.0 (+https://github.com/omueller369/LokZeitleiste)','Content-Type':'application/x-www-form-urlencoded'})
        try:
            with urllib.request.urlopen(request,timeout=18) as response:
                raw=response.read(2*1024*1024+1)
            if len(raw)>2*1024*1024:raise ValueError(_text_source('server_gps.text_146835ea0bc8'))
            data=json.loads(raw)
            if data.get('remark'):raise ValueError(_text_source('server_gps.text_3299be54a680'))
            return data.get('elements',[])
        except Exception as exc:raise HTTPException(503,_text_source('server_gps.text_c3d8d43508a9')) from exc
    finally:_lock.release()

def place_key(lat,lon):
    return f'place:{round(lat,2):.2f},{round(lon,2):.2f}'

def normalized_name(value):
    return ' '.join(re.sub(r'[^\w]+',' ',unicodedata.normalize('NFKC',value).casefold()).split())

def station_data(db,lat,lon,nearby=False):
    """Find the nearest named place within 5 km, then match its name in DS100.

    Separate cache namespace deliberately leaves previous railway cache entries intact.
    No railway reference or distance to a railway site is used for suggestions.
    """
    cell=place_key(lat,lon);cached=db.get(GpsStationCache,cell)
    if cached and cached.updated_at>now_utc()-timedelta(days=30):elements=json.loads(cached.payload_json)
    else:
        # 6.5 km around rounded cell fully covers each caller's 5 km circle.
        elements=osm_query(round(lat,2),round(lon,2),6500)
        if not cached:cached=GpsStationCache(cell=cell);db.add(cached)
        cached.payload_json=json.dumps(elements,ensure_ascii=False);cached.updated_at=now_utc()
        try:db.commit()
        except IntegrityError:
            db.rollback();cached=db.get(GpsStationCache,cell)
            if not cached:raise
            elements=json.loads(cached.payload_json)
    places=[]
    for item in elements:
        tags=item.get('tags',{});name=tags.get('name','').strip()
        if tags.get('place') not in {'city','town','village','hamlet','suburb','quarter','neighbourhood','locality','isolated_dwelling'} or not name:continue
        point=item if 'lat' in item else item.get('center',{})
        if any(not isinstance(point.get(k),(int,float)) or not math.isfinite(point[k]) for k in ('lat','lon')):continue
        if not -90<=point['lat']<=90 or not -180<=point['lon']<=180:continue
        meters=distance(dict(lat=lat,lon=lon),point)
        if meters<=5000:places.append(dict(name=name,lat=point['lat'],lon=point['lon'],distance_m=meters))
    if not places:return []
    place=min(places,key=lambda p:(p['distance_m'],p['name']));key=normalized_name(place['name'])
    if not key:return []
    stations=[]
    for station in db.scalars(select(RailwayStation).order_by(RailwayStation.name,RailwayStation.code)):
        name=normalized_name(station.name)
        # Exact place name or a station qualifier, e.g. Berlin Hauptbahnhof.
        if name==key or name.startswith(key+' '):
            stations.append(dict(code=station.code,name=station.name,lat=place['lat'],lon=place['lon'],place_name=place['name']))
    return stations

def create_router(require_account):
    router=APIRouter();driver=driver_dependency(require_account)
    def owned(db,user,journey_id,lock=False):
        if lock:db.scalar(select(User).where(User.id==user.id).with_for_update())
        query=select(TrainGpsRecording).where(TrainGpsRecording.owner_id==user.id,TrainGpsRecording.journey_id==str(journey_id))
        row=db.scalar(query.with_for_update() if lock else query)
        if not row:raise HTTPException(404,_text_source('server_gps.text_d425fe5589f1'))
        return row
    def read_payload(row):
        payload=json.loads(row.payload_json)
        if payload.get('detection_version')==5:return payload
        # Resolve old numbered assignments by their original start time.
        old=[r for r in analyse(payload['points'],payload.get('stop_edits') or {},legacy=payload.get('detection_version') not in (2,3,4),version2=payload.get('detection_version')==2,version3=payload.get('detection_version')==3,version4=payload.get('detection_version')==4)['rows'] if r['kind']==_text_source('server_gps.text_0fd998791d67')]
        edits=payload.get('stop_edits') or {}
        for item in old:
            station=payload.get('stations',{}).get(item['key']) or payload.get('locations',{}).get(str(item['start']))
            reason=payload.get('reasons',{}).get(item['key'],{})
            key='live-'+str(item['start'])
            if key not in edits and (station or reason):
                edits[key]=dict(station=station,station_input=((station.get('code','')+' · ' if station.get('code') else '')+station.get('name','')) if station else '',reason=reason.get('reason',''),detail=reason.get('detail',''),end=None,manual_end=False,imported=False)
        payload['stop_edits']=edits
        new=[r for r in analyse(payload['points'])['rows'] if r['kind']==_text_source('server_gps.text_0fd998791d67')]
        key_map={}
        for item in old:
            match=next((r for r in new if r['start']<=item['start']<=r['end']),None)
            if match:key_map[item['key']]=match['key']
        key_map.update(start='start',end='end')
        for field in ('stations','reasons'):
            values={}
            for key,value in payload.get(field,{}).items():
                if key in key_map:values.setdefault(key_map[key],value)
            payload[field]=values
        payload['selection']=list(dict.fromkeys(key_map[k] for k in payload.get('selection',[]) if k in key_map))
        payload['detection_version']=5
        return payload
    def view(row):
        payload=read_payload(row);result=analyse(payload['points'],payload.get('stop_edits') or {})
        payload.setdefault('reasons',{})
        for item in result['rows']:
            item['station']=payload.get('stations',{}).get(item['key'])
            item['reason']=payload['reasons'].get(item['key'],{})
        return dict(payload,revision=row.revision,analysis=result)
    @router.get('/tf/gps.js')
    def script():return FileResponse(Path(__file__).parent/'static'/'gps.js',media_type='text/javascript',headers={'Cache-Control':'no-cache'})
    @router.get('/api/v1/tf/gps/nearby')
    def nearby(lat:float=Query(ge=-90,le=90,allow_inf_nan=False),lon:float=Query(ge=-180,le=180,allow_inf_nan=False),user:User=Depends(driver),db:Session=Depends(database_session)):
        stations=station_data(db,lat,lon,nearby=True)
        result=[dict(r,distance_m=round(distance(dict(lat=lat,lon=lon),r))) for r in stations if distance(dict(lat=lat,lon=lon),r)<=5000]
        return dict(radius_m=5000,stations=sorted(result,key=lambda r:r['distance_m']))
    @router.get('/api/v1/tf/gps/{journey_id}')
    def get(journey_id:UUID,user:User=Depends(driver),db:Session=Depends(database_session)):return view(owned(db,user,journey_id))
    @router.put('/api/v1/tf/gps/{journey_id}')
    def save(journey_id:UUID,data:Recording,user:User=Depends(driver),db:Session=Depends(database_session)):
        db.scalar(select(User).where(User.id==user.id).with_for_update())
        row=db.scalar(select(TrainGpsRecording).where(TrainGpsRecording.owner_id==user.id,TrainGpsRecording.journey_id==str(journey_id)).with_for_update())
        if (row.revision if row else 0)!=data.expected_revision:raise HTTPException(409,_text_source('server_gps.text_e9455228bddf'))
        payload=data.model_dump(exclude={'expected_revision'});previous=read_payload(row) if row else {}
        payload['detection_version']=5
        if payload['manual_stops'] is None:payload['manual_stops']=previous.get('manual_stops',[])
        gps_stops=[item for item in analyse(payload['points'])['rows'] if item['kind']==_text_source('server_gps.text_0fd998791d67')]
        stops={'live-'+str(item['start']):item for item in gps_stops}
        for item in payload['manual_stops']:stops[item['key']]=item
        timestamps={p['t'] for p in payload['points']}
        # Retain all historical source IDs even when several halts now merge into one.
        for key in set(previous.get('stop_edits') or {})|set(payload.get('stop_edits') or {}):
            if key.startswith('live-') and key[5:].isdigit() and int(key[5:]) in timestamps:
                match=next((item for item in gps_stops if item['start']<=int(key[5:])<=item['end']),None)
                if match:stops[key]=dict(match,start=int(key[5:]))
                elif key in (previous.get('stop_edits') or {}):stops[key]=dict(start=int(key[5:]))
        edits=payload.get('stop_edits')
        if edits is None:edits={key:value for key,value in (previous.get('stop_edits') or {}).items() if key in stops}
        if any(key not in stops for key in edits):raise HTTPException(422,_text_source('server_gps.text_edfb4f6ac516'))
        for key,edit in edits.items():
            if edit.get('end') is not None and edit['end']<=stops[key]['start']:raise HTTPException(422,_text_source('server_gps.text_6d8354985870'))
            if edit.get('station'):
                code=edit['station'].get('code','').strip().upper()
                if not code:
                    name=edit['station'].get('name','').strip()
                    if not name or len(name)>255:raise HTTPException(422,_text_source('server_gps.text_be7663d51aa2'))
                    edit['station']=dict(code='',name=name)
                else:
                    station=db.get(RailwayStation,code)
                    if not station:raise HTTPException(422,_text_source('server_gps.text_b418a717a2d3'))
                    edit['station']=dict(code=station.code,name=station.name)
        # Preserve explicit assignments from older 0.25/RC recordings.
        for item in analyse(previous.get('points',[]),(previous.get('stop_edits') or {}))['rows']:
            key='live-'+str(item['start'])
            if item['kind']!=_text_source('server_gps.text_0fd998791d67') or key not in stops or key in edits:continue
            station=previous.get('stations',{}).get(item['key']) or previous.get('locations',{}).get(str(item['start']))
            reason=previous.get('reasons',{}).get(item['key'],{})
            if station:edits[key]=dict(station=station,station_input=(station.get('code','')+' · ' if station.get('code') else '')+station.get('name',''),reason=reason.get('reason',''),detail=reason.get('detail',''),end=None,manual_end=False,imported=False)
        payload['stop_edits']=edits
        if 'locations' in previous:payload['locations']=previous['locations']
        payload['stations']=previous.get('stations',{}) if previous.get('points')==payload['points'] else {}
        payload['reasons']=previous.get('reasons',{}) if previous.get('points')==payload['points'] else {}
        payload['selection']=previous.get('selection',[]) if previous.get('points')==payload['points'] else []
        for kind,error in (('start',_text_source('server_gps.text_f96e8bf660b7')),('end',_text_source('server_gps.text_5b9f556e58d7'))):
            code_field,name_field=kind+'_station',kind+'_station_name'
            code=(payload[code_field] or '').strip().upper()
            name=payload[name_field].strip()
            if not code and name_field not in data.model_fields_set and not previous.get(code_field):
                name=previous.get(name_field) or ''
            if code:
                station=db.get(RailwayStation,code)
                if not station:raise HTTPException(422,error)
                code,name=station.code,station.name
            payload[code_field],payload[name_field]=code or None,name
            if name:payload['stations'][kind]=dict(code=code,name=name)
            elif name_field in data.model_fields_set:payload['stations'].pop(kind,None)
        if not row:row=TrainGpsRecording(owner_id=user.id,journey_id=str(journey_id),revision=0);db.add(row)
        row.payload_json=json.dumps(payload,ensure_ascii=False);row.revision+=1;db.commit();return view(row)
    @router.delete('/api/v1/tf/gps/{journey_id}')
    def remove(journey_id:UUID,user:User=Depends(driver),db:Session=Depends(database_session)):
        row=owned(db,user,journey_id,True);db.delete(row);db.commit();return {'ok':True}
    @router.post('/api/v1/tf/gps/{journey_id}/stations')
    def suggest(journey_id:UUID,user:User=Depends(driver),db:Session=Depends(database_session)):
        row=owned(db,user,journey_id);result=view(row)
        # Incremental explicit lookup: one uncached vicinity per click, cached rows together.
        for item in result['analysis']['rows']:
            cell=place_key(item['lat'],item['lon']);cached=db.get(GpsStationCache,cell)
            if not cached or cached.updated_at<=now_utc()-timedelta(days=30):
                station_data(db,item['lat'],item['lon'],nearby=True);break
        for item in result['analysis']['rows']:
            cached=db.get(GpsStationCache,place_key(item['lat'],item['lon']))
            item['candidates']=[dict(station,distance_m=round(distance(item,station))) for station in station_data(db,item['lat'],item['lon'],nearby=True)] if cached and cached.updated_at>now_utc()-timedelta(days=30) else []
            item['lookup_pending']=not cached or cached.updated_at<=now_utc()-timedelta(days=30)
        return result
    @router.put('/api/v1/tf/gps/{journey_id}/stations')
    def choose(journey_id:UUID,data:Choices,user:User=Depends(driver),db:Session=Depends(database_session)):
        from .app_defaults import ensure_defaults,use_value
        ensure_defaults(db)
        row=owned(db,user,journey_id,True)
        if row.revision!=data.expected_revision:raise HTTPException(409,_text_source('server_gps.text_e9455228bddf'))
        payload=read_payload(row);keys={item['key'] for item in analyse(payload['points'],payload.get('stop_edits') or {})['rows']};selected={}
        for key,place in data.stations.items():
            if key in keys:
                if isinstance(place,FreePlace):
                    if place.name.strip():
                        selected[key]=dict(code='',name=place.name.strip())
                        continue
                else:
                    station=db.get(RailwayStation,place.strip().upper())
                    if station:
                        selected[key]=dict(code=station.code,name=station.name)
                        continue
            raise HTTPException(422,_text_source('server_gps.text_c5c16d0e1424'))
        if data.reasons is not None:
            if any(key not in keys for key in data.reasons):raise HTTPException(422,_text_source('server_gps.text_27e6f9d32657'))
            labels={}
            for key,value in sorted(data.reasons.items()):
                if value.reason:labels[key]=use_value(db,'reason',value.reason,payload.get('reasons',{}).get(key,{}).get('reason')).label
            payload['reasons']={key:dict(value.model_dump(),label=labels[key]) for key,value in data.reasons.items() if value.reason}
        if data.selection is not None:
            if any(key not in keys for key in data.selection):raise HTTPException(422,_text_source('server_gps.text_31cbf51014e1'))
            payload['selection']=list(dict.fromkeys(data.selection))
        payload['stations']=selected
        for kind in ('start','end'):
            if kind in selected:
                payload[kind+'_station']=selected[kind]['code'] or None
                payload[kind+'_station_name']=selected[kind]['name']
        row.payload_json=json.dumps(payload,ensure_ascii=False);row.revision+=1;db.commit();return view(row)
    return router
