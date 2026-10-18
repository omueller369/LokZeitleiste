import hashlib
import os
import re
import tempfile
from datetime import datetime
from pathlib import PurePosixPath,Path
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select

from ..models import DocumentFile, now_utc
from ..user_directories import user_path

MAX_FILE = 10 * 1024 * 1024


def today():
    return datetime.now(ZoneInfo('Europe/Berlin'))


def prepare_tree(user):
    root = user_path(user.username, user.role)
    root.mkdir(mode=0o770, exist_ok=True)
    if user.role == 'tf':
        folders = ['Arbeitsberichte/'+today().strftime('%Y-%m-%d'),
                   'Monatsabrechnung/'+today().strftime('%Y-%m'),
                   'Fahrpläne/Trassen', 'Fahrpläne/FPLO', 'Fahrpläne/Sonstiges']
    else:
        folders = ['Protokolle', 'Sonstiges']
    for folder in ['Dokumente']+['Dokumente/'+p for p in folders]:
        current = root
        for part in PurePosixPath(folder).parts:
            current = current/part
            if current.is_symlink():
                raise HTTPException(409, 'Ungültiger Dokumentpfad.')
            current.mkdir(mode=0o770, exist_ok=True)
    return root


def safe_path(user, relative, directory=False):
    if not isinstance(relative,str) or '\\' in relative or '\x00' in relative:
        raise HTTPException(422,'Ungültiger Dokumentpfad.')
    parts=PurePosixPath(relative).parts
    if PurePosixPath(relative).as_posix()!=relative or not parts or parts[0]!='Dokumente' or any(p in ('.','..') for p in relative.split('/')) or relative.startswith('/'):
        raise HTTPException(422,'Ungültiger Dokumentpfad.')
    root=prepare_tree(user);path=root
    for part in parts:
        path=path/part
        if path.is_symlink():raise HTTPException(409,'Ungültiger Dokumentpfad.')
    if not path.exists() or (directory and not path.is_dir()) or (not directory and not path.is_file()):
        raise HTTPException(404,'Dokument oder Verzeichnis nicht gefunden.')
    if not path.resolve().is_relative_to(root.resolve()):raise HTTPException(422,'Ungültiger Dokumentpfad.')
    return path


def clean_name(name):
    if not name or not name.strip() or name.startswith(('.upload-','.delete-')) or name in ('.','..') or '/' in name or '\\' in name or any(ord(c)<32 or ord(c)==127 for c in name) or len(name.encode('utf-8'))>200:
        raise HTTPException(422,'Ungültiger Dateiname.')
    return name


def write_atomic(path, content):
    fd,name=tempfile.mkstemp(prefix='.upload-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(content);stream.flush();os.fsync(stream.fileno());os.fchmod(stream.fileno(),0o660)
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


def generated(db,user,relative,content,source):
    root=prepare_tree(user)
    existing=db.scalar(select(DocumentFile).where(DocumentFile.owner_id==user.id,DocumentFile.source_key==source))
    if existing:relative=existing.relative_path
    parts=PurePosixPath(relative).parts
    if not parts or parts[0]!='Dokumente' or any(p in ('.','..') for p in parts):raise ValueError('Invalid archive path')
    current=root
    for part in parts[:-1]:
        current=current/part
        if current.is_symlink():raise HTTPException(409,'Ungültiger Dokumentpfad.')
        current.mkdir(mode=0o770,exist_ok=True)
    path=root/relative
    if path.is_symlink():raise HTTPException(409,'Ungültiger Dokumentpfad.')
    if path.exists() and not existing:
        from uuid import uuid4
        path=path.with_name(path.stem+'-system-'+uuid4().hex[:12]+path.suffix)
        relative=path.relative_to(root).as_posix()
    digest=hashlib.sha256(content).hexdigest()
    if existing and existing.sha256==digest and path.is_file():return existing
    write_atomic(path,content)
    row=existing or DocumentFile(owner_id=user.id,source_key=source,uploader_id=None)
    row.relative_path=relative;row.display_name=path.name;row.byte_size=len(content);row.sha256=digest;row.updated_at=now_utc()
    if not existing:db.add(row)
    return row


def tree(db,user,query=''):
    root=prepare_tree(user)
    records={r.relative_path:r for r in db.scalars(select(DocumentFile).where(DocumentFile.owner_id==user.id))}
    from ..i18n import translate
    folders=[];files=[];q=query.casefold().strip()
    for base,dirs,names in os.walk(root/'Dokumente',followlinks=False):
        dirs[:]=sorted(d for d in dirs if not (Path(base)/d).is_symlink())
        relative=Path(base).relative_to(root).as_posix();folders.append(relative)
        for name in sorted(names):
            path=Path(base)/name
            if name.startswith(('.upload-','.delete-')) or path.is_symlink() or not path.is_file():continue
            rel=path.relative_to(root).as_posix()
            if q and q not in rel.casefold() and q not in '/'.join(translate(part) for part in PurePosixPath(rel).parts).casefold():continue
            row=records.get(rel)
            files.append(dict(path=rel,name=row.display_name if row else name,size=path.stat().st_size,
                modified=datetime.fromtimestamp(path.stat().st_mtime,ZoneInfo('Europe/Berlin')).isoformat(),
                can_delete=bool(row and row.uploader_id==user.id and not row.source_key),generated=bool(row and row.source_key)))
    return dict(folders=folders,files=files)
