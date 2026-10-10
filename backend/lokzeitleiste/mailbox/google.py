"""Google OAuth/API account linking with PKCE, one-use state and session binding."""
import base64
import hashlib
import json
import os
import secrets
import time
from datetime import timedelta
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from fastapi import APIRouter, Depends, HTTPException, Cookie, Response, Query
from fastapi.responses import RedirectResponse
from pydantic import EmailStr, TypeAdapter
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from ..db import database_session
from ..models import User, TfProfile, MailboxAccount, MailboxSettings, MailboxOAuthState, SessionToken, now_utc
from ..accounts.access import demand
from .providers import PROVIDERS, settings
from . import oauth

SCOPE='https://mail.google.com/'
COOKIE='mailbox_google_nonce'
CALLBACK='/api/v1/mailbox/google/callback'


def digest(value):return hashlib.sha256(value.encode()).hexdigest()

def application(origin):
    client=os.getenv('MAILBOX_GOOGLE_CLIENT_ID','').strip();secret=os.getenv('MAILBOX_GOOGLE_CLIENT_SECRET','').strip()
    url=urlsplit(origin)
    if not client or not secret or url.scheme not in ('http','https') or not url.netloc or url.path not in ('','/') or url.query or url.fragment:
        raise HTTPException(409,'Google-App-Zugang und öffentliche Serveradresse müssen eingerichtet werden.')
    if url.scheme!='https' and url.hostname not in ('localhost','127.0.0.1'):
        raise HTTPException(409,'Google-Anmeldung benötigt HTTPS.')
    return client,secret,origin.rstrip('/')+CALLBACK


def request_json(url,data=None,token=None):
    headers={'Accept':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    encoded=urlencode(data).encode() if data else None
    if encoded:headers['Content-Type']='application/x-www-form-urlencoded'
    try:
        with urlopen(Request(url,data=encoded,headers=headers),timeout=15) as response:return json.loads(response.read(1024*1024))
    except (HTTPError,URLError,OSError,ValueError) as exc:
        raise HTTPException(502,'Google-Anmeldung fehlgeschlagen. Bitte erneut verbinden.') from exc


def fingerprint(db,tf_id):
    account=db.get(MailboxAccount,tf_id);row=db.get(MailboxSettings,tf_id)
    return digest(json.dumps([account.address,account.username,account.password_encrypted,row.config_json if row else '',row.tokens_encrypted if row else ''])) if account else 'new'


def access_token(account):
    db=account._db
    row=db.scalar(select(MailboxSettings).where(MailboxSettings.tf_user_id==account.tf_user_id).with_for_update().execution_options(populate_existing=True))
    cfg=json.loads(row.config_json)
    if cfg.get('provider')!='google' or cfg.get('auth_method')!='oauth2' or not row.tokens_encrypted:
        raise HTTPException(409,'Google-Zugang erneut verbinden.')
    previous=oauth.unseal(row.tokens_encrypted)
    if previous['expires_at']>time.time()+60:db.commit();return previous['access_token']
    client=os.getenv('MAILBOX_GOOGLE_CLIENT_ID','');secret=os.getenv('MAILBOX_GOOGLE_CLIENT_SECRET','')
    if not client or not secret:raise HTTPException(409,'Google-App-Zugang und öffentliche Serveradresse müssen eingerichtet werden.')
    result=request_json('https://oauth2.googleapis.com/token',dict(client_id=client,client_secret=secret,grant_type='refresh_token',refresh_token=previous['refresh_token']))
    oauth.store_tokens(row,result,previous);db.commit();return result['access_token']


def create_router(require_admin,public_origin):
    router=APIRouter()

    @router.post('/api/v1/admin/email/{tf_id}/google/start')
    def start(tf_id:int,response:Response,actor:User=Depends(require_admin),admin_session:str|None=Cookie(default=None),db:Session=Depends(database_session)):
        user=db.get(User,tf_id);profile=db.get(TfProfile,tf_id)
        if not user or user.role!='tf' or not profile:raise HTTPException(404,'Tf nicht gefunden')
        client,_,redirect=application(public_origin());oauth.cipher()
        if not admin_session:raise HTTPException(401,'Admin-Anmeldung erforderlich')
        state=secrets.token_urlsafe(32);nonce=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(48)
        challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        db.execute(delete(MailboxOAuthState).where(MailboxOAuthState.expires_at<now_utc()))
        db.add(MailboxOAuthState(state_hash=digest(state),tf_user_id=tf_id,actor_id=actor.id,expires_at=now_utc()+timedelta(minutes=10),encrypted_payload=oauth.seal(dict(nonce_hash=digest(nonce),session_hash=digest(admin_session),verifier=verifier,client_id=client,redirect_uri=redirect,fingerprint=fingerprint(db,tf_id)))))
        db.commit();response.set_cookie(COOKIE,nonce,max_age=600,httponly=True,secure=public_origin().startswith('https:'),samesite='lax',path=CALLBACK)
        params=dict(client_id=client,redirect_uri=redirect,response_type='code',scope=SCOPE,access_type='offline',prompt='consent select_account',state=state,code_challenge=challenge,code_challenge_method='S256',login_hint=profile.email)
        return dict(url='https://accounts.google.com/o/oauth2/v2/auth?'+urlencode(params))

    @router.get(CALLBACK)
    def callback(state:str=Query(max_length=200),code:str|None=Query(default=None,max_length=4096),error:str|None=Query(default=None,max_length=200),mailbox_google_nonce:str|None=Cookie(default=None),db:Session=Depends(database_session)):
        row=db.scalar(select(MailboxOAuthState).where(MailboxOAuthState.state_hash==digest(state)).with_for_update())
        if not row or row.expires_at<=now_utc():raise HTTPException(409,'Google-Anmeldung abgelaufen. Erneut starten.')
        data=oauth.unseal(row.encrypted_payload)
        if not mailbox_google_nonce or not secrets.compare_digest(data['nonce_hash'],digest(mailbox_google_nonce)):
            raise HTTPException(403,'Google-Anmeldung gehört nicht zu dieser Sitzung.')
        session=db.scalar(select(SessionToken).where(SessionToken.token_hash==data['session_hash'],SessionToken.user_id==row.actor_id,SessionToken.expires_at>now_utc()))
        actor=db.get(User,row.actor_id)
        if not session or not actor or not actor.active or actor.role not in ('admin','staff'):
            raise HTTPException(401,'Admin-Anmeldung erforderlich')
        demand(db,actor,'email',3)
        tf_id=row.tf_user_id;db.delete(row);db.commit()
        status='oauth_error=1'
        try:
            if error or not code:raise HTTPException(409,'Google-Anmeldung abgebrochen.')
            client,secret,redirect=application(public_origin())
            if client!=data['client_id'] or redirect!=data['redirect_uri']:raise HTTPException(409,'Google-Anmeldung abgelaufen. Erneut starten.')
            result=request_json('https://oauth2.googleapis.com/token',dict(client_id=client,client_secret=secret,code=code,grant_type='authorization_code',redirect_uri=redirect,code_verifier=data['verifier']))
            if not result.get('access_token') or not result.get('refresh_token') or SCOPE not in result.get('scope','').split():
                raise HTTPException(409,'Google-Zugang erneut verbinden.')
            profile=request_json('https://gmail.googleapis.com/gmail/v1/users/me/profile',token=result['access_token'])
            address=str(TypeAdapter(EmailStr).validate_python(profile.get('emailAddress','')))
            # Lock the employee before replacing the linked account; reject concurrent changes.
            target=db.scalar(select(User).where(User.id==tf_id).with_for_update())
            if not target or target.role!='tf' or fingerprint(db,tf_id)!=data['fingerprint']:
                raise HTTPException(409,'Postfach wurde geändert. Erneut verbinden.')
            account=db.get(MailboxAccount,tf_id)
            if not account:account=MailboxAccount(tf_user_id=tf_id);db.add(account)
            account.address=account.username=address;account.password_encrypted='';db.flush()
            setting=db.get(MailboxSettings,tf_id)
            if not setting:setting=MailboxSettings(tf_user_id=tf_id);db.add(setting)
            setting.config_json=json.dumps(dict(PROVIDERS['google'],provider='google',smtp_username='',auth_method='oauth2'))
            oauth.store_tokens(setting,result);db.commit();status='oauth_connected=1'
        except (HTTPException,ValueError):db.rollback()
        response=RedirectResponse('/admin/email?tf='+str(tf_id)+'&'+status,status_code=303)
        response.delete_cookie(COOKIE,path=CALLBACK);response.headers['Cache-Control']='no-store';response.headers['Referrer-Policy']='no-referrer'
        return response
    return router
