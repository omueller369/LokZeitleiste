"""Private TF signature capture; normalized transparent ink only."""
import io,json
from pathlib import Path
from fastapi import APIRouter,Depends,File,Form,HTTPException,UploadFile
from fastapi.responses import FileResponse,Response
from PIL import Image,ImageChops,UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import database_session
from .models import UserSignature,UserSignaturePlacement,TfProfile,User,now_utc
from .tf_portal import driver_dependency
MAX_BYTES=1024*1024
VIEWPORT=(640,1680,940,1830)
CAPTURE_MODE="field40-v1"

def normalize(content,with_position=False):
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
    output=io.BytesIO();ink.save(output,format='PNG',optimize=True)
    if with_position:
        if image.size!=(1000,500):raise HTTPException(422,'Zeichenfläche wurde geändert. Bitte das Unterschriftfenster neu öffnen.')
        x0,y0,x1,y1=VIEWPORT;w,h=image.size;l,t,r,b=bounds
        return output.getvalue(),[x0+l/w*(x1-x0),y0+t/h*(y1-y0),(r-l)/w*(x1-x0),(b-t)/h*(y1-y0)]
    return output.getvalue()

def signature_for(db,user):
    row=db.get(UserSignature,user.id)
    return row.image_data if row else None

def signature_position_for(db,user):
    row=db.get(UserSignaturePlacement,user.id)
    return json.loads(row.geometry_json) if row else None

def background(name):
    from .brake_sheet_image import TEMPLATE,font
    from PIL import ImageDraw
    with Image.open(TEMPLATE) as source:image=source.convert('RGB')
    sx=image.width/1335;sy=image.height/1888;draw=ImageDraw.Draw(image)
    # Show the name ending at the same anchor used for placed signatures in field 40.
    logical=14
    while logical>6 and draw.textlength(name,font=font(round(logical*sy)))>196*sx-6:logical-=1
    f=font(round(logical*sy));tail=name[-3:]
    height=round(1771*sy)-round(1751*sy)-4;step=round(logical*sy*1.22)
    top=round(1751*sy)+(height-step)//2+2
    draw.text((round(698*sx)-3-draw.textlength(tail,font=f),top),tail,font=f,fill='black',anchor='lt')
    crop=image.crop(tuple(round(v*scale) for v,scale in zip(VIEWPORT,[sx,sy,sx,sy])))
    crop=crop.resize((1000,500),Image.Resampling.LANCZOS)
    output=io.BytesIO();crop.save(output,format='PNG');return output.getvalue()

def create_router(require_account):
    router=APIRouter();driver=driver_dependency(require_account);static=Path(__file__).parent/'static'
    @router.get('/tf/signature.js')
    def script():return FileResponse(static/'tf-signature.js',media_type='text/javascript',headers={'Cache-Control':'no-cache'})
    @router.get('/tf/signature.css')
    def style():return FileResponse(static/'tf-signature.css',media_type='text/css',headers={'Cache-Control':'no-cache'})
    @router.get('/api/v1/tf/me/signature/background')
    def guide(user=Depends(driver),db:Session=Depends(database_session)):
        profile=db.get(TfProfile,user.id)
        if not profile:raise HTTPException(404,'TF nicht gefunden.')
        return Response(background((profile.first_name+' '+profile.last_name).strip()),media_type='image/png',headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})
    @router.get('/api/v1/tf/me/signature')
    def get(user=Depends(driver),db:Session=Depends(database_session)):
        content=signature_for(db,user)
        if not content:raise HTTPException(404,'Noch keine Unterschrift gespeichert.')
        return Response(content,media_type='image/png',headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})
    @router.put('/api/v1/tf/me/signature')
    async def save(file:UploadFile=File(...),capture_mode:str|None=Form(default=None),user=Depends(driver),db:Session=Depends(database_session)):
        try:content=await file.read(MAX_BYTES+1)
        finally:await file.close()
        if len(content)>MAX_BYTES:raise HTTPException(413,'Unterschrift darf höchstens 1 MB groß sein.')
        if capture_mode not in (None,CAPTURE_MODE):raise HTTPException(422,'Unbekannte Zeichenfläche. Bitte neu laden.')
        geometry=None
        if capture_mode:content,geometry=normalize(content,with_position=True)
        else:content=normalize(content)
        db.scalar(select(User).where(User.id==user.id).with_for_update())
        row=db.get(UserSignature,user.id)
        if not row:row=UserSignature(user_id=user.id,image_data=content);db.add(row)
        row.image_data=content;row.updated_at=now_utc();db.flush()
        placement=db.get(UserSignaturePlacement,user.id)
        if geometry:
            if not placement:placement=UserSignaturePlacement(user_id=user.id);db.add(placement)
            placement.geometry_json=json.dumps(geometry)
        elif placement:db.delete(placement)
        db.commit()
        return Response(content,media_type='image/png',headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})
    return router
