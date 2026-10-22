"""Private browser-test GPS recordings and cached OSM operating-site suggestions."""
import json,math,time,threading,urllib.request,urllib.parse
from datetime import timedelta
from pathlib import Path
from uuid import UUID
from typing import Annotated
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel,Field,model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .db import database_session
from .models import User,RailwayStation,TrainGpsRecording,GpsStationCache,now_utc
from .tf_portal import driver_dependency
from .gps_analysis import analyse,candidates

_finite=Annotated[float,Field(allow_inf_nan=False)]
class Point(BaseModel):
    t:int=Field(ge=946684800000,le=4133980800000)
    lat:_finite=Field(ge=-90,le=90)
    lon:_finite=Field(ge=-180,le=180)
    accuracy:_finite=Field(ge=0,le=100000)
    speed:_finite|None=Field(default=None,ge=0,le=200)
class Recording(BaseModel):
    train_number:str=Field(pattern=r'^[A-Za-z0-9]{1,12}$')
    points:list[Point]=Field(min_length=1,max_length=20000)
    ended:bool=True
    expected_revision:int=Field(default=0,ge=0)
    @model_validator(mode='after')
    def ordered(self):
        if any(b.t<=a.t for a,b in zip(self.points,self.points[1:])):raise ValueError('GPS-Zeitstempel müssen aufsteigen.')
        if self.points[-1].t-self.points[0].t>48*3600_000:raise ValueError('GPS-Aufzeichnung höchstens 48 Stunden.')
        return self
class Choices(BaseModel):
    expected_revision:int=Field(ge=1)
    stations:dict[str,str]=Field(default_factory=dict,max_length=1024)

_lock=threading.Lock();_last_query=0

def osm_query(lat,lon):
    global _last_query
    # One small vicinity query per explicit request; cached for 30 days.
    if not _lock.acquire(blocking=False):raise HTTPException(429,'ZMS-Dienst beschäftigt. Bitte später erneut versuchen.')
    try:
        if time.monotonic()-_last_query<2:raise HTTPException(429,'ZMS-Abfragen bitte mit Abstand wiederholen.')
        _last_query=time.monotonic()
        query=f'[out:json][timeout:12];nwr(around:3500,{lat:.5f},{lon:.5f})["railway"~"^(station|halt|junction|yard|service_station|crossover|blockpost)$"];out center tags;'
        request=urllib.request.Request('https://overpass-api.de/api/interpreter',data=urllib.parse.urlencode({'data':query}).encode(),headers={'User-Agent':'LokZeitleiste-GPS-Browsertest/1.0 (+https://github.com/omueller369/LokZeitleiste)','Content-Type':'application/x-www-form-urlencoded'})
        try:
            with urllib.request.urlopen(request,timeout=18) as response:
                raw=response.read(2*1024*1024+1)
            if len(raw)>2*1024*1024:raise ValueError('Response too large')
            data=json.loads(raw)
            if data.get('remark'):raise ValueError('Incomplete OSM response')
            return data.get('elements',[])
        except Exception as exc:raise HTTPException(503,'ZMS-Daten derzeit nicht verfügbar. GPS bleibt gespeichert.') from exc
    finally:_lock.release()

def station_data(db,lat,lon):
    cell=f'{round(lat,2):.2f},{round(lon,2):.2f}';cached=db.get(GpsStationCache,cell)
    if cached and cached.updated_at>now_utc()-timedelta(days=30):elements=json.loads(cached.payload_json)
    else:
        # Center on the rounded cell, so cached coverage is identical for every caller.
        elements=osm_query(round(lat,2),round(lon,2))
        if not cached:cached=GpsStationCache(cell=cell);db.add(cached)
        cached.payload_json=json.dumps(elements,ensure_ascii=False);cached.updated_at=now_utc()
        try:db.commit()
        except IntegrityError:
            db.rollback();cached=db.get(GpsStationCache,cell)
            if not cached:raise
            elements=json.loads(cached.payload_json)
    stations=[];seen=set()
    for item in elements:
        tags=item.get('tags',{});code=(tags.get('ref:DB') or tags.get('railway:ref') or '').strip().upper()
        catalog=db.get(RailwayStation,code) if code and len(code)<=10 else None
        if not catalog:continue
        point=item if 'lat' in item else item.get('center',{})
        if code in seen or not isinstance(point.get('lat'),(int,float)) or not isinstance(point.get('lon'),(int,float)):continue
        if not math.isfinite(point['lat']) or not math.isfinite(point['lon']) or not -90<=point['lat']<=90 or not -180<=point['lon']<=180:continue
        seen.add(code);stations.append(dict(code=code,name=catalog.name,lat=point['lat'],lon=point['lon']))
    return stations

def create_router(require_account):
    router=APIRouter();driver=driver_dependency(require_account)
    def owned(db,user,journey_id,lock=False):
        if lock:db.scalar(select(User).where(User.id==user.id).with_for_update())
        query=select(TrainGpsRecording).where(TrainGpsRecording.owner_id==user.id,TrainGpsRecording.journey_id==str(journey_id))
        row=db.scalar(query.with_for_update() if lock else query)
        if not row:raise HTTPException(404,'Keine GPS-Aufzeichnung vorhanden.')
        return row
    def view(row):
        payload=json.loads(row.payload_json);result=analyse(payload['points'])
        for item in result['rows']:item['station']=payload.get('stations',{}).get(item['key'])
        return dict(payload,revision=row.revision,analysis=result)
    @router.get('/tf/gps.js')
    def script():return FileResponse(Path(__file__).parent/'static'/'gps.js',media_type='text/javascript',headers={'Cache-Control':'no-cache'})
    @router.get('/api/v1/tf/gps/{journey_id}')
    def get(journey_id:UUID,user:User=Depends(driver),db:Session=Depends(database_session)):return view(owned(db,user,journey_id))
    @router.put('/api/v1/tf/gps/{journey_id}')
    def save(journey_id:UUID,data:Recording,user:User=Depends(driver),db:Session=Depends(database_session)):
        db.scalar(select(User).where(User.id==user.id).with_for_update())
        row=db.scalar(select(TrainGpsRecording).where(TrainGpsRecording.owner_id==user.id,TrainGpsRecording.journey_id==str(journey_id)).with_for_update())
        if (row.revision if row else 0)!=data.expected_revision:raise HTTPException(409,'GPS-Aufzeichnung wurde geändert. Bitte neu laden.')
        payload=data.model_dump(exclude={'expected_revision'});previous=json.loads(row.payload_json) if row else {}
        payload['stations']=previous.get('stations',{}) if previous.get('points')==payload['points'] else {}
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
            cell=f'{round(item["lat"],2):.2f},{round(item["lon"],2):.2f}';cached=db.get(GpsStationCache,cell)
            if not cached or cached.updated_at<=now_utc()-timedelta(days=30):
                station_data(db,item['lat'],item['lon']);break
        for item in result['analysis']['rows']:
            cached=db.get(GpsStationCache,f'{round(item["lat"],2):.2f},{round(item["lon"],2):.2f}')
            item['candidates']=candidates(item,station_data(db,item['lat'],item['lon'])) if cached and cached.updated_at>now_utc()-timedelta(days=30) else []
            item['lookup_pending']=not cached or cached.updated_at<=now_utc()-timedelta(days=30)
        return result
    @router.put('/api/v1/tf/gps/{journey_id}/stations')
    def choose(journey_id:UUID,data:Choices,user:User=Depends(driver),db:Session=Depends(database_session)):
        row=owned(db,user,journey_id,True)
        if row.revision!=data.expected_revision:raise HTTPException(409,'GPS-Aufzeichnung wurde geändert. Bitte neu laden.')
        payload=json.loads(row.payload_json);keys={item['key'] for item in analyse(payload['points'])['rows']};selected={}
        for key,code in data.stations.items():
            station=db.get(RailwayStation,code.strip().upper())
            if key not in keys or not station:raise HTTPException(422,'Bitte gültige DS100-Betriebsstellen wählen.')
            selected[key]=dict(code=station.code,name=station.name)
        payload['stations']=selected;row.payload_json=json.dumps(payload,ensure_ascii=False);row.revision+=1;db.commit();return view(row)
    return router
