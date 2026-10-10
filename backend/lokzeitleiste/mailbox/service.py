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
        raise HTTPException(409, 'Postfach-Verschlüsselungsschlüssel muss auf dem Server eingerichtet werden.') from exc


def password(account):
    try:
        return cipher().decrypt(account.password_encrypted.encode()).decode()
    except InvalidToken as exc:
        raise HTTPException(409, 'Postfachschlüssel passt nicht. Zugangsdaten neu hinterlegen.') from exc


def host(name):
    value = os.environ.get(name, '').strip()
    if not value:
        raise HTTPException(409, 'Mailserver ist noch nicht eingerichtet: '+name)
    return value


@contextmanager
def connection(account):
    client = None
    try:
        cfg=settings(account)
        if not cfg['imap_host']:raise HTTPException(409,'Mailserver ist noch nicht eingerichtet: MAILBOX_IMAP_HOST')
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
        raise HTTPException(502, 'Postfachverbindung fehlgeschlagen. Server und Zugangsdaten prüfen.') from exc
    finally:
        if client:
            try:
                client.logout()
            except (imaplib.IMAP4.error, OSError):
                pass


def folder_name(value):
    if not value or len(value)>200 or any(ord(c)<32 for c in value):
        raise HTTPException(422, 'Ungültiger Ordner')
    return '"'+value.replace('\\','\\\\').replace('"','\\"')+'"'


def select_folder(client, folder, validity=None, readonly=True):
    status, _ = client.select(folder_name(folder), readonly=readonly)
    if status != 'OK':
        raise HTTPException(404, 'Postfachordner nicht gefunden')
    _, values = client.response('UIDVALIDITY')
    current = values[0].decode() if values and values[0] else ''
    if validity is not None and (not current or current != validity):
        raise HTTPException(409, 'Postfachordner hat sich geändert. Bitte neu laden.')
    return current


def payload_bytes(rows):
    return b''.join(row[1] for row in rows if isinstance(row, tuple) and isinstance(row[1], bytes))


def message_bytes(client, uid):
    status, sizes = client.uid('fetch', str(uid), '(RFC822.SIZE)')
    found = re.search(rb'RFC822.SIZE (\d+)', b' '.join(r for r in sizes if isinstance(r, bytes)))
    if status != 'OK' or not found:
        raise HTTPException(404, 'Nachricht nicht gefunden')
    if int(found.group(1)) > MAX_MESSAGE:
        raise HTTPException(413, 'Nachricht größer als 10 MiB; bitte im externen Mailprogramm öffnen.')
    status, rows = client.uid('fetch', str(uid), '(BODY.PEEK[])')
    raw = payload_bytes(rows)
    if status != 'OK' or not raw:
        raise HTTPException(404, 'Nachricht nicht gefunden')
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
    return dict(subject=str(msg.get('Subject','')), sender=str(msg.get('From','')), to=str(msg.get('To','')),
                reply_to=str(msg.get('Reply-To',msg.get('From',''))), date=str(msg.get('Date','')),
                message_id=str(msg.get('Message-ID','')), body=value,
                attachments=[dict(index=i, name=a.get_filename() or 'Anhang', size=len(a.get_payload(decode=True) or b'')) for i,a in enumerate(attachments)])


def send(account, data):
    msg = EmailMessage()
    msg['From'] = account.address
    msg['To'] = ', '.join(str(a) for a in data.to)
    msg['Subject'] = data.subject
    msg['Date'] = email.utils.formatdate(localtime=True)
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
            raise HTTPException(422,'Ungültiger Anhang') from exc
        msg.add_attachment(content, maintype='application', subtype='octet-stream', filename=item.name)
    if len(msg.as_bytes()) > MAX_MESSAGE:
        raise HTTPException(413,'Nachricht inklusive Anhängen darf höchstens 10 MiB groß sein.')
    try:
        cfg=settings(account);security=cfg['smtp_security'];server=cfg['smtp_host'];port=cfg['smtp_port']
        if not server:raise HTTPException(409,'Mailserver ist noch nicht eingerichtet: MAILBOX_SMTP_HOST')
        if security not in ('ssl','starttls'):
            raise HTTPException(409,'Postfach-SMTP benötigt SSL oder STARTTLS.')
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
            refused=client.send_message(msg)
            if refused:
                raise HTTPException(502,'Mindestens ein Empfänger wurde abgelehnt. Zustellung kann teilweise erfolgt sein; Empfänger vor erneutem Senden prüfen.')
    except (smtplib.SMTPException,OSError,ValueError) as exc:
        raise HTTPException(502,'E-Mail-Versand fehlgeschlagen. Keine automatische Wiederholung; Postfach und Server prüfen.') from exc
    warning=''
    sent_folder=settings(account)['sent_folder']
    try:
        with connection(account) as client:
            status,_=client.append(folder_name(sent_folder),'\\Seen',imaplib.Time2Internaldate(__import__('time').time()),msg.as_bytes())
            if status!='OK': warning='Versendet, aber Kopie im Gesendet-Ordner konnte nicht gespeichert werden.'
    except HTTPException:
        warning='Versendet, aber Kopie im Gesendet-Ordner konnte nicht gespeichert werden.'
    return dict(sent=True, warning=warning)
