"""Private, versioned draft backup; no work entries, PDFs or email before final submission."""
import json
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,UploadFile,File,Header
from fastapi.responses import Response
from pydantic import BaseModel,Field
from sqlalchemy import select,delete
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from ..db import database_session
from ..models import DutyReportDraft as Draft,DutyReportDraftFile as DraftFile,DutyReport,DutyReceipt,User,now_utc
from ..tf_portal import driver_dependency
from .schemas import DraftReportIn
from .receipts import MAX_FILE,validate_receipt,recipient

class DraftInput(BaseModel):
    expected_revision:int=Field(ge=0)
    report:DraftReportIn
    receipt_keys:list[UUID]=Field(default_factory=list,max_length=20)

def find(db,user,client_id):
    return db.scalar(select(Draft).where(Draft.owner_id==user.id,Draft.client_id==str(client_id)))
def deleted(row):return bool(row and json.loads(row.payload_json).get('_deleted'))
def lock_owner(db,user):db.scalar(select(User).where(User.id==user.id).with_for_update())
def draft_files(db,row):
    keys=json.loads(row.receipt_keys_json)
    return list(db.scalars(select(DraftFile).where(DraftFile.draft_id==row.id,DraftFile.file_key.in_(keys)))) if keys else []
def view(db,row):
    return dict(client_id=row.client_id,report=json.loads(row.payload_json),revision=row.revision,updated_at=row.updated_at.isoformat(),receipt_keys=json.loads(row.receipt_keys_json),files=[dict(key=f.file_key,name=f.filename,mime_type=f.mime_type) for f in draft_files(db,row)])
def before_finalize(db,user,client_id,revision):
    lock_owner(db,user);row=find(db,user,client_id)
    if deleted(row):raise HTTPException(409,'Dieser Entwurf wurde gelöscht.')
    if row and not row.finalized_report_id:
        if revision!=row.revision:raise HTTPException(409,'Der Entwurf wurde auf einem anderen Gerät geändert. Bitte den Serverstand laden.')
        if len(draft_files(db,row))!=len(json.loads(row.receipt_keys_json)):raise HTTPException(409,'Nicht alle Entwurfsbelege wurden gesichert. Bitte erneut sichern.')
    return row

def finalize_files(db,row,report):
    if not row:return []
    ids=[]
    for f in draft_files(db,row):
        receipt=db.scalar(select(DutyReceipt).where(DutyReceipt.report_id==report.id,DutyReceipt.content_hash==f.content_hash))
        if not receipt:
            receipt=DutyReceipt(report_id=report.id,filename=f.filename,mime_type=f.mime_type,content_hash=f.content_hash,content=f.content,recipient_email=recipient());db.add(receipt);db.flush()
        if receipt.status!='sent':ids.append(receipt.id)
    row.finalized_report_id=report.id;row.updated_at=now_utc()
    return ids

def create_router(require_account):
    router=APIRouter(prefix='/api/v1/tf/work-report-drafts');driver=driver_dependency(require_account)
    @router.get('')
    def listing(user=Depends(driver),db:Session=Depends(database_session)):
        rows=list(db.scalars(select(Draft).where(Draft.owner_id==user.id).order_by(Draft.updated_at.desc())))
        return dict(drafts=[view(db,r) for r in rows if not r.finalized_report_id and not deleted(r)],finalized=[dict(client_id=r.client_id,report_id=r.finalized_report_id) for r in rows if r.finalized_report_id])
    @router.get('/{client_id}')
    def detail(client_id:UUID,user=Depends(driver),db:Session=Depends(database_session)):
        row=find(db,user,client_id)
        if not row or row.finalized_report_id or deleted(row):raise HTTPException(404,'Entwurf nicht gefunden.')
        return view(db,row)
    @router.delete('/{client_id}')
    def remove(client_id:UUID,user=Depends(driver),db:Session=Depends(database_session)):
        lock_owner(db,user)
        if db.scalar(select(DutyReport.id).where(DutyReport.tf_user_id==user.id,DutyReport.client_id==str(client_id))):raise HTTPException(409,'Bereits synchronisierte Arbeitsberichte können hier nicht gelöscht werden.')
        row=find(db,user,client_id)
        if row:
            if row.finalized_report_id:raise HTTPException(409,'Arbeitsbericht bereits synchronisiert.')
            db.execute(delete(DraftFile).where(DraftFile.draft_id==row.id));row.payload_json=json.dumps({'_deleted':True});row.receipt_keys_json='[]';row.revision+=1;row.updated_at=now_utc();db.commit()
        return {'ok':True}
    @router.put('/{client_id}')
    def save(client_id:UUID,data:DraftInput,user=Depends(driver),db:Session=Depends(database_session)):
        if client_id!=data.report.client_id:raise HTTPException(422,'Entwurfs-ID stimmt nicht überein.')
        payload=data.report.model_dump_json()
        if len(payload.encode('utf-8'))>60000:raise HTTPException(422,'Arbeitsbericht enthält zu viele Zugfahrtdaten.')
        lock_owner(db,user);row=find(db,user,client_id)
        if db.scalar(select(DutyReport.id).where(DutyReport.tf_user_id==user.id,DutyReport.client_id==str(client_id))):raise HTTPException(409,'Dieser Arbeitsbericht wurde bereits abgeschlossen. Bitte die Monatsliste aktualisieren.')
        if deleted(row):raise HTTPException(409,'Dieser Entwurf wurde gelöscht. Bitte einen neuen Arbeitsbericht beginnen.')
        if (row.revision if row else 0)!=data.expected_revision:raise HTTPException(409,'Der Entwurf wurde auf einem anderen Gerät geändert. Bitte den Serverstand laden.')
        keys=list(dict.fromkeys(str(k) for k in data.receipt_keys))
        if not row:row=Draft(owner_id=user.id,client_id=str(client_id),revision=0);db.add(row)
        row.payload_json=payload;row.receipt_keys_json=json.dumps(keys);row.revision+=1;row.updated_at=now_utc()
        try:db.commit()
        except IntegrityError as exc:
            db.rollback();raise HTTPException(409,'Der Entwurf wurde gleichzeitig auf einem anderen Gerät angelegt. Bitte aktualisieren.') from exc
        return view(db,row)
    @router.put('/{client_id}/files/{file_key}')
    async def upload(client_id:UUID,file_key:UUID,file:UploadFile=File(...),user=Depends(driver),db:Session=Depends(database_session)):
        try:content=await file.read(MAX_FILE+1)
        finally:await file.close()
        try:name,mime,digest=validate_receipt(file.filename,content)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        lock_owner(db,user);row=find(db,user,client_id)
        if not row or row.finalized_report_id or deleted(row):raise HTTPException(404,'Entwurf nicht gefunden.')
        if str(file_key) not in json.loads(row.receipt_keys_json):raise HTTPException(409,'Der Beleg gehört nicht mehr zum aktuellen Entwurf.')
        existing=db.scalar(select(DraftFile).where(DraftFile.draft_id==row.id,DraftFile.file_key==str(file_key)))
        if existing and existing.content_hash!=digest:raise HTTPException(409,'Beleg-ID ist bereits mit anderen Daten belegt.')
        if not existing:db.add(DraftFile(draft_id=row.id,file_key=str(file_key),filename=name,mime_type=mime,content_hash=digest,content=content))
        db.commit();return {'ok':True}
    @router.get('/{client_id}/files/{file_key}')
    def download(client_id:UUID,file_key:UUID,user=Depends(driver),db:Session=Depends(database_session)):
        row=find(db,user,client_id)
        if not row:raise HTTPException(404,'Entwurf nicht gefunden.')
        file=next((f for f in draft_files(db,row) if f.file_key==str(file_key)),None)
        if not file:raise HTTPException(404,'Beleg nicht gefunden.')
        return Response(file.content,media_type=file.mime_type,headers={'X-Content-Type-Options':'nosniff'})
    return router
