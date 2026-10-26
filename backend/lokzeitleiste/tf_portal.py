"""TF landing pages and read-only access to the driver's own personnel plan."""
from pathlib import Path as FilePath
from fastapi import APIRouter, Cookie, Depends, HTTPException, Path, Request
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, Response
from sqlalchemy.orm import Session
from .db import database_session
from .models import User, TfProfile
from .security import user_from_token
from .accounts.access import password_required
from .planning.service import get_month,get_year

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
    @router.get('/tf/leuna-uebergabeprotokoll')
    @router.get('/tf/arbeitsplan')
    @router.get('/tf/bahnhoefe')
    def page(tf_session:str|None=Cookie(default=None),admin_session:str|None=Cookie(default=None),db:Session=Depends(database_session)):
        user=user_from_token(db,tf_session or admin_session)
        if not user or password_required(db,user):return RedirectResponse('/account?area=tf',status_code=303)
        if user.role!='tf':return RedirectResponse('/account?area=tf',status_code=303)
        return FileResponse(STATIC/'tf-portal.html',headers={'Cache-Control':'no-store'})

    @router.get('/tf/loco-handover')
    @router.get('/tf/lokuebergabebuch')
    def handover_page(tf_session:str|None=Cookie(default=None),admin_session:str|None=Cookie(default=None),db:Session=Depends(database_session)):
        user=user_from_token(db,tf_session or admin_session)
        if not user or password_required(db,user):return RedirectResponse('/account?area=tf',status_code=303)
        if user.role!='tf':return RedirectResponse('/account?area=tf',status_code=303)
        html=(STATIC/'loco-handover.html').read_text().replace('href="/admin/start">Startseite', 'href="/tf">TF Portal')
        return HTMLResponse(html,headers={'Cache-Control':'no-store'})

    @router.get('/tf/return.js')
    def return_script():return FileResponse(STATIC/'tf-return.js',media_type='text/javascript',headers={'Cache-Control':'no-cache'})

    @router.get('/tf/portal.js')
    def script():return FileResponse(STATIC/'tf-portal.js',media_type='text/javascript',headers={'Cache-Control':'no-store'})

    @router.get('/tf/portal.css')
    def styles():return FileResponse(STATIC/'tf-portal.css',media_type='text/css')

    @router.get('/api/v1/tf/portal')
    def identity(user:User=Depends(require_driver),db:Session=Depends(database_session)):
        profile=db.get(TfProfile,user.id)
        if not profile:raise HTTPException(404,'Tf nicht gefunden')
        return {'id':user.id,'username':user.username,'first_name':profile.first_name,'last_name':profile.last_name}

    @router.get('/tf/me')
    @router.get('/tf/nachrichten')
    def personal_page(request:Request,tf_session:str|None=Cookie(default=None),admin_session:str|None=Cookie(default=None),db:Session=Depends(database_session)):
        user=user_from_token(db,tf_session or admin_session)
        if not user or user.role!='tf' or password_required(db,user):return RedirectResponse('/account?area=tf',status_code=303)
        return FileResponse(STATIC/('tf-messages.html' if request.url.path.endswith('/nachrichten') else 'tf-profile.html'),headers={'Cache-Control':'no-store'})

    @router.get('/tf/shell.js')
    def shell_script():return FileResponse(STATIC/'tf-shell.js',media_type='text/javascript',headers={'Cache-Control':'no-cache'})
    @router.get('/tf/shell.css')
    def shell_css():return FileResponse(STATIC/'tf-shell.css',media_type='text/css',headers={'Cache-Control':'no-cache'})
    @router.get('/tf/profile.js')
    def profile_script():return FileResponse(STATIC/'tf-profile.js',media_type='text/javascript',headers={'Cache-Control':'no-cache'})
    @router.get('/tf/ctl-logistics-logo.jpg')
    def logo():return FileResponse(STATIC/'ctl-logistics-logo.jpg',media_type='image/jpeg',headers={'Cache-Control':'public, max-age=86400'})

    @router.get('/api/v1/tf/shell')
    def shell(user:User=Depends(require_driver),db:Session=Depends(database_session)):
        from .models import AccountLoginStamp,SessionToken
        from sqlalchemy import select,func
        from .security import TOKEN_LIFETIME
        from .version import SOFTWARE_TITLE,SOFTWARE_VERSION
        profile=db.get(TfProfile,user.id)
        if not profile:raise HTTPException(404,'Tf nicht gefunden')
        stamp=db.get(AccountLoginStamp,user.id)
        last_login=stamp.last_login_at if stamp else db.scalar(select(func.max(SessionToken.expires_at)).where(SessionToken.user_id==user.id))
        if last_login and not stamp:last_login-=TOKEN_LIFETIME
        return dict(first_name=profile.first_name,last_name=profile.last_name,tf_number=user.username,last_login_at=last_login.isoformat()+'Z' if last_login else None,software=SOFTWARE_TITLE,version=SOFTWARE_VERSION)

    @router.get('/api/v1/tf/me')
    def personal(user:User=Depends(require_driver),db:Session=Depends(database_session)):
        from .models import TfBahnCardValidity,ProfilePhoto
        from .accounts.tf_profiles import details_dict
        from .planning.duties import driver_type
        profile=db.get(TfProfile,user.id)
        if not profile:raise HTTPException(404,'Tf nicht gefunden')
        valid=db.get(TfBahnCardValidity,user.id)
        values={column.name:getattr(profile,column.name) for column in TfProfile.__table__.columns if column.name!='user_id'}
        values.update(details_dict(db,user),driver_type=driver_type(db,user.id),active=user.active,role=user.role,bahncard_valid_until=valid.valid_until if valid else None)
        return dict(data=values,has_photo=db.get(ProfilePhoto,user.id) is not None)

    @router.get('/api/v1/tf/me/photo')
    def personal_photo(user:User=Depends(require_driver),db:Session=Depends(database_session)):
        from .models import ProfilePhoto
        photo=db.get(ProfilePhoto,user.id)
        if not photo:raise HTTPException(404,'Kein Foto vorhanden')
        return Response(photo.image_data,media_type='image/jpeg')

    @router.get('/api/v1/tf/portal/plan/{year}/{month}')
    def plan(year:int=Path(ge=2000,le=2100),month:int=Path(ge=1,le=12),
             user:User=Depends(require_driver),db:Session=Depends(database_session)):
        if not db.get(TfProfile,user.id):raise HTTPException(404,'Tf nicht gefunden')
        return get_month(db,user.id,year,month)

    @router.get('/api/v1/tf/portal/plan/{year}')
    def annual_plan(year:int=Path(ge=2000,le=2100),user:User=Depends(require_driver),db:Session=Depends(database_session)):
        if not db.get(TfProfile,user.id):raise HTTPException(404,'Tf nicht gefunden')
        return get_year(db,user.id,year)

    return router
