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
from .models import User,TfProfile,TfMessage as Message,TfMessageDelivery as Delivery,TfMessageAttachment as Attachment,now_utc
from .security import account_active
from .tf_portal import driver_dependency

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
def recipients(db):return [(u,p) for u,p in db.execute(select(User,TfProfile).join(TfProfile,User.id==TfProfile.user_id).where(User.role=='tf',User.active==True).order_by(TfProfile.last_name,TfProfile.first_name,User.id)) if account_active(db,u)]
def targets(db,data):
    active={u.id for u,p in recipients(db)};selected=active if data.all_tf else set(data.recipients)
    if not selected:raise HTTPException(422,'Bitte mindestens einen TF auswählen.')
    if not selected<=active:raise HTTPException(422,'Ein ausgewählter TF ist nicht mehr verfügbar. Bitte die Empfängerliste aktualisieren.')
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

def create_router(require_account):
    router=APIRouter();driver=driver_dependency(require_account)
    @router.get('/tf/messages.js')
    def script():return FileResponse(Path(__file__).parent/'static'/'tf-messages.js',media_type='text/javascript',headers={'Cache-Control':'no-cache'})
    @router.get('/api/v1/tf/messages/recipients')
    def choices(user=Depends(driver),db:Session=Depends(database_session)):return [dict(id=u.id,name=name(p)) for u,p in recipients(db)]
    @router.get('/api/v1/tf/messages/unread')
    def unread(user=Depends(driver),db:Session=Depends(database_session)):
        return dict(count=db.scalar(select(func.count()).select_from(Delivery).join(Message,Message.id==Delivery.message_id).where(Delivery.recipient_id==user.id,Message.sender_id!=user.id,Delivery.read_at.is_(None),Delivery.deleted_at.is_(None))))
    @router.get('/api/v1/tf/messages')
    def listing(offset:int=Query(default=0,ge=0),limit:int=Query(default=50,ge=1,le=100),user=Depends(driver),db:Session=Depends(database_session)):
        query=select(Delivery,Message).join(Message,Message.id==Delivery.message_id).where(Delivery.recipient_id==user.id,Delivery.deleted_at.is_(None))
        total=db.scalar(select(func.count()).select_from(query.subquery()))
        rows=db.execute(query.order_by(Message.created_at.desc(),Message.id.desc()).offset(offset).limit(limit)).all()
        return dict(total=total,messages=[view(db,m,d) for d,m in rows])
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
        message=Message(sender_id=user.id,sender_name=name(profile),subject=data.subject,body=data.body,attachment_id=attachment.id if attachment else None);db.add(message);db.flush()
        for target in selected:db.add(Delivery(message_id=message.id,recipient_id=target))
        db.commit();return dict(id=message.id,sent=len(selected))
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
        message=Message(sender_id=user.id,sender_name=name(profile),subject=('WG: '+original.subject)[:200],body=original.body,attachment_id=original.attachment_id);db.add(message);db.flush()
        for target in selected:db.add(Delivery(message_id=message.id,recipient_id=target))
        db.commit();return dict(id=message.id,sent=len(selected))
    @router.get('/api/v1/tf/messages/{message_id}/attachment')
    def attachment(message_id:int,user=Depends(driver),db:Session=Depends(database_session)):
        delivery,message=owned(db,user,message_id);file=db.get(Attachment,message.attachment_id) if message.attachment_id else None
        if not file:raise HTTPException(404,'Dateianhang nicht gefunden.')
        from urllib.parse import quote
        return Response(file.content,media_type=file.mime_type,headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(file.filename),'X-Content-Type-Options':'nosniff','Content-Security-Policy':"sandbox; default-src 'none'"})
    return router
