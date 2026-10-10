"""Provider defaults. Saved settings always take precedence over environment defaults."""
import json
import re
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

PROVIDERS = {
    'manual': dict(imap_host='', imap_port=993, imap_security='ssl', smtp_host='', smtp_port=587, smtp_security='starttls', sent_folder='Sent'),
    'google': dict(imap_host='imap.gmail.com', imap_port=993, imap_security='ssl', smtp_host='smtp.gmail.com', smtp_port=587, smtp_security='starttls', sent_folder='[Gmail]/Sent Mail'),
    'apple': dict(imap_host='imap.mail.me.com', imap_port=993, imap_security='ssl', smtp_host='smtp.mail.me.com', smtp_port=587, smtp_security='starttls', sent_folder='Sent Messages'),
    'webde': dict(imap_host='imap.web.de', imap_port=993, imap_security='ssl', smtp_host='smtp.web.de', smtp_port=587, smtp_security='starttls', sent_folder='Gesendet'),
    'yahoo': dict(imap_host='imap.mail.yahoo.com', imap_port=993, imap_security='ssl', smtp_host='smtp.mail.yahoo.com', smtp_port=465, smtp_security='ssl', sent_folder='Sent'),
    'microsoft': dict(imap_host='outlook.office365.com', imap_port=993, imap_security='ssl', smtp_host='smtp-mail.outlook.com', smtp_port=587, smtp_security='starttls', sent_folder='Sent'),
}


class ServerInput(BaseModel):
    provider: Literal['manual','google','apple','webde','yahoo','microsoft'] = 'manual'
    auth_method: Literal["password","oauth2"] = "password"
    imap_host: str = Field(min_length=1,max_length=253)
    imap_port: int = Field(ge=1,le=65535)
    imap_security: Literal['ssl','starttls']
    smtp_host: str = Field(min_length=1,max_length=253)
    smtp_port: int = Field(ge=1,le=65535)
    smtp_security: Literal['ssl','starttls']
    smtp_username: str = Field(default='',max_length=320)
    sent_folder: str = Field(default='Sent',min_length=1,max_length=200)

    @field_validator('imap_host','smtp_host')
    @classmethod
    def server_name(cls,value):
        value=value.strip().lower()
        if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?',value):
            raise ValueError('Servername ohne Protokoll, Pfad oder Leerzeichen eingeben.')
        return value

    @field_validator('smtp_username','sent_folder')
    @classmethod
    def plain_string(cls,value):
        if any(ord(c)<32 for c in value):raise ValueError('Ungültige Eingabe')
        return value.strip()

    @model_validator(mode='after')
    def microsoft_servers(self):
        if self.provider=='microsoft' and (self.imap_host!='outlook.office365.com' or self.smtp_host not in ('smtp-mail.outlook.com','smtp.office365.com') or self.imap_port!=993 or self.imap_security!='ssl' or self.smtp_port!=587 or self.smtp_security!='starttls'):
            raise ValueError('Microsoft benötigt die vorgegebenen Server und OAuth2.')
        if self.provider=='google' and self.auth_method=='oauth2' and (self.imap_host!='imap.gmail.com' or self.smtp_host!='smtp.gmail.com' or self.imap_port!=993 or self.imap_security!='ssl' or (self.smtp_port,self.smtp_security) not in ((587,'starttls'),(465,'ssl'))):raise ValueError('Google OAuth2 benötigt die vorgegebenen Google-Server.')
        return self


def settings(account):
    saved=getattr(account,'_settings',None)
    if saved:return json.loads(saved.config_json)
    import os
    return dict(provider='manual', imap_host=os.getenv('MAILBOX_IMAP_HOST',''),imap_port=int(os.getenv('MAILBOX_IMAP_PORT','993')),imap_security='ssl',smtp_host=os.getenv('MAILBOX_SMTP_HOST',''),smtp_port=int(os.getenv('MAILBOX_SMTP_PORT','465')),smtp_security=os.getenv('MAILBOX_SMTP_SECURITY','ssl'),smtp_username='',sent_folder=os.getenv('MAILBOX_SENT_FOLDER','Sent'))
