from ..localization import source as _text_source
import io
import base64
import binascii
import warnings
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import database_session
from ..models import ProfilePhoto, User
from .access import check_delegation

MAX_BYTES=5*1024*1024


def normalize(content):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as source:
                if source.format not in ('JPEG','PNG','WEBP') or getattr(source,'n_frames',1)!=1:
                    raise ValueError(_text_source('server_accounts_photos.text_bfabfb15a702'))
                if source.width*source.height>12_000_000:
                    raise ValueError(_text_source('server_accounts_photos.text_bef405a162b1'))
                source.load()
                image=ImageOps.exif_transpose(source).convert('RGBA')
                image.thumbnail((640,640))
                background=Image.new('RGB',image.size,'white');background.paste(image,mask=image.getchannel('A'))
                result=io.BytesIO();background.save(result,format='JPEG',quality=85)
                return result.getvalue()
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError,Image.DecompressionBombWarning,ValueError) as exc:
        raise HTTPException(422,str(exc) if isinstance(exc,ValueError) else _text_source('server_accounts_photos.text_2f8803f0996c')) from exc


def decode_photo(value):
    if value is None:return None
    try:content=base64.b64decode(value,validate=True)
    except (binascii.Error,ValueError) as exc:raise HTTPException(422,_text_source('server_accounts_photos.text_2976a3624c72')) from exc
    if len(content)>MAX_BYTES:raise HTTPException(413,_text_source('server_accounts_photos.text_511b9dcb0f51'))
    return normalize(content)


def save_photo(db,user_id,image):
    if image is not None:
        item=db.get(ProfilePhoto,user_id)
        if item is None:item=ProfilePhoto(user_id=user_id);db.add(item)
        item.image_data=image


def create_router(require_admin):
    router=APIRouter(dependencies=[Depends(require_admin)])

    def target(db,user_id,role):
        user=db.get(User,user_id)
        if not user or user.role!=role:raise HTTPException(404,_text_source('server_accounts_photos.text_d425970b74c9'))
        return user

    def get(db,user_id,role):
        target(db,user_id,role);photo=db.get(ProfilePhoto,user_id)
        if not photo:raise HTTPException(404,_text_source('server_accounts_photos.text_689fa5701f2b'))
        return Response(photo.image_data,media_type='image/jpeg',headers={
            'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})

    async def put(db,user_id,role,actor,file):
        user=target(db,user_id,role)
        if role=='staff' and user.id!=actor.id:check_delegation(db,actor,{},user)
        try:content=await file.read(MAX_BYTES+1)
        finally:await file.close()
        if len(content)>MAX_BYTES:raise HTTPException(413,_text_source('server_accounts_photos.text_511b9dcb0f51'))
        image=normalize(content)
        db.scalar(select(User).where(User.id==user_id).with_for_update())
        photo=db.get(ProfilePhoto,user_id)
        if not photo:photo=ProfilePhoto(user_id=user_id);db.add(photo)
        photo.image_data=image;db.commit()
        return {'has_photo':True}

    def remove(db,user_id,role,actor):
        user=target(db,user_id,role)
        if role=='staff' and user.id!=actor.id:check_delegation(db,actor,{},user)
        db.scalar(select(User).where(User.id==user_id).with_for_update())
        photo=db.get(ProfilePhoto,user_id)
        if photo:db.delete(photo);db.commit()
        return {'has_photo':False}

    @router.get('/api/v1/admin/tf/{user_id}/photo')
    def tf_photo(user_id:int,db:Session=Depends(database_session)):return get(db,user_id,'tf')
    @router.post('/api/v1/admin/tf/{user_id}/photo')
    async def tf_put(user_id:int,file:UploadFile=File(...),actor:User=Depends(require_admin),db:Session=Depends(database_session)):
        return await put(db,user_id,'tf',actor,file)
    @router.delete('/api/v1/admin/tf/{user_id}/photo')
    def tf_delete(user_id:int,actor:User=Depends(require_admin),db:Session=Depends(database_session)):return remove(db,user_id,'tf',actor)
    @router.get('/api/v1/admin/staff/{user_id}/photo')
    def staff_photo(user_id:int,db:Session=Depends(database_session)):return get(db,user_id,'staff')
    @router.post('/api/v1/admin/staff/{user_id}/photo')
    async def staff_put(user_id:int,file:UploadFile=File(...),actor:User=Depends(require_admin),db:Session=Depends(database_session)):
        return await put(db,user_id,'staff',actor,file)
    @router.delete('/api/v1/admin/staff/{user_id}/photo')
    def staff_delete(user_id:int,actor:User=Depends(require_admin),db:Session=Depends(database_session)):return remove(db,user_id,'staff',actor)
    return router
