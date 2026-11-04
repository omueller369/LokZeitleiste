from ..localization import source as _text_source
import email
import imaplib
import os
import re
import smtplib
import ssl
from contextlib import contextmanager
from email.message import EmailMessage
from email.policy import default
from html.parser import HTMLParser
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

from .providers import settings

MAX_MESSAGE = 10 * 1024 * 1024


def cipher():
    try:
        return Fernet(os.environ.get('MAILBOX_ENCRYPTION_KEY', '').encode())
    except (ValueError, TypeError) as exc:
        raise HTTPException(409, _text_source('server_mailbox_service.text_1148fd35f915')) from exc


def password(account):
    try:
        return cipher().decrypt(account.password_encrypted.encode()).decode()
    except InvalidToken as exc:
        raise HTTPException(409, _text_source('server_mailbox_service.text_0357b8d84286')) from exc


def host(name):
    value = os.environ.get(name, '').strip()
    if not value:
        raise HTTPException(409, _text_source('server_mailbox_service.text_c411554968a4')+name)
    return value


@contextmanager
def connection(account):
    client = None
    try:
        cfg=settings(account)
        if not cfg['imap_host']:raise HTTPException(409,_text_source('server_mailbox_service.text_97f7bb674340'))
        if cfg['imap_security']=='ssl':client=imaplib.IMAP4_SSL(cfg['imap_host'],cfg['imap_port'],ssl_context=ssl.create_default_context(),timeout=15)
        else:
            client=imaplib.IMAP4(cfg['imap_host'],cfg['imap_port'],timeout=15)
            client.starttls(ssl_context=ssl.create_default_context())
        if cfg['provider']=='microsoft' or (cfg['provider']=='google' and cfg.get('auth_method')=='oauth2'):
            if cfg['provider']=='google':from .google import access_token
            else:from .oauth import access_token
            token=access_token(account)
            client.authenticate('XOAUTH2',lambda _:('user='+account.username+'\x01auth=Bearer '+token+'\x01\x01').encode())
        else:client.login(account.username,password(account))
        yield client
    except (imaplib.IMAP4.error, OSError, ValueError) as exc:
        raise HTTPException(502, _text_source('server_mailbox_service.text_50e64315bb61')) from exc
    finally:
        if client:
            try:
                client.logout()
            except (imaplib.IMAP4.error, OSError):
                pass


def folder_name(value):
    if not value or len(value)>200 or any(ord(c)<32 for c in value):
        raise HTTPException(422, _text_source('server_mailbox_service.text_e50b22ccbc58'))
    return '"'+value.replace('\\','\\\\').replace('"','\\"')+'"'


def select_folder(client, folder, validity=None, readonly=True):
    status, _ = client.select(folder_name(folder), readonly=readonly)
    if status != 'OK':
        raise HTTPException(404, _text_source('server_mailbox_service.text_f00305a5a31e'))
    _, values = client.response('UIDVALIDITY')
    current = values[0].decode() if values and values[0] else ''
    if validity is not None and (not current or current != validity):
        raise HTTPException(409, _text_source('server_mailbox_service.text_93207f76e5a7'))
    return current


def payload_bytes(rows):
    return b''.join(row[1] for row in rows if isinstance(row, tuple) and isinstance(row[1], bytes))


def message_bytes(client, uid):
    status, sizes = client.uid('fetch', str(uid), '(RFC822.SIZE)')
    found = re.search(rb'RFC822.SIZE (\d+)', b' '.join(r for r in sizes if isinstance(r, bytes)))
    if status != 'OK' or not found:
        raise HTTPException(404, _text_source('server_mailbox_service.text_9398a18492a2'))
    if int(found.group(1)) > MAX_MESSAGE:
        raise HTTPException(413, _text_source('server_mailbox_service.text_6381fdab9086'))
    status, rows = client.uid('fetch', str(uid), '(BODY.PEEK[])')
    raw = payload_bytes(rows)
    if status != 'OK' or not raw:
        raise HTTPException(404, _text_source('server_mailbox_service.text_9398a18492a2'))
    return email.message_from_bytes(raw, policy=default)


class PlainHTML(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style'): self.skip+=1
        if tag in ('p','br','div','li'): self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ('script','style') and self.skip: self.skip-=1
    def handle_data(self, data):
        if not self.skip: self.parts.append(data)


def view_message(msg):
    body = msg.get_body(preferencelist=('plain', 'html'))
    value = body.get_content() if body else ''
    if body and body.get_content_type() == 'text/html':
        parser=PlainHTML();parser.feed(value);value=''.join(parser.parts)
    attachments = list(msg.iter_attachments())
    return dict(subject=str(msg.get(_text_source('server_mailbox_service.text_68971283841a'),'')), sender=str(msg.get(_text_source('server_mailbox_service.text_218197693424'),'')), to=str(msg.get('To','')),
                reply_to=str(msg.get('Reply-To',msg.get(_text_source('server_mailbox_service.text_218197693424'),''))), date=str(msg.get(_text_source('server_mailbox_service.text_99c40ab40592'),'')),
                message_id=str(msg.get('Message-ID','')), body=value,
                attachments=[dict(index=i, name=a.get_filename() or _text_source('server_mailbox_service.text_9e313cd30ea1'), size=len(a.get_payload(decode=True) or b'')) for i,a in enumerate(attachments)])


def send(account, data):
    msg = EmailMessage()
    msg[_text_source('server_mailbox_service.text_218197693424')] = account.address
    msg['To'] = ', '.join(str(a) for a in data.to)
    if getattr(data,'cc',[]):msg['Cc'] = ', '.join(str(a) for a in data.cc)
    msg[_text_source('server_mailbox_service.text_68971283841a')] = data.subject
    msg[_text_source('server_mailbox_service.text_99c40ab40592')] = email.utils.formatdate(localtime=True)
    msg['Message-ID'] = email.utils.make_msgid()
    if data.in_reply_to:
        msg['In-Reply-To'] = data.in_reply_to
        msg['References'] = data.in_reply_to
    msg.set_content(data.body)
    import base64
    for item in data.attachments:
        try:
            content=base64.b64decode(item.content_base64,validate=True)
        except ValueError as exc:
            raise HTTPException(422,_text_source('server_mailbox_service.text_918edb31339c')) from exc
        msg.add_attachment(content, maintype='application', subtype='octet-stream', filename=item.name)
    return send_prepared(account,msg,data)


def send_prepared(account,msg,data):
    if len(msg.as_bytes()) > MAX_MESSAGE:
        raise HTTPException(413,_text_source('server_mailbox_service.text_05150731716a'))
    try:
        cfg=settings(account);security=cfg['smtp_security'];server=cfg['smtp_host'];port=cfg['smtp_port']
        if not server:raise HTTPException(409,_text_source('server_mailbox_service.text_a1ec065c6346'))
        if security not in ('ssl','starttls'):
            raise HTTPException(409,_text_source('server_mailbox_service.text_843ace047541'))
        with (smtplib.SMTP_SSL(server,port,timeout=15,context=ssl.create_default_context()) if security=='ssl' else smtplib.SMTP(server,port,timeout=15)) as client:
            if security=='starttls':
                client.starttls(context=ssl.create_default_context())
            username=cfg.get('smtp_username') or account.username
            if cfg['provider']=='microsoft' or (cfg['provider']=='google' and cfg.get('auth_method')=='oauth2'):
                if cfg['provider']=='google':from .google import access_token
                else:from .oauth import access_token
                token=access_token(account)
                client.auth('XOAUTH2',lambda challenge=None:'' if challenge else 'user='+username+'\x01auth=Bearer '+token+'\x01\x01')
            else:client.login(username,password(account))
            recipients=[str(a) for a in [*data.to,*getattr(data,'cc',[]),*getattr(data,'bcc',[])]]
            refused=client.send_message(msg,to_addrs=recipients) if getattr(data,'cc',[]) or getattr(data,'bcc',[]) else client.send_message(msg)
            if refused:
                raise HTTPException(502,_text_source('server_mailbox_service.text_4334ed9da2f0'))
    except (smtplib.SMTPException,OSError,ValueError) as exc:
        raise HTTPException(502,_text_source('server_mailbox_service.text_b65390d9692e')) from exc
    warning=''
    sent_folder=settings(account)['sent_folder']
    try:
        with connection(account) as client:
            status,_=client.append(folder_name(sent_folder),'\\Seen',imaplib.Time2Internaldate(__import__('time').time()),msg.as_bytes())
            if status!='OK': warning=_text_source('server_mailbox_service.text_0d94fb23ce2e')
    except HTTPException:
        warning=_text_source('server_mailbox_service.text_0d94fb23ce2e')
    return dict(sent=True, warning=warning)
