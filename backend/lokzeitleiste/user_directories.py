"""Persistent per-login document directories; no documents are moved into them yet."""
import argparse
import logging
import os
import re
from contextlib import contextmanager
from pathlib import Path

from fastapi import HTTPException

ROLE_DIRECTORIES = {'tf': 'TF', 'staff': 'VW', 'admin': 'VW'}
STORAGE_ERROR = 'Benutzerverzeichnis konnte nicht vorbereitet werden. Bitte die Serverkonfiguration prüfen.'


def storage_root():
    value = os.environ.get('LOKZEITLEISTE_FILES_ROOT')
    root = Path(value) if value else Path(__file__).resolve().parents[2]
    if not root.is_absolute():
        raise ValueError('LOKZEITLEISTE_FILES_ROOT muss ein absoluter Pfad sein.')
    return root.resolve()


def component(username):
    if username in ('.', '..') or not re.fullmatch(r'[a-z0-9._-]{1,64}', username):
        raise ValueError('Ungültiger Verzeichnisname.')
    return username


def private_directory(path):
    if path.is_symlink():
        raise ValueError('Symbolische Links sind als Benutzerverzeichnisse nicht zulässig.')
    created=not path.exists()
    path.mkdir(mode=0o700, exist_ok=True)
    if not path.is_dir() or path.is_symlink():
        raise ValueError('Benutzerpfad ist kein Verzeichnis.')
    if created:
        path.chmod(0o700)
    return path


def user_path(username, role):
    category = ROLE_DIRECTORIES[role]
    root = storage_root()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    parent = private_directory(root / category)
    path = parent / component(username)
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise ValueError('Benutzerpfad ist kein reguläres Verzeichnis.')
    return path


@contextmanager
def directory_transaction(user, previous_username=None, *, creating=False):
    """Provision before DB commit; undo an empty creation/rename if commit fails."""
    path = old = None
    created = moved = False
    try:
        path = user_path(user.username, user.role)
        if creating and path.exists():
            raise HTTPException(409, 'Benutzerverzeichnis ist bereits vergeben.')
        if previous_username and previous_username != user.username:
            old = user_path(previous_username, user.role)
            if old.exists():
                if path.exists():
                    raise ValueError('Zielverzeichnis existiert bereits; keine Dateien überschrieben.')
                old.rename(path)
                moved = True
        created = not moved and not path.exists()
        private_directory(path)
    except (OSError, ValueError, KeyError) as exc:
        if moved:
            path.rename(old)
        raise HTTPException(503, STORAGE_ERROR) from exc
    try:
        from .documents.storage import prepare_tree
        prepare_tree(user)
        yield path
    except BaseException:
        try:
            if moved:
                path.rename(old)
            elif created:
                for folder in sorted(path.rglob('*'),key=lambda p:len(p.parts),reverse=True):
                    if folder.is_dir() and not folder.is_symlink():
                        try:folder.rmdir()
                        except OSError:pass
                path.rmdir()  # Never remove a directory containing documents.
        except OSError:
            logging.getLogger(__name__).exception('Leeres Benutzerverzeichnis konnte nicht zurückgesetzt werden.')
        raise


def sync_user_directories(db):
    from sqlalchemy import select
    from .models import User
    count = 0
    for user in db.scalars(select(User).where(User.role.in_(ROLE_DIRECTORIES))):
        with directory_transaction(user):
            count += 1
    return count


def prepare_container_root():
    """One-shot Compose service; only the two mounted category roots are chowned."""
    if os.geteuid() != 0 or not os.environ.get('LOKZEITLEISTE_FILES_ROOT'):
        raise RuntimeError('Container-Vorbereitung benötigt root und LOKZEITLEISTE_FILES_ROOT.')
    root = storage_root()
    if root != Path('/user-files'):
        raise RuntimeError('Container-Vorbereitung ist ausschließlich für /user-files vorgesehen.')
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    for path in (root, root / 'TF', root / 'VW'):
        private_directory(path)
        if path.stat().st_uid != 10001:path.chmod(0o700)
        os.chown(path, 10001, 10001)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-container', action='store_true')
    args = parser.parse_args()
    if args.prepare_container:
        prepare_container_root()
    else:
        from sqlalchemy.orm import Session
        from .db import engine
        with Session(engine()) as db:
            print(f'{sync_user_directories(db)} Benutzerverzeichnisse vorbereitet.')


if __name__ == '__main__':
    main()
