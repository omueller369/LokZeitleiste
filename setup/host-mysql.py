"""Prepare or back up the existing host database without exposing credentials."""
import getpass
import gzip
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import quote,unquote,urlsplit


def settings(path):
    if path.is_symlink():raise ValueError('Symlink als Konfiguration nicht zulässig')
    values=dict(line.split('=',1) for line in path.read_text().splitlines() if '=' in line and not line.startswith('#'))
    uri=urlsplit(values['DATABASE_URL'])
    database=uri.path.lstrip('/')
    if uri.hostname!='127.0.0.1' or uri.port!=3306 or not re.fullmatch(r'[a-zA-Z0-9_]{1,64}',database):raise ValueError('Ungültige Host-Datenbankkonfiguration')
    return unquote(uri.username),unquote(uri.password),database


def client_file(user,password):
    if any(c in user+password for c in '\r\n\x00'):raise ValueError('Ungültige Zugangsdaten')
    escape=lambda s:s.replace('\\','\\\\').replace('"','\\"')
    fd,name=tempfile.mkstemp(prefix='lokzeitleiste-mysql-')
    with os.fdopen(fd,'w') as out:
        out.write('[client]\nprotocol=tcp\nhost=127.0.0.1\nport=3306\nuser="'+escape(user)+'"\npassword="'+escape(password)+'"\n')
    return name


def prepare(path):
    path=Path(path)
    if path.exists():
        user,password,database=settings(path)
    else:
        user=input('MySQL-Benutzer [ctl-software]: ').strip() or 'ctl-software'
        database=input('Datenbank [ctl_software]: ').strip() or 'ctl_software'
        password=getpass.getpass('MySQL-Passwort: ')
    if not re.fullmatch(r'[a-zA-Z0-9_]{1,64}',database):raise ValueError('Datenbankname: nur Buchstaben, Ziffern und Unterstrich')
    config=client_file(user,password)
    try:
        subprocess.run(['mysql','--defaults-file='+config,'--batch','--execute',f'CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;'],check=True)
        subprocess.run(['mysql','--defaults-file='+config,'--database='+database,'--batch','--execute','SELECT 1'],check=True,stdout=subprocess.DEVNULL)
    finally:os.unlink(config)
    if not path.exists():
        # Percent encoding also protects Compose interpolation and URL parsing.
        url=f'mysql+pymysql://{quote(user,safe="")}:{quote(password,safe="")}@127.0.0.1:3306/{database}?charset=utf8mb4'
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as out:out.write('DATABASE_URL='+url+'\nPUBLIC_ORIGIN=http://ctl-software.io-goerlitz.eu\nCOOKIE_SECURE=false\n')
    path.chmod(0o600)
    print('Host-MySQL verbunden; vorhandene Tabellen bleiben erhalten.')


def backup(path,target):
    user,password,database=settings(Path(path));config=client_file(user,password)
    try:
        with tempfile.TemporaryFile() as raw:
            subprocess.run(['mysqldump','--defaults-file='+config,'--single-transaction','--no-tablespaces','--set-gtid-purged=OFF',database],check=True,stdout=raw)
            raw.seek(0)
            with gzip.open(target,'wb') as out:
                while chunk:=raw.read(1024*1024):out.write(chunk)
        Path(target).chmod(0o600)
    finally:os.unlink(config)


if __name__=='__main__':
    try:
        if sys.argv[1]=='prepare':prepare(sys.argv[2])
        elif sys.argv[1]=='backup':backup(sys.argv[2],sys.argv[3])
        else:raise ValueError('Unknown command')
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as error:
        raise SystemExit('Host-MySQL fehlgeschlagen. Verbindung/Benutzerrechte prüfen; keine Daten gelöscht. '+str(error))
