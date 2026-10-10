import json
from datetime import timedelta
import base64
import email
import re
from typing import Literal
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from ..db import database_session
from ..models import MailboxAccount, MailboxSettings, MailboxAuthorization, User, MailDraft, now_utc
from . import service, oauth
from .providers import ServerInput, PROVIDERS, settings


class ConfigInput(BaseModel):
    servers: ServerInput | None = None
    address: EmailStr
    username: str = Field(min_length=1,max_length=320)
    password: str | None = Field(default=None,min_length=1,max_length=4096)
    @field_validator('username')
    @classmethod
    def valid_username(cls,value):
        value=value.strip()
        if not value or any(ord(c)<32 for c in value):raise ValueError('Ungültige Eingabe')
        return value


class AttachmentInput(BaseModel):
    name: str = Field(min_length=1,max_length=200)
    content_base64: str = Field(max_length=12*1024*1024)
    @field_validator('name')
    @classmethod
    def valid_name(cls,value):
        if any(ord(c)<32 for c in value): raise ValueError('Ungültiger Dateiname')
        return value


class MessageInput(BaseModel):
    to: list[EmailStr] = Field(min_length=1,max_length=20)
    subject: str = Field(max_length=300)
    body: str = Field(max_length=200000)
    in_reply_to: str = Field(default='',max_length=500)
    attachments: list[AttachmentInput] = Field(default_factory=list,max_length=5)
    @field_validator('subject','in_reply_to')
    @classmethod
    def valid_header(cls,value):
        if '\r' in value or '\n' in value: raise ValueError('Ungültige Kopfzeile')
        return value


class DraftInput(BaseModel):
    to: str = Field(default='',max_length=2000)
    subject: str = Field(default='',max_length=300)
    body: str = Field(default='',max_length=200000)


class FlagInput(BaseModel):
    folder: str
    uidvalidity: str
    seen: bool


def create_router(require_admin):
    router=APIRouter(prefix='/api/v1/admin/email/{tf_id}',dependencies=[Depends(require_admin)])
    def target(db,tf_id):
        user=db.get(User,tf_id)
        if not user or user.role!='tf': raise HTTPException(404,'Tf nicht gefunden')
    def account(db,tf_id):
        target(db,tf_id);value=db.get(MailboxAccount,tf_id)
        if not value: raise HTTPException(409,'Für diesen Tf ist noch kein Postfach eingerichtet.')
        value._settings=db.get(MailboxSettings,tf_id);value._db=db
        return value

    @router.get('/config')
    def config(tf_id:int,db:Session=Depends(database_session)):
        target(db,tf_id);value=db.get(MailboxAccount,tf_id)
        if value:value=account(db,tf_id)
        cfg=settings(value) if value else dict(PROVIDERS['manual'],provider='manual',smtp_username='')
        return dict(configured=bool(value),address=value.address if value else '',username=value.username if value else '',servers=cfg,providers=PROVIDERS,oauth_connected=bool(value and value._settings and value._settings.tokens_encrypted),microsoft_available=bool(__import__('os').getenv('MAILBOX_MICROSOFT_CLIENT_ID')))

    @router.put('/config')
    def save_config(tf_id:int,data:ConfigInput,db:Session=Depends(database_session)):
        target(db,tf_id);value=db.get(MailboxAccount,tf_id);row=db.get(MailboxSettings,tf_id)
        old=settings(account(db,tf_id)) if value else None
        cfg=data.servers.model_dump() if data.servers else old
        microsoft=bool(cfg and cfg['provider']=='microsoft')
        changed=bool(value and (({k:v for k,v in (cfg or {}).items() if k!='sent_folder'}!={k:v for k,v in (old or {}).items() if k!='sent_folder'}) or data.username!=value.username or str(data.address)!=value.address))
        if not microsoft and not data.password and (not value or changed or (old and old['provider']=='microsoft')):
            raise HTTPException(422,'Bei geändertem Konto oder Server das Postfachpasswort erneut eingeben.')
        service.cipher()
        encrypted='' if microsoft else service.cipher().encrypt(data.password.encode()).decode() if data.password else (value.password_encrypted if value else '')
        if not value:value=MailboxAccount(tf_user_id=tf_id);db.add(value)
        value.address,value.username,value.password_encrypted=str(data.address),data.username,encrypted
        db.flush()
        if cfg:
            if not row:row=MailboxSettings(tf_user_id=tf_id);db.add(row)
            row.config_json=json.dumps(cfg)
            if changed or not microsoft:row.tokens_encrypted=None
        db.execute(delete(MailboxAuthorization).where(MailboxAuthorization.tf_user_id==tf_id))
        db.commit();return dict(configured=True)

    @router.post('/microsoft/start')
    def start_microsoft(tf_id:int,actor:User=Depends(require_admin),db:Session=Depends(database_session)):
        value=account(db,tf_id)
        if settings(value)['provider']!='microsoft':raise HTTPException(409,'Zuerst Microsoft als Anbieter speichern.')
        client,_=oauth.application();service.cipher()
        result=oauth.request_token('devicecode',dict(client_id=client,scope=oauth.SCOPES))
        if not result.get('device_code') or not result.get('user_code'):raise HTTPException(502,'Microsoft-Anmeldung fehlgeschlagen.')
        now=now_utc();interval=max(5,int(result.get('interval',5)))
        row=db.get(MailboxAuthorization,(tf_id,actor.id))
        if not row:row=MailboxAuthorization(tf_user_id=tf_id,actor_id=actor.id);db.add(row)
        row.device_encrypted=oauth.seal(dict(device_code=result['device_code'],client_id=client,tenant=oauth.application()[1],username=value.username))
        row.expires_at=now+timedelta(seconds=min(1800,int(result.get('expires_in',900))))
        row.next_poll_at=now+timedelta(seconds=interval);row.interval=interval
        db.commit();return dict(user_code=result['user_code'],verification_uri='https://microsoft.com/devicelogin',interval=interval)

    @router.post('/microsoft/finish')
    def finish_microsoft(tf_id:int,actor:User=Depends(require_admin),db:Session=Depends(database_session)):
        value=account(db,tf_id)
        row=db.scalar(select(MailboxAuthorization).where(MailboxAuthorization.tf_user_id==tf_id,MailboxAuthorization.actor_id==actor.id).with_for_update())
        now=now_utc()
        if not row or row.expires_at<=now:raise HTTPException(409,'Microsoft-Anmeldung abgelaufen. Erneut starten.')
        if now<row.next_poll_at:return dict(connected=False,pending=True,interval=row.interval)
        device=oauth.unseal(row.device_encrypted);client,tenant=oauth.application()
        if settings(value)['provider']!='microsoft' or device['client_id']!=client or device['tenant']!=tenant or device['username']!=value.username:
            raise HTTPException(409,'Microsoft-Anmeldung abgelaufen. Erneut starten.')
        result=oauth.request_token('token',dict(client_id=client,grant_type='urn:ietf:params:oauth:grant-type:device_code',device_code=device['device_code']))
        error=result.get('error')
        if error in ('authorization_pending','slow_down'):
            if error=='slow_down':row.interval+=5
            row.next_poll_at=now+timedelta(seconds=row.interval);db.commit();return dict(connected=False,pending=True,interval=row.interval)
        if error:
            db.delete(row);db.commit();raise HTTPException(409,'Microsoft-Anmeldung fehlgeschlagen. Erneut starten.')
        oauth.store_tokens(value._settings,result);db.delete(row);db.commit();return dict(connected=True,pending=False)

    @router.get('/folders')
    def folders(tf_id:int,db:Session=Depends(database_session)):
        with service.connection(account(db,tf_id)) as client:
            status,rows=client.list()
            if status!='OK': raise HTTPException(502,'Ordnerliste konnte nicht gelesen werden')
            result=[]
            for row in rows:
                if not row: continue
                match=re.match(rb'\((.*?)\) (?:".*?"|NIL) (.*)$',row)
                if not match or b'\\Noselect' in match.group(1):continue
                value=match.group(2).decode('ascii')
                if value.startswith('"'):value=value[1:-1].replace('\\"','"').replace('\\\\','\\')
                result.append(value)
            return result

    @router.get('/messages')
    def messages(tf_id:int,folder:str='INBOX',page:int=Query(default=0,ge=0),search:str=Query(default='',max_length=200),db:Session=Depends(database_session)):
        with service.connection(account(db,tf_id)) as client:
            validity=service.select_folder(client,folder)
            # Search headers safely using a quoted IMAP argument, never interpolated command text.
            if search:
                criterion=service.folder_name(search).encode('utf-8')
                status,rows=client.uid('search','UTF-8','OR','SUBJECT',criterion,'FROM',criterion)
            else: status,rows=client.uid('search',None,'ALL')
            if status!='OK':raise HTTPException(502,'Nachrichtensuche fehlgeschlagen')
            uids=rows[0].split()[::-1] if rows and rows[0] else []
            result=[]
            for uid in uids[page*25:(page+1)*25]:
                status,parts=client.uid('fetch',uid,'(FLAGS BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE)])')
                if status!='OK':continue
                msg=email.message_from_bytes(service.payload_bytes(parts),policy=email.policy.default)
                meta=b' '.join(p[0] if isinstance(p,tuple) else p for p in parts if isinstance(p,(tuple,bytes)))
                result.append(dict(uid=int(uid),sender=str(msg.get('From','')),subject=str(msg.get('Subject','')),date=str(msg.get('Date','')),seen=b'\\Seen' in meta))
            return dict(messages=result,total=len(uids),page=page,uidvalidity=validity)

    @router.get('/messages/{uid}')
    def message(tf_id:int,uid:int,folder:str,uidvalidity:str,db:Session=Depends(database_session)):
        if uid<1:raise HTTPException(422,'Ungültige Nachrichtenkennung')
        with service.connection(account(db,tf_id)) as client:
            service.select_folder(client,folder,uidvalidity)
            return service.view_message(service.message_bytes(client,uid))

    @router.get('/messages/{uid}/attachments/{index}')
    def attachment(tf_id:int,uid:int,index:int,folder:str,uidvalidity:str,db:Session=Depends(database_session)):
        if uid<1 or index<0:raise HTTPException(422,'Ungültiger Anhang')
        with service.connection(account(db,tf_id)) as client:
            service.select_folder(client,folder,uidvalidity)
            items=list(service.message_bytes(client,uid).iter_attachments())
            if index>=len(items):raise HTTPException(404,'Anhang nicht gefunden')
            item=items[index];content=item.get_payload(decode=True) or b''
            name=item.get_filename() or 'Anhang'
            return Response(content,media_type='application/octet-stream',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(name,safe=''),'X-Content-Type-Options':'nosniff'})

    @router.post('/messages/{uid}/seen')
    def flag(tf_id:int,uid:int,data:FlagInput,db:Session=Depends(database_session)):
        if uid<1:raise HTTPException(422,'Ungültige Nachrichtenkennung')
        with service.connection(account(db,tf_id)) as client:
            service.select_folder(client,data.folder,data.uidvalidity,readonly=False)
            status,_=client.uid('store',str(uid),'+FLAGS.SILENT' if data.seen else '-FLAGS.SILENT','(\\Seen)')
            if status!='OK':raise HTTPException(502,'Lesestatus konnte nicht geändert werden')
        return dict(saved=True)

    @router.post('/send')
    def send(tf_id:int,data:MessageInput,db:Session=Depends(database_session)):
        return service.send(account(db,tf_id),data)

    @router.get('/draft')
    def draft(tf_id:int,actor:User=Depends(require_admin),db:Session=Depends(database_session)):
        target(db,tf_id);item=db.get(MailDraft,(actor.id,tf_id))
        return dict(to=item.recipient if item else '',subject=item.subject if item else '',body=item.body if item else '')

    @router.put('/draft')
    def save_draft(tf_id:int,data:DraftInput,actor:User=Depends(require_admin),db:Session=Depends(database_session)):
        target(db,tf_id);item=db.get(MailDraft,(actor.id,tf_id))
        if not item:item=MailDraft(actor_id=actor.id,tf_user_id=tf_id);db.add(item)
        item.recipient,item.subject,item.body=data.to,data.subject,data.body;db.commit();return dict(saved=True)
    return router
