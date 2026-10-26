import re
import hashlib
import mimetypes
import os
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter,Depends,HTTPException,UploadFile,File,Form,Query
from fastapi.responses import FileResponse,Response,StreamingResponse,JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..accounts.access import ready
from ..db import database_session
from ..models import User,DocumentFile
from .storage import MAX_FILE,tree,safe_path,clean_name,write_atomic


class DocumentUploadLimit:
    """Bound multipart data before Starlette can spool an oversized upload to disk."""
    def __init__(self,app):self.app=app

    async def __call__(self,scope,receive,send):
        path=scope.get('path','')
        station_plan=scope.get('method')=='PUT' and re.fullmatch(r'/api/v1/tf/stations/[^/]+/plan',path)
        draft_receipt=scope.get('method')=='PUT' and re.fullmatch(r'/api/v1/tf/work-report-drafts/[^/]+/files/[^/]+',path)
        if scope['type']!='http' or (path!='/api/v1/documents/upload' and not station_plan and not draft_receipt and not (scope.get('method')=='POST' and (path=='/api/v1/tf/messages' or (path.startswith('/api/v1/tf/messages/') and path.endswith('/reply'))))):
            return await self.app(scope,receive,send)
        limit=MAX_FILE+65536;headers=dict(scope.get('headers',[]));chunks=[];total=0
        async def reject():
            from ..i18n import translate,language
            lang=language(headers.get(b'accept-language',b'de').decode('latin1'))
            await JSONResponse({'detail':translate('Dokument darf höchstens 10 MB groß sein.',lang)},status_code=413)(scope,receive,send)
        try:declared=int(headers.get(b'content-length',b'0'))
        except ValueError:declared=0
        if declared>limit:return await reject()
        while True:
            message=await receive()
            if message['type']=='http.disconnect':return
            chunk=message.get('body',b'');total+=len(chunk)
            if total>limit:return await reject()
            chunks.append(chunk)
            if not message.get('more_body',False):break
        replayed=False
        async def replay():
            nonlocal replayed
            if not replayed:
                replayed=True
                return {'type':'http.request','body':b''.join(chunks),'more_body':False}
            return await receive()
        await self.app(scope,replay,send)


def create_router(require_account):
    router=APIRouter()
    def owner(user:User=Depends(require_account),db:Session=Depends(database_session)):
        ready(db,user);return user

    @router.get('/documents')
    def page():return FileResponse(Path(__file__).parent.parent/'static'/'documents.html')

    @router.get('/documents.js')
    def script():return FileResponse(Path(__file__).parent.parent/'static'/'documents.js',media_type='text/javascript',headers={'Cache-Control':'no-cache'})

    @router.get('/documents.css')
    def css():return FileResponse(Path(__file__).parent.parent/'static'/'documents.css',media_type='text/css')

    @router.get('/api/v1/documents/tree')
    def listing(q:str=Query(default='',max_length=200),user:User=Depends(owner),db:Session=Depends(database_session)):
        return tree(db,user,q)

    @router.get('/api/v1/documents/download')
    def download(path:str,user:User=Depends(owner)):
        file=safe_path(user,path)
        fd=os.open(file,os.O_RDONLY|os.O_NOFOLLOW)
        def chunks():
            with os.fdopen(fd,'rb') as stream:
                while data:=stream.read(65536):yield data
        return StreamingResponse(chunks(),media_type='application/octet-stream',headers={
            'Content-Disposition':"attachment; filename*=UTF-8''"+quote(file.name,safe=''),
            'X-Content-Type-Options':'nosniff','Cache-Control':'private, no-store'})

    @router.post('/api/v1/documents/upload',status_code=201)
    async def upload(folder:str=Form(...),file:UploadFile=File(...),user:User=Depends(owner),db:Session=Depends(database_session)):
        try:content=await file.read(MAX_FILE+1)
        finally:await file.close()
        if not content or len(content)>MAX_FILE:raise HTTPException(413,'Dokument darf höchstens 10 MB groß sein.')
        name=clean_name(file.filename)
        db.scalar(select(User).where(User.id==user.id).with_for_update())
        parent=safe_path(user,folder,directory=True);path=parent/name
        if path.exists() or path.is_symlink():
            name=Path(name).stem+'-'+uuid4().hex[:12]+Path(name).suffix;path=parent/name
        relative=folder+'/'+name
        write_atomic(path,content)
        row=DocumentFile(owner_id=user.id,uploader_id=user.id,relative_path=relative,display_name=name,byte_size=len(content),sha256=hashlib.sha256(content).hexdigest())
        db.add(row)
        try:db.commit()
        except Exception:
            db.rollback();path.unlink(missing_ok=True);raise
        return dict(path=relative,name=name)

    @router.delete('/api/v1/documents/file')
    def delete(path:str,user:User=Depends(owner),db:Session=Depends(database_session)):
        db.scalar(select(User).where(User.id==user.id).with_for_update())
        row=db.scalar(select(DocumentFile).where(DocumentFile.owner_id==user.id,DocumentFile.relative_path==path))
        if not row or row.uploader_id!=user.id or row.source_key:
            raise HTTPException(403,'Nur selbst hochgeladene Dokumente dürfen gelöscht werden.')
        target=safe_path(user,path);temporary=target.with_name('.delete-'+uuid4().hex)
        target.rename(temporary);db.delete(row)
        try:db.commit()
        except Exception:
            db.rollback();temporary.rename(target);raise
        temporary.unlink()
        return {'deleted':True}
    return router
