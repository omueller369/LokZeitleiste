"""Authenticated TF sharing of immutable station snapshots by revocable token."""
import hashlib
import json
import secrets
from datetime import timedelta
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter,Depends,HTTPException,Path as ApiPath
from fastapi.responses import FileResponse,Response
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import database_session
from .models import User,TfProfile,TfStation,TfStationPlan,TfStationShare,TfStationShareItem,now_utc
from .stations import StationContact,contacts_json
from .work_reports.receipts import MAX_FILE

MAX_STATIONS=50
MAX_PLANS=20*1024*1024


class ShareCreate(BaseModel):
    station_ids:list[int]=Field(min_length=1,max_length=MAX_STATIONS)
    include_plans:bool=False

    @field_validator('station_ids')
    @classmethod
    def unique(cls,value):
        if len(value)!=len(set(value)) or any(n<1 for n in value):raise ValueError('Ungültige Bahnhofsauswahl.')
        return value


class ImportItem(BaseModel):
    id:int=Field(ge=1)
    expected_revision:int=Field(ge=0)


class ShareImport(BaseModel):
    items:list[ImportItem]=Field(min_length=1,max_length=MAX_STATIONS)
    mode:Literal['new_only','merge']='merge'
    include_plans:bool=True

    @field_validator('items')
    @classmethod
    def unique(cls,value):
        if len({item.id for item in value})!=len(value):raise ValueError('Ungültige Bahnhofsauswahl.')
        return value


def contact_key(contact):
    return (contact['category'],contact['label'].strip().casefold(),''.join(contact['number'].split()).casefold())


def create_router(driver):
    router=APIRouter()

    def shared(db,token,lock=False):
        query=select(TfStationShare).where(TfStationShare.token_hash==hashlib.sha256(token.encode()).hexdigest())
        share=db.scalar(query.with_for_update(read=True) if lock else query)
        if not share or share.revoked or share.expires_at<=now_utc():
            raise HTTPException(404,'Freigabe nicht gefunden oder abgelaufen.')
        return share

    @router.get('/tf/station-sharing.js')
    def script():
        return FileResponse(Path(__file__).parent/'static'/'station-sharing.js',media_type='text/javascript',headers={'Cache-Control':'no-cache'})

    @router.post('/api/v1/tf/station-shares',status_code=201)
    def create(data:ShareCreate,user:User=Depends(driver),db:Session=Depends(database_session)):
        db.scalar(select(User).where(User.id==user.id).with_for_update())
        rows=db.scalars(select(TfStation).where(TfStation.owner_id==user.id,TfStation.id.in_(data.station_ids)).order_by(TfStation.code).with_for_update()).all()
        if len(rows)!=len(data.station_ids):raise HTTPException(404,'Bahnhofseintrag nicht gefunden.')
        token=secrets.token_urlsafe(32)
        share=TfStationShare(owner_id=user.id,token_hash=hashlib.sha256(token.encode()).hexdigest(),expires_at=now_utc()+timedelta(days=30),revoked=False)
        db.add(share);db.flush();total=0
        for row in rows:
            contacts=[StationContact.model_validate(contact) for contact in json.loads(row.contacts_json)]
            plan=db.scalar(select(TfStationPlan).where(TfStationPlan.station_id==row.id).with_for_update()) if data.include_plans else None
            content=plan.content if plan else None
            total+=len(content) if content else 0
            if (content and len(content)>MAX_FILE) or total>MAX_PLANS:
                raise HTTPException(413,'Bahnhofspläne zusammen höchstens 20 MB; Auswahl verkleinern oder ohne Pläne teilen.')
            db.add(TfStationShareItem(share_id=share.id,code=row.code,name=row.name,contacts_json=contacts_json(contacts),
                plan_filename=plan.filename if plan else None,plan_mime_type=plan.mime_type if plan else None,plan_content=content))
        db.commit()
        return dict(id=share.id,token=token,expires_at=share.expires_at.isoformat(),stations=len(rows))

    @router.get('/api/v1/tf/station-shares')
    def mine(user:User=Depends(driver),db:Session=Depends(database_session)):
        shares=db.scalars(select(TfStationShare).where(TfStationShare.owner_id==user.id).order_by(TfStationShare.id.desc()).limit(50)).all()
        result=[]
        for share in shares:
            codes=list(db.scalars(select(TfStationShareItem.code).where(TfStationShareItem.share_id==share.id).order_by(TfStationShareItem.code)))
            result.append(dict(id=share.id,codes=codes,created_at=share.created_at.isoformat(),expires_at=share.expires_at.isoformat(),
                               revoked=share.revoked,active=not share.revoked and share.expires_at>now_utc()))
        return result

    @router.delete('/api/v1/tf/station-shares/mine/{share_id}')
    def revoke(share_id:int,user:User=Depends(driver),db:Session=Depends(database_session)):
        db.scalar(select(User).where(User.id==user.id).with_for_update())
        share=db.scalar(select(TfStationShare).where(TfStationShare.id==share_id,TfStationShare.owner_id==user.id).with_for_update())
        if not share:raise HTTPException(404,'Freigabe nicht gefunden oder abgelaufen.')
        share.revoked=True;db.commit();return {'ok':True}

    @router.get('/api/v1/tf/station-shares/{token}')
    def preview(token:str=ApiPath(pattern=r'^[A-Za-z0-9_-]{43}$'),user:User=Depends(driver),db:Session=Depends(database_session)):
        share=shared(db,token)
        profile=db.get(TfProfile,share.owner_id)
        rows=db.scalars(select(TfStationShareItem).where(TfStationShareItem.share_id==share.id).order_by(TfStationShareItem.code)).all()
        own={row.code:row for row in db.scalars(select(TfStation).where(TfStation.owner_id==user.id,TfStation.code.in_([item.code for item in rows])))}
        return dict(sender=(profile.first_name+' '+profile.last_name) if profile else '',expires_at=share.expires_at.isoformat(),
                    items=[dict(id=row.id,code=row.code,name=row.name,contacts=json.loads(row.contacts_json),
                                plan=dict(filename=row.plan_filename,mime_type=row.plan_mime_type) if row.plan_content else None,
                                expected_revision=own[row.code].revision if row.code in own else 0) for row in rows])

    @router.get('/api/v1/tf/station-shares/{token}/items/{item_id}/plan')
    def plan(item_id:int,token:str=ApiPath(pattern=r'^[A-Za-z0-9_-]{43}$'),user:User=Depends(driver),db:Session=Depends(database_session)):
        share=shared(db,token)
        row=db.scalar(select(TfStationShareItem).where(TfStationShareItem.id==item_id,TfStationShareItem.share_id==share.id))
        if not row or not row.plan_content:raise HTTPException(404,'Kein Bahnhofsplan vorhanden.')
        return Response(row.plan_content,media_type=row.plan_mime_type,headers={
            'Content-Disposition':"attachment; filename*=UTF-8''"+quote(row.plan_filename,safe=''),
            'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})

    @router.post('/api/v1/tf/station-shares/{token}/import')
    def import_entries(data:ShareImport,token:str=ApiPath(pattern=r'^[A-Za-z0-9_-]{43}$'),user:User=Depends(driver),db:Session=Depends(database_session)):
        db.scalar(select(User).where(User.id==user.id).with_for_update())
        share=shared(db,token,True)
        rows=db.scalars(select(TfStationShareItem).where(TfStationShareItem.share_id==share.id,TfStationShareItem.id.in_([item.id for item in data.items])).order_by(TfStationShareItem.code)).all()
        if len(rows)!=len(data.items):raise HTTPException(404,'Bahnhofseintrag nicht gefunden.')
        revisions={item.id:item.expected_revision for item in data.items}
        result=dict(created=0,extended=0,unchanged=0,skipped=0,plans_added=0)
        for source in rows:
            target=db.scalar(select(TfStation).where(TfStation.owner_id==user.id,TfStation.code==source.code).with_for_update())
            if (target.revision if target else 0)!=revisions[source.id]:
                raise HTTPException(409,'Eigene Bahnhofsliste wurde geändert. Freigabe erneut laden.')
            if target and data.mode=='new_only':result['skipped']+=1;continue
            existing=json.loads(target.contacts_json) if target else []
            incoming=json.loads(source.contacts_json)
            seen={contact_key(contact) for contact in existing};merged=list(existing)
            for contact in incoming:
                key=contact_key(contact)
                if key not in seen:merged.append(contact);seen.add(key)
            if len(merged)>100:raise HTTPException(409,'Ergänzung überschreitet 100 Nummern; Bahnhof einzeln prüfen.')
            encoded=contacts_json([StationContact.model_validate(contact) for contact in merged])
            created=target is None;changed=created or encoded!=(target.contacts_json if target else '')
            if created:
                target=TfStation(owner_id=user.id,code=source.code,name=source.name,contacts_json=encoded,revision=1)
                db.add(target);db.flush()
            else:target.contacts_json=encoded
            if data.include_plans and source.plan_content:
                target_plan=db.scalar(select(TfStationPlan).where(TfStationPlan.station_id==target.id).with_for_update())
                if not target_plan:
                    db.add(TfStationPlan(station_id=target.id,filename=source.plan_filename,mime_type=source.plan_mime_type,content=source.plan_content))
                    result['plans_added']+=1;changed=True
            if created:result['created']+=1
            elif changed:target.revision+=1;result['extended']+=1
            else:result['unchanged']+=1
        db.commit();return result

    return router
