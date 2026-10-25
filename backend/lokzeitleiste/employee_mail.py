"""Managed employee addresses and an encrypted outbox for the local mail provisioner."""
import base64
import json
import os
import re
import unicodedata
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, Field, TypeAdapter
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .db import database_session
from .default_order import ordered
from .models import EmailDomain, EmployeeEmail, MailboxProvision, MailboxAccount, MailboxSettings, User, TfProfile, StaffProfile
from .accounts.access import demand
from .mailbox import service
from .mailbox.api import MessageInput


def domain_name(value):
    value=value.strip().lower().rstrip('.')
    try:value=value.encode('idna').decode('ascii')
    except UnicodeError:raise HTTPException(422,'Ungültige Domain')
    if len(value)>253 or '.' not in value or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',p) for p in value.split('.')):
        raise HTTPException(422,'Ungültige Domain')
    return value


def domains(db):
    name=os.getenv('CTL_MAIL_DOMAIN','').strip()
    if name and not db.scalar(select(EmailDomain.id).limit(1)):
        db.add(EmailDomain(name=domain_name(name)));db.flush()
    return ordered(db,'email-domains',db.scalars(select(EmailDomain).order_by(EmailDomain.name)))


def local_name(first,last):
    text=(first+'.'+last).lower().replace('ä','ae').replace('ö','oe').replace('ü','ue').replace('ß','ss')
    text=unicodedata.normalize('NFKD',text).encode('ascii','ignore').decode()
    text=re.sub(r'[^a-z0-9.]+','',text);text=re.sub(r'\.+','.',text).strip('.')
    return text[:58] or 'mitarbeiter'


def address_taken(db,address,user_id=None):
    # Include historical profiles not yet migrated into the unique address registry.
    for cls,field,pk in ((EmployeeEmail,EmployeeEmail.address,EmployeeEmail.user_id),(TfProfile,TfProfile.email,TfProfile.user_id),(MailboxAccount,MailboxAccount.address,MailboxAccount.tf_user_id)):
        query=select(pk).where(field==address)
        if user_id is not None:query=query.where(pk!=user_id)
        if db.scalar(query) is not None:return True
    return False


def suggest(db,first,last,birth,domain,user_id=None):
    domain=domain_name(domain);stem=local_name(first,last);base=stem+'@'+domain
    if not address_taken(db,base,user_id):return base
    stem+=str(birth.year)[-2:] if birth else ''
    for number in range(1000):
        candidate=stem+(str(number) if number else '')+'@'+domain
        if not address_taken(db,candidate,user_id):return candidate
    raise HTTPException(409,'Keine freie E-Mail-Adresse gefunden.')


def save_email(db,user,address,password=None):
    address=str(TypeAdapter(EmailStr).validate_python(address)).lower()
    row=db.get(EmployeeEmail,user.id)
    if address_taken(db,address,user.id):raise HTTPException(409,'E-Mail-Adresse bereits vergeben. Bitte Vorschlag aktualisieren.')
    managed=address.rsplit('@',1)[1] in {d.name for d in domains(db)}
    if managed and not re.fullmatch(r'[a-z0-9][a-z0-9._+-]{0,63}',address.split('@')[0]):raise HTTPException(422,'Für lokale Postfächer nur Kleinbuchstaben, Zahlen, Punkt, Bindestrich, Unterstrich und Plus verwenden.')
    if row and row.managed and row.address!=address:
        raise HTTPException(409,'Ein bestehendes lokales Postfach kann nicht durch eine Profiländerung umbenannt werden.')
    if not row:row=EmployeeEmail(user_id=user.id);db.add(row)
    row.address=address;row.managed=managed
    if user.role=='tf':db.get(TfProfile,user.id).email=address
    if managed and password:
        if any(c in password for c in '\r\n\x00'):raise HTTPException(422,'Initialpasswort darf keine Steuerzeichen enthalten.')
        if not os.getenv('CTL_MAIL_PROVISIONING'):
            raise HTTPException(503,'Lokale Postfachanlage ist noch nicht eingerichtet. Setup aktualisieren.')
        encrypted=service.cipher().encrypt(password.encode()).decode()
        job=db.get(MailboxProvision,user.id)
        if not job:job=MailboxProvision(user_id=user.id);db.add(job)
        job.address=address;job.password_encrypted=encrypted;job.status='pending';job.error=''
        account=db.get(MailboxAccount,user.id)
        if not account:account=MailboxAccount(tf_user_id=user.id);db.add(account)
        account.address=account.username=address;account.password_encrypted=encrypted
        cfg=dict(provider='manual',auth_method='password',imap_host=os.getenv('MAILBOX_IMAP_HOST',''),imap_port=993,imap_security='ssl',smtp_host=os.getenv('MAILBOX_SMTP_HOST',''),smtp_port=465,smtp_security='ssl',smtp_username=address,sent_folder='Sent')
        settings=db.get(MailboxSettings,user.id)
        if not settings:settings=MailboxSettings(tf_user_id=user.id);db.add(settings)
        settings.config_json=json.dumps(cfg)
    return row


def employee_rows(db):
    result=[]
    for user in db.scalars(select(User).where(User.role.in_(('tf','staff')))):
        profile=db.get(TfProfile if user.role=='tf' else StaffProfile,user.id)
        row=db.get(EmployeeEmail,user.id);job=db.get(MailboxProvision,user.id)
        account=db.get(MailboxAccount,user.id)
        address=row.address if row else (profile.email or '' if user.role=='tf' and profile else '')
        status=job.status if job else 'ready' if account and account.address==address else 'external'
        result.append(dict(id=user.id,first_name=profile.first_name if profile else user.username,last_name=profile.last_name if profile else '',role='TF' if user.role=='tf' else 'Verwaltung',email=address,mailbox_status=status,own=user.id))
    return sorted(result,key=lambda r:(r['last_name'].casefold(),r['first_name'].casefold()))


class DomainInput(BaseModel):
    name:str=Field(min_length=3,max_length=253)


class ComposeInput(MessageInput):
    pass

def create_router(require_admin):
    router=APIRouter()
    @router.get('/api/v1/admin/email-domains',dependencies=[Depends(require_admin)])
    def list_domains(db:Session=Depends(database_session)):
        result=[dict(id=d.id,name=d.name) for d in domains(db)];db.commit();return result
    @router.post('/api/v1/admin/app-defaults/email-domains',status_code=201)
    def add(data:DomainInput,user=Depends(require_admin),db:Session=Depends(database_session)):
        demand(db,user,'app_defaults',3);row=EmailDomain(name=domain_name(data.name));db.add(row)
        try:db.commit()
        except IntegrityError:db.rollback();raise HTTPException(409,'Domain bereits vorhanden')
        return dict(id=row.id,name=row.name)
    @router.delete('/api/v1/admin/app-defaults/email-domains/{id}')
    def remove(id:int,user=Depends(require_admin),db:Session=Depends(database_session)):
        demand(db,user,'app_defaults',3);row=db.get(EmailDomain,id)
        if not row:raise HTTPException(404,'Domain nicht gefunden')
        if db.scalar(select(EmployeeEmail.user_id).where(EmployeeEmail.address.like('%@'+row.name)).limit(1)):raise HTTPException(409,'Domain wird bereits verwendet')
        db.delete(row);db.commit();return dict(ok=True)
    @router.get('/api/v1/admin/email-suggestion')
    def suggestion(first_name:str,last_name:str,birth_date:str,domain:str,user_id:int|None=None,user=Depends(require_admin),db:Session=Depends(database_session)):
        from datetime import date
        try:birth=date.fromisoformat(birth_date) if birth_date else None
        except ValueError:raise HTTPException(422,'Ungültiges Geburtsdatum')
        if domain not in {d.name for d in domains(db)}:raise HTTPException(422,'Domain nicht in der Liste')
        return dict(address=suggest(db,first_name,last_name,birth,domain,user_id))
    @router.get('/api/v1/admin/email/employees')
    def employees(user=Depends(require_admin),db:Session=Depends(database_session)):
        demand(db,user,'email',1);return employee_rows(db)
    @router.post('/api/v1/admin/email/employees/{user_id}/send')
    def send(user_id:int,data:ComposeInput,actor=Depends(require_admin),db:Session=Depends(database_session)):
        demand(db,actor,'email',2)
        account=db.get(MailboxAccount,user_id);job=db.get(MailboxProvision,user_id)
        address=db.get(EmployeeEmail,user_id)
        if account and address and account.address!=address.address:raise HTTPException(409,'Postfach und Mitarbeiteradresse stimmen nicht überein.')
        if not account or (job and job.status!='ready'):raise HTTPException(409,'Postfach ist noch nicht versandbereit oder extern nicht verbunden.')
        account._settings=db.get(MailboxSettings,user_id);account._db=db
        return service.send(account,data)
    @router.get('/employee-mail.js')
    def fields():return FileResponse(Path(__file__).parent/'static/employee-mail.js',media_type='text/javascript')
    return router
