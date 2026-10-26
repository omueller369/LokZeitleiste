"""TF-to-TF inbox. No SMTP, usernames or TF numbers in message-facing responses."""
import io
from pathlib import Path,PurePosixPath
from fastapi import APIRouter,Depends,File,Form,UploadFile,HTTPException,Query
from fastapi.responses import FileResponse,Response
from pydantic import BaseModel,Field,ValidationError,field_validator
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from PIL import Image
from .db import database_session
from .models import StaffProfile,User,TfProfile,TfMessage as Message,TfMessageDelivery as Delivery,TfMessageAttachment as Attachment,now_utc
from .security import account_active
from .accounts.access import ready

MAX_FILE=10*1024*1024
class Recipients(BaseModel):
    recipients:list[int]=Field(default_factory=list,max_length=5000)
    all_tf:bool=False
class MessageIn(Recipients):
    subject:str=Field(min_length=1,max_length=200)
    body:str=Field(min_length=1,max_length=1000)
    @field_validator('subject','body')
    @classmethod
    def nonempty(cls,value):
        value=value.strip()
        if not value:raise ValueError('Betreff und Nachricht dürfen nicht leer sein.')
        return value
class ReadIn(BaseModel):read:bool

def name(profile):
    if not profile:raise HTTPException(404,'Tf nicht gefunden')
    return (profile.first_name+' '+profile.last_name).strip()
def identity(db,user):
    profile=db.get(TfProfile if user.role=='tf' else StaffProfile,user.id)
    return name(profile) if profile else 'Administration'
def recipients(db):
    rows=[]
    for u in db.scalars(select(User).where(User.role.in_(['tf','staff','admin']),User.active==True)):
        if account_active(db,u):rows.append((u,identity(db,u)))
    return sorted(rows,key=lambda row:(row[0].role=='tf',row[1].casefold(),row[0].id))

def targets(db,data):
    active={u.id for u,p in recipients(db)};selected={u.id for u,p in recipients(db) if u.role=='tf'} if data.all_tf else set(data.recipients)
    if not selected:raise HTTPException(422,'Bitte mindestens einen Empfänger auswählen.')
    if not selected<=active:raise HTTPException(422,'Ein ausgewählter Empfänger ist nicht mehr verfügbar. Bitte die Empfängerliste aktualisieren.')
    return selected

def owned(db,user,message_id):
    delivery=db.scalar(select(Delivery).where(Delivery.message_id==message_id,Delivery.recipient_id==user.id,Delivery.deleted_at.is_(None)).with_for_update())
    if not delivery:raise HTTPException(404,'Nachricht nicht gefunden.')
    return delivery,db.get(Message,message_id)

def view(db,message,delivery,detail=False):
    file=db.get(Attachment,message.attachment_id) if detail and message.attachment_id else None
    result=dict(id=message.id,sender_name=message.sender_name,subject=message.subject,created_at=message.created_at.isoformat()+'Z',read=delivery.read_at is not None,has_attachment=message.attachment_id is not None)
    if detail:result.update(body=message.body,attachment=dict(filename=file.filename,mime_type=file.mime_type,size=len(file.content),url=f'/api/v1/tf/messages/{message.id}/attachment') if file else None)
    return result


def sent_owned(db,user,message_id):
    message=db.scalar(select(Message).where(Message.id==message_id,Message.sender_id==user.id))
    if not message:raise HTTPException(404,'Nachricht nicht gefunden.')
    return message

def sent_view(db,message,detail=False):
    names=[identity(db,u) for u in db.scalars(select(User).join(Delivery,Delivery.recipient_id==User.id).where(Delivery.message_id==message.id).order_by(User.id))]
    result=dict(id=message.id,subject=message.subject,sender_name=message.sender_name,recipient_names=names,created_at=message.created_at.isoformat()+'Z',has_attachment=message.attachment_id is not None)
    if detail:
        file=db.get(Attachment,message.attachment_id) if message.attachment_id else None
        result.update(body=message.body,attachment=dict(filename=file.filename,mime_type=file.mime_type,size=len(file.content),url=f'/api/v1/tf/messages/sent/{message.id}/attachment') if file else None)
    return result

def create_router(require_account):
    router=APIRouter()
    def driver(user=Depends(require_account),db:Session=Depends(database_session)):
        if user.role not in ('tf','staff','admin'):raise HTTPException(403,'Keine Freigabe.')
        ready(db,user)
        return user
    @router.get('/admin/messages')
    def backend_page():
        content=(Path(__file__).parent/'static'/'tf-messages.html').read_text()
        content=content.replace('TF-Portal','Verwaltung').replace('<header><h1>Verwaltung</h1></header>','<header><a href="/admin/start">Verwaltung</a></header>').replace('</body>','<script src="/admin/backend-nav.js"></script></body>')
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content,headers={'Cache-Control':'no-store'})
    @router.get('/tf/messages.js')
    def script():return FileResponse(Path(__file__).parent/'static'/'tf-messages.js',media_type='text/javascript',headers={'Cache-Control':'no-cache'})
    @router.get('/api/v1/tf/messages/recipients')
    def choices(user=Depends(driver),db:Session=Depends(database_session)):return [dict(id=u.id,name=p,group='TF' if u.role=='tf' else 'Sachbearbeiter') for u,p in recipients(db)]
    @router.get('/api/v1/tf/messages/unread')
    def unread(user=Depends(driver),db:Session=Depends(database_session)):
        return dict(count=db.scalar(select(func.count()).select_from(Delivery).join(Message,Message.id==Delivery.message_id).where(Delivery.recipient_id==user.id,Message.sender_id!=user.id,Delivery.read_at.is_(None),Delivery.deleted_at.is_(None))))
    @router.get('/api/v1/tf/messages')
    def listing(offset:int=Query(default=0,ge=0),limit:int=Query(default=50,ge=1,le=100),user=Depends(driver),db:Session=Depends(database_session)):
        query=select(Delivery,Message).join(Message,Message.id==Delivery.message_id).where(Delivery.recipient_id==user.id,Delivery.deleted_at.is_(None))
        total=db.scalar(select(func.count()).select_from(query.subquery()))
        rows=db.execute(query.order_by(Message.created_at.desc(),Message.id.desc()).offset(offset).limit(limit)).all()
        return dict(total=total,messages=[view(db,m,d) for d,m in rows])
    @router.get('/api/v1/tf/messages/sent')
    def sent_listing(offset:int=Query(default=0,ge=0),limit:int=Query(default=50,ge=1,le=100),user=Depends(driver),db:Session=Depends(database_session)):
        query=select(Message).where(Message.sender_id==user.id)
        total=db.scalar(select(func.count()).select_from(query.subquery()))
        rows=db.scalars(query.order_by(Message.created_at.desc(),Message.id.desc()).offset(offset).limit(limit)).all()
        return dict(total=total,messages=[sent_view(db,m) for m in rows])
    @router.get('/api/v1/tf/messages/sent/{message_id}')
    def sent_detail(message_id:int,user=Depends(driver),db:Session=Depends(database_session)):
        return sent_view(db,sent_owned(db,user,message_id),True)
    @router.get('/api/v1/tf/messages/sent/{message_id}/attachment')
    def sent_attachment(message_id:int,user=Depends(driver),db:Session=Depends(database_session)):
        message=sent_owned(db,user,message_id);file=db.get(Attachment,message.attachment_id) if message.attachment_id else None
        if not file:raise HTTPException(404,'Dateianhang nicht gefunden.')
        from urllib.parse import quote
        return Response(file.content,media_type=file.mime_type,headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(file.filename),'X-Content-Type-Options':'nosniff','Content-Security-Policy':"sandbox; default-src 'none'"})
    @router.post('/api/v1/tf/messages',status_code=201)
    async def send(payload:str=Form(max_length=50000),file:UploadFile|None=File(default=None),user=Depends(driver),db:Session=Depends(database_session)):
        try:data=MessageIn.model_validate_json(payload)
        except ValidationError as exc:raise HTTPException(422,'Bitte Empfänger, Betreff und Nachricht (maximal 1000 Zeichen) prüfen.') from exc
        selected=targets(db,data);attachment=None
        if file:
            try:content=await file.read(MAX_FILE+1)
            finally:await file.close()
            if not content or len(content)>MAX_FILE:raise HTTPException(413,'Dateianhang darf höchstens 10 MB groß sein.')
            filename=PurePosixPath((file.filename or 'Anhang').replace('\\','/')).name
            if not filename or len(filename)>200 or any(ord(c)<32 or ord(c)==127 for c in filename):raise HTTPException(422,'Ungültiger Dateiname.')
            mime='application/octet-stream'
            try:
                with Image.open(io.BytesIO(content)) as image:
                    image.verify()
                    if image.format in ('JPEG','PNG','GIF','WEBP'):mime=Image.MIME[image.format]
            except Exception:pass
            if content.startswith(b'%PDF-'):mime='application/pdf'
            attachment=Attachment(filename=filename,mime_type=mime,content=content);db.add(attachment);db.flush()
        profile=db.get(TfProfile,user.id)
        message=Message(sender_id=user.id,sender_name=identity(db,user),subject=data.subject,body=data.body,attachment_id=attachment.id if attachment else None);db.add(message);db.flush()
        for target in selected:db.add(Delivery(message_id=message.id,recipient_id=target))
        db.commit();return dict(id=message.id,sent=len(selected))
    @router.post('/api/v1/tf/messages/{message_id}/reply',status_code=201)
    async def reply(message_id:int,payload:str=Form(max_length=50000),file:UploadFile|None=File(default=None),user=Depends(driver),db:Session=Depends(database_session)):
        delivery,original=owned(db,user,message_id)
        try:data=MessageIn.model_validate_json(payload)
        except ValidationError as exc:raise HTTPException(422,'Bitte Betreff und Nachricht prüfen.') from exc
        data.recipients=[original.sender_id];data.all_tf=False
        return await send(data.model_dump_json(),file,user,db)
    @router.get('/api/v1/tf/messages/{message_id}')
    def detail(message_id:int,user=Depends(driver),db:Session=Depends(database_session)):
        delivery,message=owned(db,user,message_id)
        if delivery.read_at is None:delivery.read_at=now_utc();db.commit()
        return view(db,message,delivery,True)
    @router.put('/api/v1/tf/messages/{message_id}/read')
    def mark(message_id:int,data:ReadIn,user=Depends(driver),db:Session=Depends(database_session)):
        delivery,message=owned(db,user,message_id);delivery.read_at=now_utc() if data.read else None;db.commit();return {'read':data.read}
    @router.delete('/api/v1/tf/messages/{message_id}')
    def remove(message_id:int,user=Depends(driver),db:Session=Depends(database_session)):
        delivery,message=owned(db,user,message_id);delivery.deleted_at=now_utc();db.commit();return {'deleted':True}
    @router.post('/api/v1/tf/messages/{message_id}/forward',status_code=201)
    def forward(message_id:int,data:Recipients,user=Depends(driver),db:Session=Depends(database_session)):
        delivery,original=owned(db,user,message_id);selected=targets(db,data)
        profile=db.get(TfProfile,user.id)
        message=Message(sender_id=user.id,sender_name=identity(db,user),subject=('WG: '+original.subject)[:200],body=original.body,attachment_id=original.attachment_id);db.add(message);db.flush()
        for target in selected:db.add(Delivery(message_id=message.id,recipient_id=target))
        db.commit();return dict(id=message.id,sent=len(selected))
    @router.get('/api/v1/tf/messages/{message_id}/attachment')
    def attachment(message_id:int,user=Depends(driver),db:Session=Depends(database_session)):
        delivery,message=owned(db,user,message_id);file=db.get(Attachment,message.attachment_id) if message.attachment_id else None
        if not file:raise HTTPException(404,'Dateianhang nicht gefunden.')
        from urllib.parse import quote
        return Response(file.content,media_type=file.mime_type,headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(file.filename),'X-Content-Type-Options':'nosniff','Content-Security-Policy':"sandbox; default-src 'none'"})
    return router
