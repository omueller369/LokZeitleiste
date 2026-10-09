from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import database_session
from ..models import AccountAudit, AccountPolicy, ModulePermission, SessionToken, StaffAddress, StaffProfile, User, ProfilePhoto
from ..schemas import Credentials
from ..security import hash_password, issue_token, revoke_token, user_from_token, verify_password
from .access import MODULES, check_delegation, demand, password_required, permissions
from .photos import decode_photo, save_photo
from .schemas import PasswordChange, PasswordReset, StaffCreate, StaffIn


def account_dependency(origin):
    def account(request: Request, admin_session: str | None = Cookie(default=None),
                authorization: str | None = Header(default=None), db: Session = Depends(database_session)):
        bearer = authorization and authorization.startswith('Bearer ')
        token = authorization.removeprefix('Bearer ').strip() if bearer else admin_session
        user = user_from_token(db,token)
        if not user:
            raise HTTPException(401,'Anmeldung erforderlich')
        if not bearer and request.method not in ('GET','HEAD') and origin() and request.headers.get('origin') != origin():
            raise HTTPException(403,'Ungültiger Ursprung')
        return user

    return account


def create_router(admin_dependency, origin, cookie_secure, dependency=None):
    router = APIRouter()

    account = dependency or account_dependency(origin)

    @router.post('/api/v1/account/login')
    def login(data: Credentials, request: Request, response: Response, db: Session = Depends(database_session)):
        if origin() and request.headers.get('origin') != origin():
            raise HTTPException(403,'Ungültiger Ursprung')
        user = db.scalar(select(User).where(User.username == data.username.strip().lower(),User.active == True))
        if not user or not verify_password(data.password,user.password_hash):
            raise HTTPException(401,'Anmeldung fehlgeschlagen')
        token = issue_token(db,user)
        response.set_cookie('admin_session',token,httponly=True,secure=cookie_secure,samesite='strict',path='/',max_age=365*24*3600)
        return {'username':user.username,'role':user.role,'password_change_required':password_required(db,user)}

    def identity(db,user):
        return {'id':user.id,'username':user.username,'role':user.role,
                'password_change_required':password_required(db,user),'permissions':permissions(db,user)}

    @router.get('/api/v1/account/me')
    def me(user: User = Depends(account),db: Session = Depends(database_session)):
        return identity(db,user)

    @router.post('/api/v1/account/password')
    def change(data: PasswordChange, response: Response, authorization: str | None = Header(default=None),
               user: User = Depends(account),db: Session = Depends(database_session)):
        current = db.scalar(select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True))
        if not verify_password(data.current_password,current.password_hash):
            raise HTTPException(403,'Aktuelles Passwort ist falsch')
        if verify_password(data.new_password,current.password_hash):
            raise HTTPException(422,'Neues Passwort muss sich vom bisherigen Passwort unterscheiden')
        current.password_hash = hash_password(data.new_password)
        policy = db.get(AccountPolicy,user.id)
        if not policy:
            policy = AccountPolicy(user_id=user.id,must_change_password=False); db.add(policy)
        policy.must_change_password = False
        db.execute(delete(SessionToken).where(SessionToken.user_id == user.id))
        db.add(AccountAudit(actor_id=user.id,target_id=user.id,action='password_changed'))
        db.commit()
        if not authorization or not authorization.startswith('Bearer '):
            response.delete_cookie('admin_session',path='/')
        return {'changed':True,'login_required':True}

    @router.post('/api/v1/account/logout')
    def logout(response: Response, admin_session: str | None = Cookie(default=None),
               authorization: str | None = Header(default=None), user: User = Depends(account),db: Session = Depends(database_session)):
        raw = authorization.removeprefix('Bearer ').strip() if authorization and authorization.startswith('Bearer ') else admin_session
        if raw: revoke_token(db,raw)
        response.delete_cookie('admin_session',path='/')
        return {'ok':True}

    @router.get('/api/v1/admin/me')
    def admin_me(user: User = Depends(admin_dependency), db: Session = Depends(database_session)):
        return identity(db,user)

    @router.get('/api/v1/admin/modules')
    def modules(user: User = Depends(admin_dependency), db: Session = Depends(database_session)):
        levels = permissions(db,user)
        return [{'id':m,'label':label,'maximum_level':levels[m]} for m,label in MODULES.items()]

    def staff_dict(db,user,profile):
        addresses = db.scalars(select(StaffAddress).where(StaffAddress.user_id == user.id).order_by(StaffAddress.id)).all()
        return {'id':user.id,'username':user.username,'active':user.active,
                **{key:getattr(profile,key) for key in ('first_name','last_name','nationality','cost_center')},
                'birth_date':profile.birth_date.isoformat(),'has_photo':db.get(ProfilePhoto,user.id) is not None,
                'addresses':[{key:getattr(a,key) for key in ('street','house_number','postal_code','city')} for a in addresses],
                'permissions':permissions(db,user),'password_change_required':password_required(db,user)}

    def save_profile(db,user,profile,data):
        for key in ('first_name','last_name','nationality','birth_date','cost_center'):
            setattr(profile,key,getattr(data,key))
        db.execute(delete(StaffAddress).where(StaffAddress.user_id == user.id))
        db.execute(delete(ModulePermission).where(ModulePermission.user_id == user.id))
        db.flush()
        db.add_all([StaffAddress(user_id=user.id,**a.model_dump()) for a in data.addresses])
        db.add_all([ModulePermission(user_id=user.id,module=m,level=v) for m,v in data.permissions.items() if v])

    @router.get('/api/v1/admin/staff')
    def staff_list(user: User = Depends(admin_dependency),db: Session = Depends(database_session)):
        rows = db.execute(select(User,StaffProfile).join(StaffProfile,User.id == StaffProfile.user_id)
                          .where(User.role == 'staff').order_by(StaffProfile.last_name)).all()
        return [staff_dict(db,u,p) for u,p in rows]

    @router.post('/api/v1/admin/staff',status_code=201)
    def create(data: StaffCreate,actor: User = Depends(admin_dependency),db: Session = Depends(database_session)):
        check_delegation(db,actor,data.permissions)
        image=decode_photo(data.photo_base64)
        try:
            user = User(username=data.username,password_hash=hash_password(data.initial_password),role='staff')
            db.add(user); db.flush()
            profile = StaffProfile(user_id=user.id)
            db.add(profile)
            # Stammdaten setzen, bevor die neue Profilzeile für Adressen angelegt wird.
            for key in ('first_name','last_name','nationality','birth_date','cost_center'):
                setattr(profile,key,getattr(data,key))
            db.flush()
            save_profile(db,user,profile,data)
            save_photo(db,user.id,image)
            db.add(AccountPolicy(user_id=user.id,must_change_password=True))
            db.add(AccountAudit(actor_id=actor.id,target_id=user.id,action='staff_created'))
            db.commit()
            return {'id':user.id,'username':user.username,'password_change_required':True}
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(409,'Benutzername bereits vergeben') from exc

    @router.put('/api/v1/admin/staff/{user_id}')
    def update(user_id: int,data: StaffIn,actor: User = Depends(admin_dependency),db: Session = Depends(database_session)):
        user = db.scalar(select(User).where(User.id == user_id).with_for_update())
        profile = db.get(StaffProfile,user_id)
        if not user or user.role != 'staff' or not profile:
            raise HTTPException(404,'Verwaltungsmitarbeiter nicht gefunden')
        if data.permissions != permissions(db,user):
            demand(db,actor,'staff',3)
        check_delegation(db,actor,data.permissions,user)
        image=decode_photo(data.photo_base64)
        save_profile(db,user,profile,data)
        save_photo(db,user.id,image)
        # Rechteänderungen beenden alle Sitzungen; erneute Anmeldung übernimmt die Freigaben.
        db.execute(delete(SessionToken).where(SessionToken.user_id == user.id))
        db.add(AccountAudit(actor_id=actor.id,target_id=user.id,action='staff_profile_permissions_updated'))
        db.commit()
        return staff_dict(db,user,profile)

    @router.post('/api/v1/admin/accounts/{user_id}/reset-password')
    def reset(user_id: int,data: PasswordReset,actor: User = Depends(admin_dependency),db: Session = Depends(database_session)):
        user = db.scalar(select(User).where(User.id == user_id).with_for_update())
        if not user:
            raise HTTPException(404,'Konto nicht gefunden')
        if user.id == actor.id:
            raise HTTPException(422,'Für Ihr eigenes Konto bitte Passwort ändern verwenden')
        if user.role != 'tf':
            check_delegation(db,actor,{},user)
        if verify_password(data.initial_password,user.password_hash):
            raise HTTPException(422,'Initialpasswort muss sich vom bisherigen Passwort unterscheiden')
        user.password_hash = hash_password(data.initial_password)
        policy = db.get(AccountPolicy,user.id)
        if not policy:
            policy=AccountPolicy(user_id=user.id); db.add(policy)
        policy.must_change_password=True
        db.execute(delete(SessionToken).where(SessionToken.user_id == user.id))
        db.add(AccountAudit(actor_id=actor.id,target_id=user.id,action='password_reset'))
        db.commit()
        return {'reset':True,'password_change_required':True}

    return router
