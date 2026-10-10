"""Microsoft device authorization; secrets are never returned to the browser."""
import json
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from fastapi import HTTPException
from .service import cipher

SCOPES='offline_access https://outlook.office.com/IMAP.AccessAsUser.All https://outlook.office.com/SMTP.Send'


def application():
    client=os.getenv('MAILBOX_MICROSOFT_CLIENT_ID','').strip()
    tenant=os.getenv('MAILBOX_MICROSOFT_TENANT','common').strip()
    if not re.fullmatch(r'[a-fA-F0-9-]{36}',client) or not re.fullmatch(r'[a-zA-Z0-9.-]+',tenant):
        raise HTTPException(409,'Microsoft-App-ID muss auf dem Server eingerichtet werden.')
    return client,tenant


def request_token(endpoint,data):
    _,tenant=application()
    request=Request('https://login.microsoftonline.com/'+tenant+'/oauth2/v2.0/'+endpoint,data=urlencode(data).encode(),headers={'Content-Type':'application/x-www-form-urlencoded'})
    try:
        with urlopen(request,timeout=15) as response:return json.loads(response.read(1024*1024))
    except HTTPError as exc:
        try:return json.loads(exc.read(1024*1024))
        except (ValueError,OSError):raise HTTPException(502,'Microsoft-Anmeldung fehlgeschlagen.') from exc
    except (URLError,OSError,ValueError) as exc:
        raise HTTPException(502,'Microsoft-Anmeldung fehlgeschlagen.') from exc


def seal(value):return cipher().encrypt(json.dumps(value).encode()).decode()

def unseal(value):
    from cryptography.fernet import InvalidToken
    try:return json.loads(cipher().decrypt(value.encode()))
    except (InvalidToken,ValueError,TypeError,AttributeError) as exc:
        raise HTTPException(409,'Microsoft-Zugang erneut verbinden.') from exc


def store_tokens(row,result,previous=None):
    if not result.get('access_token') or not (result.get('refresh_token') or (previous or {}).get('refresh_token')):
        raise HTTPException(409,'Microsoft-Zugang erneut verbinden.')
    value=dict(access_token=result['access_token'],refresh_token=result.get('refresh_token') or previous['refresh_token'],expires_at=time.time()+int(result.get('expires_in',3600)))
    row.tokens_encrypted=seal(value)


def access_token(account):
    row=getattr(account,'_settings',None);db=getattr(account,'_db',None)
    if not row or not row.tokens_encrypted or db is None:
        raise HTTPException(409,'Microsoft-Zugang erneut verbinden.')
    # Lock refresh-token rotation against concurrent IMAP/SMTP requests.
    from sqlalchemy import select
    from ..models import MailboxSettings
    row=db.scalar(select(MailboxSettings).where(MailboxSettings.tf_user_id==account.tf_user_id).with_for_update().execution_options(populate_existing=True))
    previous=unseal(row.tokens_encrypted)
    if previous['expires_at']>time.time()+60:
        db.commit();return previous['access_token']
    client,_=application()
    result=request_token('token',dict(client_id=client,grant_type='refresh_token',refresh_token=previous['refresh_token'],scope=SCOPES))
    store_tokens(row,result,previous);db.commit();return result['access_token']
