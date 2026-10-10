import base64
import email
import re
from typing import Literal
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.orm import Session
from ..db import database_session
from ..models import MailboxAccount, User, MailDraft
from . import service


class ConfigInput(BaseModel):
    address: EmailStr
    username: str = Field(min_length=1,max_length=320)
    password: str | None = Field(default=None,min_length=1,max_length=4096)


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
        return value

    @router.get('/config')
    def config(tf_id:int,db:Session=Depends(database_session)):
        target(db,tf_id);value=db.get(MailboxAccount,tf_id)
        return dict(configured=bool(value),address=value.address if value else '',username=value.username if value else '')

    @router.put('/config')
    def save_config(tf_id:int,data:ConfigInput,db:Session=Depends(database_session)):
        target(db,tf_id);value=db.get(MailboxAccount,tf_id)
        if not value and not data.password: raise HTTPException(422,'Postfachpasswort erforderlich')
        encrypted=service.cipher().encrypt(data.password.encode()).decode() if data.password else value.password_encrypted
        if not value: value=MailboxAccount(tf_user_id=tf_id);db.add(value)
        value.address,value.username,value.password_encrypted=str(data.address),data.username,encrypted
        db.commit();return dict(configured=True)

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
