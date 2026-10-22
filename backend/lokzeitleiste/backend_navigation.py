"""Account-owned navigation preferences; no module grant or target-user parameter."""
from pathlib import Path
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel,Field,ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .db import database_session
from .models import User,BackendMenuPreference

class MenuPreferenceInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    variant:Literal['sidebar','compact','sections']
    expected_revision:int=Field(ge=0)

def view(user,row):return dict(user_id=user.id,variant=row.variant if row else 'sidebar',revision=row.revision if row else 0)

def create_router(require_admin):
    router=APIRouter()
    @router.get('/admin/menu-preference.js')
    def script():return FileResponse(Path(__file__).parent/'static'/'menu-preference.js',media_type='text/javascript',headers={'Cache-Control':'no-cache'})
    @router.get('/api/v1/admin/menu-preference')
    def get(user=Depends(require_admin),db:Session=Depends(database_session)):
        return view(user,db.get(BackendMenuPreference,user.id))
    @router.put('/api/v1/admin/menu-preference')
    def save(data:MenuPreferenceInput,user=Depends(require_admin),db:Session=Depends(database_session)):
        db.scalar(select(User).where(User.id==user.id).with_for_update())
        row=db.scalar(select(BackendMenuPreference).where(BackendMenuPreference.user_id==user.id).with_for_update())
        if (row.revision if row else 0)!=data.expected_revision:raise HTTPException(409,'Menüeinstellung wurde geändert. Bitte neu laden.')
        if not row:row=BackendMenuPreference(user_id=user.id,variant=data.variant,revision=0);db.add(row)
        row.variant=data.variant;row.revision+=1
        try:db.commit()
        except IntegrityError as exc:
            db.rollback();raise HTTPException(409,'Menüeinstellung wurde geändert. Bitte neu laden.') from exc
        return view(user,row)
    return router
