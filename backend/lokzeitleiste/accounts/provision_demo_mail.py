"""Assign personal demo addresses once, without changing existing portal passwords."""
import os
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import engine
from ..models import AccountAudit, EmployeeEmail, TfProfile, User
from ..employee_mail import save_email,suggest,domains
from .seed_demo_tf import PASSWORD
from .import_demo_tf import PREFIX


def provision(db):
    choices=domains(db)
    if not choices:raise ValueError('Keine Maildomain konfiguriert')
    domain=os.environ['CTL_MAIL_DOMAIN']
    ids=set(db.scalars(select(AccountAudit.target_id).where(AccountAudit.action.like(PREFIX+'%'))))
    count=0
    for uid in sorted(ids):
        user=db.get(User,uid);profile=db.get(TfProfile,uid)
        if not user or not profile or db.get(EmployeeEmail,uid):continue
        address=suggest(db,profile.first_name,profile.last_name,profile.birth_date,domain,uid)
        save_email(db,user,address,PASSWORD);count+=1
    db.commit();return count

if __name__=='__main__':
    with Session(engine()) as db:print('Demo-Postfächer vorbereitet:',provision(db))
