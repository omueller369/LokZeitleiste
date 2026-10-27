"""Private TF signature capture; normalized transparent ink only."""
import io
from pathlib import Path
from fastapi import APIRouter,Depends,File,HTTPException,UploadFile
from fastapi.responses import FileResponse,Response
from PIL import Image,ImageChops,UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import database_session
from .models import UserSignature,User,now_utc
from .tf_portal import driver_dependency
MAX_BYTES=1024*1024

def normalize(content):
    try:
        with Image.open(io.BytesIO(content)) as source:
            if source.format!='PNG' or not 1<=source.width<=2000 or not 1<=source.height<=1000 or source.width*source.height>2000000:raise ValueError()
            source.load();image=source.convert('RGBA')
    except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError) as exc:
        raise HTTPException(422,'Bitte eine gültige PNG-Unterschrift mit maximal 2000 × 1000 Pixeln verwenden.') from exc
    alpha=ImageChops.multiply(image.getchannel('A'),ImageChops.invert(image.convert('L')))
    # Remove nearly invisible background pixels and encode black ink with alpha only.
    alpha=alpha.point(lambda p:0 if p<8 else p)
    bounds=alpha.getbbox()
    if not bounds:raise HTTPException(422,'Bitte zuerst eine Unterschrift zeichnen.')
    ink=Image.new('RGBA',image.size,(0,0,0,0));ink.putalpha(alpha);ink=ink.crop(bounds)
    output=io.BytesIO();ink.save(output,format='PNG',optimize=True);return output.getvalue()

def signature_for(db,user):
    row=db.get(UserSignature,user.id)
    return row.image_data if row else None

def create_router(require_account):
    router=APIRouter();driver=driver_dependency(require_account);static=Path(__file__).parent/'static'
    @router.get('/tf/signature.js')
    def script():return FileResponse(static/'tf-signature.js',media_type='text/javascript',headers={'Cache-Control':'no-cache'})
    @router.get('/tf/signature.css')
    def style():return FileResponse(static/'tf-signature.css',media_type='text/css',headers={'Cache-Control':'no-cache'})
    @router.get('/api/v1/tf/me/signature')
    def get(user=Depends(driver),db:Session=Depends(database_session)):
        content=signature_for(db,user)
        if not content:raise HTTPException(404,'Noch keine Unterschrift gespeichert.')
        return Response(content,media_type='image/png',headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})
    @router.put('/api/v1/tf/me/signature')
    async def save(file:UploadFile=File(...),user=Depends(driver),db:Session=Depends(database_session)):
        try:content=await file.read(MAX_BYTES+1)
        finally:await file.close()
        if len(content)>MAX_BYTES:raise HTTPException(413,'Unterschrift darf höchstens 1 MB groß sein.')
        content=normalize(content)
        db.scalar(select(User).where(User.id==user.id).with_for_update())
        row=db.get(UserSignature,user.id)
        if not row:row=UserSignature(user_id=user.id,image_data=content);db.add(row)
        row.image_data=content;row.updated_at=now_utc();db.commit()
        return Response(content,media_type='image/png',headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})
    return router
