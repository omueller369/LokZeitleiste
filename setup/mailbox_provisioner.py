#!/usr/bin/python3
"""Root-owned local mailbox provisioner. No HTTP, shell commands or user-supplied paths."""
import fcntl
import grp
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import tempfile
from urllib.parse import urlsplit, unquote
from cryptography.fernet import Fernet
import pymysql


def atomic(path,text,mode=0o644,gid=0):
    path=Path(path)
    if path.is_symlink():raise ValueError('Symlink rejected')
    fd,name=tempfile.mkstemp(prefix=path.name+'.ctl-',dir=path.parent)
    temp=Path(name)
    try:
        with os.fdopen(fd,'w') as out:out.write(text)
        os.chown(temp,0,gid);os.chmod(temp,mode);os.replace(temp,path)
    finally:
        if temp.exists():temp.unlink()


def main():
    if os.geteuid()!=0:raise ValueError('Root required')
    with open('/run/lock/ctl-mailboxes.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        env=json.loads(Path('/etc/ctlsoftware-test/environment.json').read_text())
        url=urlsplit(env['DATABASE_URL']);crypto=Fernet(env['MAILBOX_ENCRYPTION_KEY'].encode())
        conn=pymysql.connect(host=url.hostname,port=url.port or 3306,user=unquote(url.username),password=unquote(url.password),database=url.path[1:],charset='utf8mb4',autocommit=False)
        identity=pwd.getpwnam('ctlvmail')
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT p.user_id,p.address,p.password_encrypted FROM mailbox_provisions p JOIN employee_emails e ON e.user_id=p.user_id AND e.address=p.address JOIN users u ON u.id=p.user_id WHERE p.status='pending' AND e.managed=1 AND u.active=1 FOR UPDATE")
                jobs=cur.fetchall()
                if not jobs:return
                cur.execute('SELECT name FROM email_domains');allowed={r[0] for r in cur.fetchall()}
                if any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+',d) for d in allowed):raise ValueError('Invalid domain configuration')
                passwd=Path('/etc/dovecot/ctl-users').read_text().splitlines()
                boxes=Path('/etc/postfix/ctl-mailboxes').read_text().splitlines()
                for uid,address,encrypted in jobs:
                    if not re.fullmatch(r'[a-z0-9][a-z0-9._+-]{0,63}@[a-z0-9.-]{3,253}',address):raise ValueError('Invalid mailbox address')
                    local,domain=address.split('@')
                    if domain not in allowed or any(p in ('','..','.') for p in domain.split('.')):raise ValueError('Invalid managed domain')
                    home=Path('/var/vmail')/domain/local
                    # Only fixed descendants, never follow an existing symlink.
                    for folder in [home.parent,home,home/'Maildir',*[home/'Maildir'/p for p in ('cur','new','tmp')]]:
                        if folder.is_symlink():raise ValueError('Symlink rejected')
                        folder.mkdir(exist_ok=True);os.chown(folder,identity.pw_uid,identity.pw_gid);folder.chmod(0o700)
                    secret=crypto.decrypt(encrypted.encode()).decode()
                    hashed=subprocess.run(['openssl','passwd','-6','-stdin'],input=secret,text=True,capture_output=True,check=True).stdout.strip()
                    passwd=[r for r in passwd if not r.startswith(address+':')]
                    passwd.append(f'{address}:{{SHA512-CRYPT}}{hashed}:{identity.pw_uid}:{identity.pw_gid}::{home}::')
                    boxes=[r for r in boxes if r.split()[:1]!=[address]];boxes.append(address+' 1')
                atomic('/etc/dovecot/ctl-users','\n'.join(passwd)+'\n',0o640,grp.getgrnam('dovecot').gr_gid)
                atomic('/etc/postfix/ctl-mailboxes','\n'.join(boxes)+'\n')
                atomic('/etc/postfix/ctl-domains',''.join(d+' OK\n' for d in sorted(allowed|{env['CTL_MAIL_DOMAIN']})))
                keyfile='/etc/opendkim/keys/'+env['CTL_MAIL_DOMAIN']+'/ctl.private'
                atomic('/etc/opendkim/ctl-keys',''.join(f'ctl._domainkey.{d} {d}:ctl:{keyfile}\n' for d in sorted(allowed|{env['CTL_MAIL_DOMAIN']})))
                atomic('/etc/opendkim/ctl-signing',''.join(f'*@{d} ctl._domainkey.{d}\n' for d in sorted(allowed|{env['CTL_MAIL_DOMAIN']})))
                for name in ('ctl-mailboxes','ctl-domains'):subprocess.run(['postmap','/etc/postfix/'+name],check=True)
                subprocess.run(['postfix','check'],check=True)
                subprocess.run(['systemctl','reload','dovecot','postfix','opendkim'],check=True)
                for uid,_,_ in jobs:cur.execute("UPDATE mailbox_provisions SET status='ready',error='' WHERE user_id=%s",(uid,))
                conn.commit()


if __name__=='__main__':
    try:main()
    except Exception as exc:
        # No SQL, passwords, encrypted payloads or arguments in the journal.
        print('Mailbox provisioning failed: '+type(exc).__name__)
        raise SystemExit(1)
