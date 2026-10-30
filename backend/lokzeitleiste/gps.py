"""Private browser-test GPS recordings and cached place-name/DS100 suggestions."""
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
class LocationChoice(BaseModel):
    code:str=Field(default='',max_length=10)
    name:str=Field(min_length=1,max_length=255)
    @model_validator(mode='after')
    def clean(self):
        self.code=self.code.strip().upper();self.name=self.name.strip()
        if not self.name:raise ValueError('Ortsname erforderlich.')
        return self

class Recording(BaseModel):
    train_number:str=Field(pattern=r'^[A-Za-z0-9]{1,12}$')
    points:list[Point]=Field(min_length=1,max_length=20000)
    start_station:str|None=Field(default=None,max_length=10)
    locations:dict[str,LocationChoice]|None=Field(default=None,max_length=1024)
    ended:bool=True
    expected_revision:int=Field(default=0,ge=0)
    @model_validator(mode='after')
    def ordered(self):
        if any(b.t<=a.t for a,b in zip(self.points,self.points[1:])):raise ValueError('GPS-Zeitstempel müssen aufsteigen.')
        if self.points[-1].t-self.points[0].t>48*3600_000:raise ValueError('GPS-Aufzeichnung höchstens 48 Stunden.')
        return self
class StopReason(BaseModel):
    reason:str=Field(default='',max_length=64)
    detail:str=Field(default='',max_length=256)
    @model_validator(mode='after')
    def valid_detail(self):
        self.detail=self.detail.strip() if self.reason=='sonstiges' else ''
        if self.reason=='sonstiges' and not self.detail:raise ValueError('Sonstigen Grund bitte angeben.')
        return self

class Choices(BaseModel):
    expected_revision:int=Field(ge=1)
    stations:dict[str,str]=Field(default_factory=dict,max_length=1024)
    reasons:dict[str,StopReason]|None=Field(default=None,max_length=1024)
    selection:list[str]|None=Field(default=None,max_length=1024)

_lock=threading.Lock();_last_query=0

def osm_query(lat,lon,radius=3500):
    global _last_query
    # One small vicinity query per explicit request; cached for 30 days.
    if not _lock.acquire(blocking=False):raise HTTPException(429,'ZMS-Dienst beschäftigt. Bitte später erneut versuchen.')
    try:
        if time.monotonic()-_last_query<2:raise HTTPException(429,'ZMS-Abfragen bitte mit Abstand wiederholen.')
        _last_query=time.monotonic()
        query=f'[out:json][timeout:12];nwr(around:{radius},{lat:.5f},{lon:.5f})["place"~"^(city|town|village|hamlet|suburb|quarter|neighbourhood|locality|isolated_dwelling)$"]["name"];out center tags;'
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
        if not row:raise HTTPException(404,'Keine GPS-Aufzeichnung vorhanden.')
        return row
    def view(row):
        payload=json.loads(row.payload_json);result=analyse(payload['points'])
        payload.setdefault('reasons',{})
        for item in result['rows']:
            item['station']=payload.get('locations',{}).get(str(item['start'])) if item['kind']=='Halt' else None
            item['station']=item['station'] or payload.get('stations',{}).get(item['key'])
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
        if (row.revision if row else 0)!=data.expected_revision:raise HTTPException(409,'GPS-Aufzeichnung wurde geändert. Bitte neu laden.')
        payload=data.model_dump(exclude={'expected_revision'});previous=json.loads(row.payload_json) if row else {}
        stops={str(item['start']) for item in analyse(payload['points'])['rows'] if item['kind']=='Halt'}
        locations=payload.get('locations')
        if locations is None:locations={key:value for key,value in previous.get('locations',{}).items() if key in stops}
        if any(key not in stops for key in locations):raise HTTPException(422,'Standort gehört nicht zu einem erkannten Halt.')
        for choice in locations.values():
            if choice['code']:
                station=db.get(RailwayStation,choice['code'])
                if not station:raise HTTPException(422,'Bitte eine gültige DS100-Betriebsstelle wählen.')
                choice.update(code=station.code,name=station.name)
        payload['locations']=locations
        payload['stations']=previous.get('stations',{}) if previous.get('points')==payload['points'] else {}
        payload['reasons']=previous.get('reasons',{}) if previous.get('points')==payload['points'] else {}
        payload['selection']=previous.get('selection',[]) if previous.get('points')==payload['points'] else []
        if data.start_station:
            station=db.get(RailwayStation,data.start_station.strip().upper())
            if not station:raise HTTPException(422,'Bitte einen gültigen Startbahnhof (DS100) wählen.')
            payload['start_station']=station.code;payload['stations']['start']=dict(code=station.code,name=station.name)
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
        if row.revision!=data.expected_revision:raise HTTPException(409,'GPS-Aufzeichnung wurde geändert. Bitte neu laden.')
        payload=json.loads(row.payload_json);keys={item['key'] for item in analyse(payload['points'])['rows']};selected={}
        for key,code in data.stations.items():
            station=db.get(RailwayStation,code.strip().upper())
            if key not in keys or not station:raise HTTPException(422,'Bitte gültige DS100-Betriebsstellen wählen.')
            selected[key]=dict(code=station.code,name=station.name)
        if data.reasons is not None:
            if any(key not in keys for key in data.reasons):raise HTTPException(422,'Ungültiger Grund.')
            labels={}
            for key,value in sorted(data.reasons.items()):
                if value.reason:labels[key]=use_value(db,'reason',value.reason,payload.get('reasons',{}).get(key,{}).get('reason')).label
            payload['reasons']={key:dict(value.model_dump(),label=labels[key]) for key,value in data.reasons.items() if value.reason}
        if data.selection is not None:
            if any(key not in keys for key in data.selection):raise HTTPException(422,'Ungültige GPS-Auswahl.')
            payload['selection']=list(dict.fromkeys(data.selection))
        payload['stations']=selected
        if selected.get('start'):payload['start_station']=selected['start']['code']
        row.payload_json=json.dumps(payload,ensure_ascii=False);row.revision+=1;db.commit();return view(row)
    return router
