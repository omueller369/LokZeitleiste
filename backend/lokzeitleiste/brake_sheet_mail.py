"""Explicit, account-owned brake-sheet mail composition and archived PDF snapshots."""
import json,os
from uuid import UUID,uuid4
from html import escape
from email.message import EmailMessage
from email.utils import formatdate,parseaddr
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import Response
from pydantic import BaseModel,EmailStr,Field,field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import database_session
from .models import BrakeSheetDraft,BrakeSheetDispatch,MailboxAccount,MailboxSettings,MailboxProvision,EmployeeEmail,User,now_utc
from .tf_portal import driver_dependency
from .signatures import signature_for
from .brake_sheets import Sheet,PreviewRequest,calculate
from .brake_sheet_image import render,render_pdf
from .documents.storage import generated
from .mailbox import service

TO='dispo@ctl-software.io-goerlitz.eu'
CC='oliver.mueller@ctl.eu'
BCC='omueller369@gmail.com'
class MailInput(BaseModel):
    to:list[EmailStr]=Field(min_length=1,max_length=20)
    cc:list[EmailStr]=Field(default_factory=list,max_length=30)
    subject:str=Field(min_length=1,max_length=300)
    body:str=Field(default='',max_length=10000)
    @field_validator('subject')
    @classmethod
    def header(cls,v):
        if '\r' in v or '\n' in v:raise ValueError('Ungültige Kopfzeile')
        return v
    bcc:list[EmailStr]=Field(default_factory=lambda:[BCC],max_length=30)

def mailbox(db,user):
    # Test-only routing for brake sheets; no TF access to administrator mail APIs.
    admins=list(db.scalars(select(User).where(User.role=='admin',User.active==True).order_by(User.id)))
    primary=next((a for a in admins if a.username=='admin'),None)
    candidates=[primary] if primary else admins
    configured=[(a,db.get(MailboxAccount,a.id)) for a in candidates if db.get(MailboxAccount,a.id)]
    if len(configured)==1:
        admin,account=configured[0];address=db.get(EmployeeEmail,admin.id);job=db.get(MailboxProvision,admin.id)
        sender=address.address if address else account.address
        return account,sender,bool(sender==account.address and (not job or job.status=='ready'))
    if configured:return None,'',False
    from .reports.mailer import smtp_configured
    sender=parseaddr(os.getenv('SMTP_FROM',''))[1]
    return None,sender,bool(sender and smtp_configured())

def message(row,data):
    msg=EmailMessage();msg['From']=row.sender;msg['To']=', '.join(str(a) for a in data.to)
    if data.cc:msg['Cc']=', '.join(str(a) for a in data.cc)
    msg['Subject']=data.subject;msg['Date']=formatdate(localtime=True);msg['Message-ID']=f'<brake-sheet-{row.id}@{row.sender.split("@")[-1]}>'
    msg.set_content(data.body)
    body=escape(data.body).replace('\n','<br>');cid='brake-sheet-preview-'+row.id+'@'+row.sender.split('@')[-1]
    msg.add_alternative('<html><body><p>'+body+'</p><img src="cid:'+cid+'" alt="Bremszettel" style="max-width:100%;height:auto"></body></html>',subtype='html')
    msg.get_payload()[-1].add_related(row.image_content,maintype='image',subtype='png',cid='<'+cid+'>',disposition='inline')
    msg.add_attachment(row.pdf_content,maintype='application',subtype='pdf',filename=row.filename)
    return msg

def create_router(require_account):
    router=APIRouter();driver=driver_dependency(require_account)
    def owned(db,user,id):
        row=db.scalar(select(BrakeSheetDispatch).where(BrakeSheetDispatch.id==str(id),BrakeSheetDispatch.owner_id==user.id).with_for_update())
        if not row:raise HTTPException(404,'Bremszettel nicht gefunden.')
        return row
    @router.post('/api/v1/tf/brake-sheets/{id}/mail')
    def prepare(id:UUID,data:PreviewRequest,user=Depends(driver),db:Session=Depends(database_session)):
        draft=db.scalar(select(BrakeSheetDraft).where(BrakeSheetDraft.id==str(id),BrakeSheetDraft.owner_id==user.id).with_for_update())
        if not draft:raise HTTPException(404,'Bremszettel nicht gefunden.')
        if draft.revision!=data.expected_revision:raise HTTPException(409,'Bremszettel wurde auf einem anderen Gerät geändert. Bitte neu laden.')
        sheet=Sheet.model_validate_json(draft.payload_json);result=calculate(db,sheet)
        if result['preview_missing']:raise HTTPException(422,'Bitte Pflichtangaben ergänzen: '+', '.join(result['preview_missing']))
        try:
            png=render(sheet,result,draft.created_at,draft.created_by_name,signature=signature_for(db,user))
            pdf=render_pdf(sheet,result,draft.created_at,draft.created_by_name,signature=signature_for(db,user))
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        number=sheet.train_numbers[0];day=sheet.departure_date
        filename=f'Bremszettel-{number}-{day.isoformat()}.PDF'
        path=f'Dokumente/Zugfahrten/{day:%Y/%m/%d}/{number}/{filename}'
        document=generated(db,user,path,pdf,'brake-sheet:'+draft.id);db.flush()
        account,sender,ready=mailbox(db,user)
        subject=f'Bremszettel {number} – {day:%d.%m.%Y}'
        mail=dict(to=[TO],cc=[CC],bcc=[BCC],subject=subject,body=f'Anbei der Bremszettel für Zug {number} vom {day:%d.%m.%Y}.')
        row=BrakeSheetDispatch(id=str(uuid4()),owner_id=user.id,draft_id=draft.id,draft_revision=draft.revision,document_id=document.id,filename=filename,sender=sender,mail_json=json.dumps(mail),pdf_content=pdf,image_content=png,status='ready')
        db.add(row);db.commit()
        root='/api/v1/tf/brake-sheet-mail/'+row.id
        return dict(id=row.id,sender=sender,mail_ready=ready,mail_notice='' if ready else 'Administratorpostfach ist noch nicht versandbereit. Die PDF wurde gespeichert.',filename=filename,document_path=document.relative_path,pdf_url=root+'/pdf',image_url=root+'/image',**mail)
    @router.get('/api/v1/tf/brake-sheet-mail/{id}/image')
    def image(id:UUID,user=Depends(driver),db:Session=Depends(database_session)):
        return Response(owned(db,user,id).image_content,media_type='image/png',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
    @router.get('/api/v1/tf/brake-sheet-mail/{id}/pdf')
    def pdf(id:UUID,user=Depends(driver),db:Session=Depends(database_session)):
        row=owned(db,user,id)
        return Response(row.pdf_content,media_type='application/pdf',headers={'Cache-Control':'no-store','Content-Disposition':'attachment; filename="'+row.filename+'"','X-Content-Type-Options':'nosniff'})
    @router.post('/api/v1/tf/brake-sheet-mail/{id}/send')
    def send(id:UUID,data:MailInput,user=Depends(driver),db:Session=Depends(database_session)):
        row=owned(db,user,id)
        if row.status=='sent':return dict(sent=True,warning=row.warning,already_sent=True)
        if row.status!='ready':raise HTTPException(409,'Versand wurde bereits gestartet. Vor erneutem Senden den Postausgang prüfen.')
        account,sender,ready=mailbox(db,user)
        if not ready or sender!=row.sender:raise HTTPException(409,'Administratorpostfach ist noch nicht versandbereit. Die PDF wurde gespeichert.')
        if BCC not in [str(a) for a in data.bcc]:data.bcc.append(BCC)
        if account:account._settings=db.get(MailboxSettings,account.tf_user_id);account._db=db
        msg=message(row,data)
        if len(msg.as_bytes())>service.MAX_MESSAGE:raise HTTPException(413,'Nachricht inklusive Anhängen darf höchstens 10 MiB groß sein.')
        row.mail_json=data.model_dump_json();row.status='sending';db.commit()
        try:
            if account:result=service.send_prepared(account,msg,data)
            else:
                from .reports.mailer import _send_message
                _send_message(msg,recipients=[str(a) for a in [*data.to,*data.cc,*data.bcc]])
                result=dict(sent=True,warning='')
        except HTTPException:
            row.status='unknown';db.commit();raise
        except Exception as exc:
            row.status='unknown';db.commit();raise HTTPException(502,'E-Mail-Versand fehlgeschlagen. Postausgang vor erneutem Senden prüfen.') from exc
        row.status='sent';row.sent_at=now_utc();row.warning=result.get('warning','');db.commit()
        return result
    return router
