"""Authenticated TF sharing of immutable station snapshots through a recipient-owned inbox."""
import hashlib
import json
import secrets
from datetime import timedelta
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import FileResponse,Response
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import database_session
from .models import User,TfProfile,TfStation,TfStationPlan,TfStationShare,TfStationShareItem,TfStationDelivery,TfStationNotes,TfStationShareNotes,TfEmployment,now_utc
from .stations import StationContact,contacts_json,NOTE_FIELDS,notes_view
from .work_reports.receipts import MAX_FILE

MAX_STATIONS=50
MAX_PLANS=20*1024*1024


class ShareCreate(BaseModel):
    station_ids:list[int]=Field(min_length=1,max_length=MAX_STATIONS)
    recipient_id:int=Field(ge=1)
    include_plans:bool=False

    @field_validator('station_ids')
    @classmethod
    def unique(cls,value):
        if len(value)!=len(set(value)) or any(n<1 for n in value):raise ValueError('Ungültige Bahnhofsauswahl.')
        return value


class ImportItem(BaseModel):
    id:int=Field(ge=1)
    expected_revision:int=Field(ge=0)
    target_station_id:int|None=Field(default=None,ge=1)


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

    def shared(db,delivery_id,user,lock=False):
        query=select(TfStationDelivery).where(TfStationDelivery.id==delivery_id,TfStationDelivery.recipient_id==user.id)
        delivery=db.scalar(query.with_for_update() if lock else query)
        if not delivery:raise HTTPException(404,'Zusendung nicht gefunden.')
        return db.get(TfStationShare,delivery.share_id)

    def available(db,user):
        employment=db.get(TfEmployment,user.id)
        return user.active and (not employment or (not employment.immediate_block and (not employment.exit_date or employment.exit_date>now_utc().date())))

    @router.get('/api/v1/tf/station-recipients')
    def recipients(user:User=Depends(driver),db:Session=Depends(database_session)):
        rows=db.execute(select(User,TfProfile).join(TfProfile,TfProfile.user_id==User.id).where(User.role=='tf',User.active.is_(True),User.id!=user.id).order_by(TfProfile.last_name,TfProfile.first_name,User.id)).all()
        return [dict(id=u.id,label=f'{p.first_name} {p.last_name}') for u,p in rows if available(db,u)]

    @router.get('/tf/station-sharing.js')
    def script():
        return FileResponse(Path(__file__).parent/'static'/'station-sharing.js',media_type='text/javascript',headers={'Cache-Control':'no-cache'})

    @router.post('/api/v1/tf/station-shares',status_code=201)
    def create(data:ShareCreate,user:User=Depends(driver),db:Session=Depends(database_session)):
        db.scalar(select(User).where(User.id==user.id).with_for_update())
        recipient=db.get(User,data.recipient_id)
        if not recipient or recipient.role!='tf' or not available(db,recipient) or recipient.id==user.id or not db.get(TfProfile,recipient.id):
            raise HTTPException(422,'Bitte einen anderen aktiven TF auswählen.')
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
            item=TfStationShareItem(share_id=share.id,code=row.code,name=row.name,contacts_json=contacts_json(contacts),
                plan_filename=plan.filename if plan else None,plan_mime_type=plan.mime_type if plan else None,plan_content=content)
            db.add(item);db.flush()
            db.add(TfStationShareNotes(item_id=item.id,**notes_view(db,TfStationNotes,row.id)))
        delivery=TfStationDelivery(share_id=share.id,recipient_id=recipient.id);db.add(delivery);db.commit()
        return dict(id=delivery.id,stations=len(rows))

    @router.get('/api/v1/tf/station-inbox')
    def inbox(user:User=Depends(driver),db:Session=Depends(database_session)):
        rows=db.execute(select(TfStationDelivery,TfStationShare).join(TfStationShare,TfStationDelivery.share_id==TfStationShare.id).where(TfStationDelivery.recipient_id==user.id).order_by(TfStationDelivery.id.desc())).all()
        result=[]
        for delivery,share in rows:
            profile=db.get(TfProfile,share.owner_id)
            codes=list(db.scalars(select(TfStationShareItem.code).where(TfStationShareItem.share_id==share.id).order_by(TfStationShareItem.code)))
            result.append(dict(id=delivery.id,codes=codes,sender=f'{profile.first_name} {profile.last_name}' if profile else '',created_at=share.created_at.isoformat()))
        return result

    @router.delete('/api/v1/tf/station-inbox/{delivery_id}')
    def remove(delivery_id:int,user:User=Depends(driver),db:Session=Depends(database_session)):
        db.scalar(select(User).where(User.id==user.id).with_for_update())
        share=shared(db,delivery_id,user,True)
        delivery=db.scalar(select(TfStationDelivery).where(TfStationDelivery.share_id==share.id))
        db.delete(delivery);db.flush();db.delete(share);db.commit()
        return {'ok':True}

    @router.get('/api/v1/tf/station-inbox/{delivery_id}')
    def preview(delivery_id:int,user:User=Depends(driver),db:Session=Depends(database_session)):
        share=shared(db,delivery_id,user)
        profile=db.get(TfProfile,share.owner_id)
        rows=db.scalars(select(TfStationShareItem).where(TfStationShareItem.share_id==share.id).order_by(TfStationShareItem.code)).all()
        own={row.code:row for row in db.scalars(select(TfStation).where(TfStation.owner_id==user.id,TfStation.code.in_([item.code for item in rows])))}
        return dict(sender=(profile.first_name+' '+profile.last_name) if profile else '',created_at=share.created_at.isoformat(),
                    items=[dict(**notes_view(db,TfStationShareNotes,row.id),id=row.id,code=row.code,name=row.name,contacts=json.loads(row.contacts_json),
                                plan=dict(filename=row.plan_filename,mime_type=row.plan_mime_type) if row.plan_content else None,
                                expected_revision=own[row.code].revision if row.code in own else 0) for row in rows])

    @router.get('/api/v1/tf/station-inbox/{delivery_id}/items/{item_id}/plan')
    def plan(item_id:int,delivery_id:int,user:User=Depends(driver),db:Session=Depends(database_session)):
        share=shared(db,delivery_id,user)
        row=db.scalar(select(TfStationShareItem).where(TfStationShareItem.id==item_id,TfStationShareItem.share_id==share.id))
        if not row or not row.plan_content:raise HTTPException(404,'Kein Bahnhofsplan vorhanden.')
        return Response(row.plan_content,media_type=row.plan_mime_type,headers={
            'Content-Disposition':"attachment; filename*=UTF-8''"+quote(row.plan_filename,safe=''),
            'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})

    @router.post('/api/v1/tf/station-inbox/{delivery_id}/import')
    def import_entries(data:ShareImport,delivery_id:int,user:User=Depends(driver),db:Session=Depends(database_session)):
        db.scalar(select(User).where(User.id==user.id).with_for_update())
        share=shared(db,delivery_id,user,True)
        rows=db.scalars(select(TfStationShareItem).where(TfStationShareItem.share_id==share.id,TfStationShareItem.id.in_([item.id for item in data.items])).order_by(TfStationShareItem.code)).all()
        if len(rows)!=len(data.items):raise HTTPException(404,'Bahnhofseintrag nicht gefunden.')
        revisions={item.id:item.expected_revision for item in data.items}
        targets={item.id:item.target_station_id for item in data.items}
        used=set()
        result=dict(created=0,extended=0,unchanged=0,skipped=0,plans_added=0)
        for source in rows:
            condition=TfStation.id==targets[source.id] if targets[source.id] else TfStation.code==source.code
            target=db.scalar(select(TfStation).where(TfStation.owner_id==user.id,condition).with_for_update())
            if targets[source.id] and not target:raise HTTPException(404,'Bahnhofseintrag nicht gefunden.')
            destination=('id',target.id) if target else ('code',source.code)
            if destination in used:raise HTTPException(422,'Jeden Zielbahnhof nur einmal pro Übernahme auswählen.')
            used.add(destination)
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
            incoming_notes=notes_view(db,TfStationShareNotes,source.id)
            target_notes=db.get(TfStationNotes,target.id)
            for field in NOTE_FIELDS:
                if incoming_notes[field] and (not target_notes or not getattr(target_notes,field)):
                    if not target_notes:target_notes=TfStationNotes(station_id=target.id);db.add(target_notes)
                    setattr(target_notes,field,incoming_notes[field]);changed=True
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
