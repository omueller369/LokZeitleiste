#!/usr/bin/env python3
"""Root-only Linux host provisioning. Never executes database values as shell code."""
import argparse
import json
import os
import pwd
import re
import subprocess
from pathlib import Path

API_UID=10001
UID_BASE=200000


def run(args):
    subprocess.run(args,check=True,stdin=subprocess.DEVNULL)


def ensure_api_account():
    name='lz_api';marker='LokZeitleiste API'
    try:account=pwd.getpwuid(API_UID)
    except KeyError:account=None
    if account:
        if account.pw_name!=name or account.pw_gecos!=marker:
            raise RuntimeError('Host UID 10001 is already used by a different account')
        run(['usermod','--shell','/usr/sbin/nologin','--lock',name])
        return
    try:pwd.getpwnam(name)
    except KeyError:pass
    else:raise RuntimeError('Host account lz_api already exists with another UID')
    run(['useradd','--system','--uid',str(API_UID),'--user-group','--no-create-home','--home-dir','/nonexistent',
        '--shell','/usr/sbin/nologin','--password','!','--comment',marker,name])


def manifest(backend):
    files=['docker','compose','--project-directory',str(backend)]
    if (backend/'.env.test').is_file():files+=['--env-file',str(backend/'.env.test'),'-f',str(backend/'compose.test.yaml')]
    else:files+=['--env-file',str(backend/'.env'),'-f',str(backend/'compose.yaml')]
    result=subprocess.run(files+['exec','-T','api','python','-m','lokzeitleiste.documents.accounts'],check=True,capture_output=True,text=True)
    return json.loads(result.stdout)


def validate(root,record):
    user_id=record['id'];login=record['username'];category=record['category']
    if type(user_id) is not int or not 0<user_id<1000000000 or category not in ('TF','VW') or not re.fullmatch(r'[a-z0-9._-]{1,64}',login) or login in ('.','..'):
        raise ValueError('Invalid account manifest')
    path=root/category/login
    if (root/category).is_symlink() or path.is_symlink() or not path.is_dir() or not path.resolve().is_relative_to(root):
        raise ValueError('Invalid user directory')
    return user_id,path


def provision(root,record):
    user_id,path=validate(root,record);name=f'lz_u_{user_id}';uid=UID_BASE+user_id;marker=f'LokZeitleiste user {user_id}'
    try:account=pwd.getpwnam(name)
    except KeyError:account=None
    if account:
        if account.pw_uid!=uid or account.pw_gecos!=marker:
            raise RuntimeError(f'Account collision: {name}')
        if account.pw_dir!=str(path) or account.pw_shell!='/usr/sbin/nologin':
            run(['usermod','--home',str(path),'--shell','/usr/sbin/nologin',name])
        run(['usermod','--lock',name])
    else:
        try:pwd.getpwuid(uid)
        except KeyError:pass
        else:raise RuntimeError(f'UID collision: {uid}')
        run(['useradd','--system','--uid',str(uid),'--user-group','--no-create-home','--home-dir',str(path),
            '--shell','/usr/sbin/nologin','--password','!','--comment',marker,name])
    parents=[];parent=path.parent
    while parent!=parent.parent:
        parents.append(str(parent));parent=parent.parent
    run(['setfacl','-m',f'u:{uid}:--x','--']+parents)
    directories=[];files=[]
    for base,dirs,names in os.walk(path,followlinks=False):
        dirs[:]=[d for d in dirs if not (Path(base)/d).is_symlink()]
        directories.append(str(base))
        files += [str(Path(base)/n) for n in names if not (Path(base)/n).is_symlink() and (Path(base)/n).is_file()]
    for filename in directories+files:
        if os.lstat(filename).st_uid!=uid:os.chown(filename,uid,-1,follow_symlinks=False)
    for offset in range(0,len(directories),100):
        run(['setfacl','-m',f'u::rwx,u:{API_UID}:rwx,u:{uid}:rwx,g::---,m::rwx,o::---,d:u::rwx,d:u:{API_UID}:rwx,d:u:{uid}:rwx,d:g::---,d:m::rwx,d:o::---','--']+directories[offset:offset+100])
    for offset in range(0,len(files),100):
        run(['setfacl','-m',f'u::rw-,u:{API_UID}:rw-,u:{uid}:rw-,g::---,m::rw-,o::---','--']+files[offset:offset+100])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--backend',required=True,type=Path);args=parser.parse_args()
    if os.geteuid()!=0:raise SystemExit('Linux-Benutzeranlage benötigt root.')
    backend=args.backend.resolve()
    if not (backend/'compose.test.yaml').is_file():raise SystemExit('Ungültiges Backend-Verzeichnis.')
    ensure_api_account()
    for record in manifest(backend):provision(backend.parent,record)


if __name__=='__main__':main()
