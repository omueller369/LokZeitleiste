"""TF landing pages and read-only access to the driver's own personnel plan."""
from pathlib import Path as FilePath
from fastapi import APIRouter, Cookie, Depends, HTTPException, Path
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session
from .db import database_session
from .models import User, TfProfile
from .security import user_from_token
from .accounts.access import password_required
from .planning.service import get_month

STATIC=FilePath(__file__).parent/'static'


def driver_dependency(require_account):
    def require_driver(user:User=Depends(require_account),db:Session=Depends(database_session)):
        if user.role!='tf':raise HTTPException(403,'TF Portal ist nur für Triebfahrzeugführer verfügbar.')
        if password_required(db,user):raise HTTPException(403,'Bitte zuerst Ihr Initialpasswort ändern.')
        return user
    return require_driver


def create_router(require_account):
    router=APIRouter()

    require_driver=driver_dependency(require_account)

    @router.get('/tf')
    @router.get('/tf/arbeitsbericht')
    @router.get('/tf/lokuebergabebuch')
    @router.get('/tf/leuna-uebergabeprotokoll')
    @router.get('/tf/arbeitsplan')
    @router.get('/tf/bahnhoefe')
    def page(admin_session:str|None=Cookie(default=None),db:Session=Depends(database_session)):
        user=user_from_token(db,admin_session)
        if not user or password_required(db,user):return RedirectResponse('/account',status_code=303)
        if user.role!='tf':raise HTTPException(403,'TF Portal ist nur für Triebfahrzeugführer verfügbar.')
        return FileResponse(STATIC/'tf-portal.html')

    @router.get('/tf/portal.js')
    def script():return FileResponse(STATIC/'tf-portal.js',media_type='text/javascript')

    @router.get('/tf/portal.css')
    def styles():return FileResponse(STATIC/'tf-portal.css',media_type='text/css')

    @router.get('/api/v1/tf/portal')
    def identity(user:User=Depends(require_driver),db:Session=Depends(database_session)):
        profile=db.get(TfProfile,user.id)
        if not profile:raise HTTPException(404,'Tf nicht gefunden')
        return {'id':user.id,'username':user.username,'first_name':profile.first_name,'last_name':profile.last_name}

    @router.get('/api/v1/tf/portal/plan/{year}/{month}')
    def plan(year:int=Path(ge=2000,le=2100),month:int=Path(ge=1,le=12),
             user:User=Depends(require_driver),db:Session=Depends(database_session)):
        if not db.get(TfProfile,user.id):raise HTTPException(404,'Tf nicht gefunden')
        return get_month(db,user.id,year,month)

    return router
