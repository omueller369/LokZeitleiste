#!/usr/bin/env bash
# Full fresh Ubuntu 26.04 CTL test server. Never execute on an existing production host.
set -Eeuo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
script_file="$script_dir/$(basename -- "${BASH_SOURCE[0]}")"
resume=false
source_dir=''
while (($#));do
 case "$1" in
  --resume) resume=true;shift ;;
  --source) (($#>=2)) || { echo '--source benötigt einen Pfad.' >&2;exit 2; };source_dir=$2;shift 2 ;;
  --help|-h)
   echo 'sudo bash install-ctlsoftware-test.sh [--resume] [--source /Pfad/zum/Projekt]'
   echo 'Nur frisches Ubuntu 26.04! Installiert Apache, MariaDB, BIND, Postfix/Dovecot und CTL-Testdaten.'
   echo 'Domain: ctl-software.io-goerlitz.eu | IPv4: 212.227.86.251 | DB: db_ctl | Benutzer: dbo_ctl'
   echo 'Das neue Datenbankpasswort wird verdeckt abgefragt.'
   exit 0 ;;
  *) echo "Unbekannte Option: $1" >&2;exit 2 ;;
 esac
done
if ((EUID!=0));then
 args=();[[ $resume == false ]] || args+=(--resume);[[ -z $source_dir ]] || args+=(--source "$source_dir")
 exec sudo -- bash "$script_file" "${args[@]}"
fi
umask 022
. /etc/os-release
[[ ${ID:-} == ubuntu && ${VERSION_ID:-} == 26.04 ]] || { echo 'Frisches Ubuntu 26.04 wird benötigt.' >&2;exit 1; }
[[ ! -d /usr/local/ispconfig ]] || { echo 'ISPConfig vorhanden: diese Routine ist nur für einen frischen Server.' >&2;exit 1; }
state_dir=/etc/ctlsoftware-test-setup
[[ ! -L $state_dir ]] || { echo 'Symlink als Installationsstatus abgelehnt.' >&2;exit 1; }
if [[ $resume == false ]];then
 [[ -t 0 ]] || { echo 'Interaktive Konsole für das Datenbankpasswort erforderlich.' >&2;exit 1; }
 [[ ! -e $state_dir && ! -e /opt/ctlsoftware-test && ! -e /etc/ctlsoftware-test ]] || { echo 'Installationsziel vorhanden. Nur eigene unterbrochene Installation mit --resume fortsetzen.' >&2;exit 1; }
 [[ ! -d /var/lib/mysql/mysql && ! -f /etc/postfix/main.cf ]] || { echo 'Vorhandene Datenbank/Mailinstallation erkannt. Keine Änderung.' >&2;exit 1; }
 if command -v ss >/dev/null;then
  for port in 25 80 143 443 465 587 993 3306 18080;do
   [[ -z $(ss -Hltn "sport = :$port") ]] || { echo "Port $port ist belegt. Frischen Server verwenden." >&2;exit 1; }
  done
 fi
 install -d -m 0700 "$state_dir"
 printf '%s\n' 'ctlsoftware-test-fresh-v1' > "$state_dir/started"
 chmod 0600 "$state_dir/started"
else
 [[ -f $state_dir/started && $(cat "$state_dir/started") == ctlsoftware-test-fresh-v1 ]] || { echo 'Keine eigene begonnene Installation gefunden.' >&2;exit 1; }
fi
export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l
if ! command -v flock >/dev/null;then apt-get update;apt-get install -y --no-install-recommends util-linux;fi
exec 9>"$state_dir/install.lock"
flock -n 9 || { echo 'Eine Installation läuft bereits.' >&2;exit 1; }
export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l
if ! command -v python3 >/dev/null;then apt-get update;apt-get install -y --no-install-recommends python3;fi
if [[ -z $source_dir && -f $script_dir/backend/requirements.txt ]];then source_dir=$script_dir;fi
work_dir=$(mktemp -d)
trap 'rm -rf -- "$work_dir"' EXIT
cat > "$work_dir/ispconfig_app.py" <<'CTL_FRESH_APP_HELPER'
"""Application-side setup checks, executed with the application's virtualenv/user."""
import json
import sys
from sqlalchemy import inspect
from sqlalchemy.orm import Session
from lokzeitleiste.db import engine


def main():
    mode=sys.argv[1]
    if mode=='empty':
        try:
            with engine().connect() as connection:
                schema=inspect(connection)
                if schema.get_table_names() or schema.get_view_names():
                    raise SystemExit('Datenbank ist nicht leer. Neuinstallation abgebrochen; keine Tabellen verändert.')
        except SystemExit:raise
        except Exception as exc:raise SystemExit('Datenbankverbindung fehlgeschlagen ('+type(exc).__name__+'). Zugang/Host und Rechte in ISPConfig prüfen.') from None
        print('Vorhandene ISPConfig-Datenbank verbunden und leer.')
    elif mode=='verify':
        from sqlalchemy import select,func
        from lokzeitleiste.models import User,ProfilePhoto
        with Session(engine()) as db:
            drivers=db.scalar(select(func.count()).select_from(User).where(User.role=='tf'))
            photos=db.scalar(select(func.count()).select_from(ProfilePhoto).join(User,User.id==ProfilePhoto.user_id).where(User.role=='tf'))
            if drivers!=20 or photos!=20:raise SystemExit('Testdatenprüfung fehlgeschlagen: 20 TF mit Bildern erwartet.')
            print(json.dumps({'tf':drivers,'fotos':photos}))
    else:raise SystemExit('Unbekannter Prüfmodus')

if __name__=='__main__':main()
CTL_FRESH_APP_HELPER
cat > "$work_dir/ispconfig_install.py" <<'CTL_FRESH_ENGINE'
"""Install only LokZeitleiste into an existing Ubuntu/ISPConfig stack. No apt/Docker/vhost edits."""
import argparse
import base64
import fcntl
import getpass
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
from urllib.parse import quote,urlsplit
from urllib.request import urlopen

SOURCE=Path(os.environ.get('CTL_INSTALL_SOURCE',str(Path(__file__).resolve().parents[1]))).resolve()
APP_HELPER=Path(os.environ.get('CTL_INSTALL_HELPER',str(SOURCE/'setup/ispconfig_app.py')))
INSTALL=Path('/opt/lokzeitleiste-ispconfig')
CONFIG=Path('/etc/lokzeitleiste-ispconfig')
DATA=Path('/var/lib/lokzeitleiste-ispconfig')
ACCOUNT='lokzeitleiste-ispconfig'
SERVICE='lokzeitleiste-ispconfig'
UNIT_DIR=Path('/etc/systemd/system')


def database_url(host,port,name,user,password):
    if not re.fullmatch(r'[A-Za-z0-9_]{1,64}',name):raise ValueError('Datenbankname: nur Buchstaben, Ziffern und Unterstrich, maximal 64 Zeichen.')
    if not re.fullmatch(r'[A-Za-z0-9.-]+',host):raise ValueError('Ungültiger Datenbankhost. Für lokalen MySQL 127.0.0.1 verwenden.')
    if not user or any(c in user+password for c in '\r\n\x00'):raise ValueError('Ungültiger Datenbankzugang.')
    if not 1<=int(port)<=65535:raise ValueError('Ungültiger Datenbankport.')
    return f'mysql+pymysql://{quote(user,safe="")}:{quote(password,safe="")}@{host}:{port}/{name}?charset=utf8mb4'


def origin(domain,http=False):
    if not re.fullmatch(r'(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?',domain) or '..' in domain:
        raise ValueError('Domain ohne Protokoll/Pfad angeben, z. B. ctl-software.io-goerlitz.eu.')
    return ('http' if http else 'https')+'://'+domain.lower()


def env_file(values):
    # systemd EnvironmentFile supports quoted values; this file is never sourced by a shell.
    def escape(value):
        if any(c in value for c in '\r\n\x00'):raise ValueError('Zeilenumbrüche in Konfiguration nicht zulässig.')
        return value.replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$')
    return ''.join(f'{key}="{escape(str(value))}"\n' for key,value in values.items())


def unit(port,worker=False):
    command=(f'{INSTALL}/venv/bin/python -m lokzeitleiste.reports.worker' if worker else
             f'{INSTALL}/venv/bin/python -m uvicorn lokzeitleiste.main:app --host 127.0.0.1 --port {port} --proxy-headers --forwarded-allow-ips 127.0.0.1')
    dependency=f'After=network.target {SERVICE}.service\nRequires={SERVICE}.service' if worker else 'After=network.target'
    return f'''# Managed by LokZeitleiste application-only ISPConfig setup
[Unit]
Description=LokZeitleiste {'background worker' if worker else 'API for ISPConfig'}
{dependency}

[Service]
Type=simple
User={ACCOUNT}
Group={ACCOUNT}
WorkingDirectory={INSTALL}/backend
EnvironmentFile={CONFIG}/app.env
ExecStart={command}
Restart=on-failure
RestartSec=5
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ReadWritePaths={DATA}

[Install]
WantedBy=multi-user.target
'''


def proxy_config(port,webserver,http=False):
    if webserver=='apache':
        return f'''# ISPConfig: Website -> Optionen -> Apache-Direktiven
# Nur für diese Website. Keine neue VirtualHost-Konfiguration anlegen.
ProxyRequests Off
ProxyPreserveHost On
RequestHeader set X-Forwarded-Proto "{'http' if http else 'https'}"
LimitRequestBody 33554432
ProxyPass /.well-known/acme-challenge/ !
ProxyPass / http://127.0.0.1:{port}/ connectiontimeout=5 timeout=180
ProxyPassReverse / http://127.0.0.1:{port}/
'''
    return f'''# ISPConfig: Website -> Optionen -> nginx-Direktiven
# Dieser Block ersetzt die bestehende Root-location, nicht daneben duplizieren.
# Längere vorhandene ACME-locations beibehalten.
client_max_body_size 32m;
location ^~ / {{
    proxy_pass http://127.0.0.1:{port};
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_connect_timeout 5s;
    proxy_read_timeout 180s;
}}
'''


def existing_site(domain,webserver,directory=None):
    directory=Path(directory) if directory is not None else Path('/etc/apache2/sites-enabled' if webserver=='apache' else '/etc/nginx/sites-enabled')
    pattern=r'^\s*Server(?:Name|Alias)\s+([^#\n]+)' if webserver=='apache' else r'^\s*server_name\s+([^;#\n]+)'
    for path in directory.glob('*'):
        if not path.is_file():continue
        try:content=path.read_text(errors='replace')
        except OSError:continue
        if any(domain.lower() in line.lower().split() for line in re.findall(pattern,content,re.MULTILINE)):return True
    return False


def preflight(args):
    problems=[]
    if sys.version_info<(3,11):problems.append('Python >=3.11 wird benötigt.')
    try:ubuntu='ID=ubuntu' in Path('/etc/os-release').read_text().replace('"','')
    except OSError:ubuntu=False
    if not ubuntu:problems.append('Diese Routine ist für Ubuntu vorgesehen.')
    for module in ('venv','ensurepip'):
        if importlib.util.find_spec(module) is None:problems.append('Python-Modul '+module+' fehlt; Python/venv durch Serveradministration bereitstellen.')
    for command in ('systemctl','useradd'):
        if not shutil.which(command):problems.append(command+' fehlt.')
    if not Path('/run/systemd/system').is_dir():problems.append('Laufendes systemd wird benötigt.')
    if not getattr(args,'standalone',False) and not Path('/usr/local/ispconfig').is_dir():problems.append('Bestehende ISPConfig-Installation unter /usr/local/ispconfig nicht gefunden.')
    if args.webserver=='apache':
        apache=shutil.which('apache2ctl')
        if not apache:problems.append('Vorhandener Apache wurde nicht gefunden; --webserver nginx verwenden, falls nginx eingerichtet ist.')
        elif os.geteuid()==0:
            loaded=subprocess.run([apache,'-M'],capture_output=True,text=True)
            if loaded.returncode:problems.append('Apache-Modulprüfung fehlgeschlagen.')
            for module in ('proxy_module','proxy_http_module','headers_module'):
                if module not in loaded.stdout:problems.append('Apache-Modul '+module+' muss durch Serveradministration aktiviert sein.')
    elif not shutil.which('nginx'):problems.append('Vorhandener nginx wurde nicht gefunden.')
    if not args.resume:
        with socket.socket() as sock:
            try:sock.bind(('127.0.0.1',args.port))
            except OSError:problems.append('Loopback-Port '+str(args.port)+' ist belegt. Anderen --port wählen.')
    for name in (SERVICE,SERVICE+'-worker'):
        path=UNIT_DIR/(name+'.service')
        if path.is_symlink() or (path.exists() and not path.read_text().startswith('# Managed by LokZeitleiste application-only ISPConfig setup')):
            problems.append('Fremde systemd-Unit wird nicht überschrieben: '+str(path))
    if getattr(args,'require_existing_site',False) and not existing_site(args.domain,args.webserver):
        problems.append('Die Subdomain wurde in keiner aktiven Website-Konfiguration gefunden. Zuerst in ISPConfig anlegen/aktivieren.')
    if not (SOURCE/'backend/lokzeitleiste/accounts/demo_tf/people.json').is_file():problems.append('Vollständiger Repository-Checkout mit TF-Testdaten erforderlich.')
    if problems:raise ValueError('\n'.join(problems)+'\nEs wurden keine Serverpakete installiert.')


def private_write(path,text):
    if path.is_symlink():raise ValueError('Symlink als Konfigurationsdatei nicht zulässig: '+str(path))
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as stream:stream.write(text)
    path.chmod(0o600)


def run_application(arguments,env,account,input=None,capture=False):
    return subprocess.run([str(INSTALL/'venv/bin/python'),*arguments],cwd=INSTALL/'backend',env={**os.environ,**env},
                          user=account.pw_uid,group=account.pw_gid,extra_groups=[],input=input,text=True,
                          capture_output=capture,check=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--standalone',action='store_true',help='Anwendung für den eigenständigen Ubuntu-Testserver einrichten')
    parser.add_argument('--db-password-file',help='Root-private Passwortdatei für eingebettete Serverinstallation')
    parser.add_argument('--domain',help='In ISPConfig angelegte Domain, ohne Protokoll')
    parser.add_argument('--webserver',choices=('apache','nginx'),default='apache')
    parser.add_argument('--http',action='store_true',help='HTTP statt des standardmäßigen HTTPS verwenden')
    parser.add_argument('--port',type=int,default=18080,help='Freier interner API-Port, Standard 18080')
    parser.add_argument('--db-host',default='127.0.0.1')
    parser.add_argument('--db-port',type=int,default=3306)
    parser.add_argument('--db-name',help='Exakter ISPConfig-Datenbankname inklusive Präfix')
    parser.add_argument('--db-user',help='Exakter ISPConfig-Datenbankbenutzer inklusive Präfix')
    parser.add_argument('--admin-user',default='admin')
    parser.add_argument('--check',action='store_true',help='Nur lokale Voraussetzungen prüfen; keine Änderungen/Passwortabfrage')
    parser.add_argument('--require-existing-site',action='store_true',help='Aktiven VirtualHost der vorhandenen Subdomain prüfen')
    parser.add_argument('--resume',action='store_true',help='Nur eigene unterbrochene Neuinstallation fortsetzen')
    args=parser.parse_args()
    if args.standalone:
        global INSTALL,CONFIG,DATA,ACCOUNT,SERVICE
        INSTALL=Path('/opt/ctlsoftware-test');CONFIG=Path('/etc/ctlsoftware-test');DATA=Path('/var/lib/ctlsoftware-test')
        ACCOUNT=SERVICE='ctlsoftware-test'
    if args.require_existing_site and not args.domain and not args.resume:parser.error('--domain für die Website-Prüfung angeben.')
    if not 1024<=args.port<=65535:parser.error('--port muss zwischen 1024 und 65535 liegen.')
    if not re.fullmatch(r'[a-z0-9._-]{3,64}',args.admin_user):parser.error('Ungültiger --admin-user.')
    if args.domain:origin(args.domain,args.http)
    if not args.check and os.geteuid()!=0:parser.error('Mit sudo ausführen.')
    state_file=CONFIG/'installation.json'
    state=None
    if args.resume:
        if not state_file.is_file() or state_file.is_symlink():raise ValueError('Keine eigene unterbrochene Installation gefunden.')
        state=json.loads(state_file.read_text())
        if state.get('complete'):raise ValueError('Installation bereits vollständig. --resume ist keine Update-Routine.')
        args.domain=state['domain'];args.port=state['port'];args.http=state['http'];args.webserver=state['webserver'];args.admin_user=state['admin_user']
    preflight(args)
    if args.check:
        print('Lokale Voraussetzungen erfüllt. Keine Änderungen durchgeführt. Datenbankzugang wird bei der Installation geprüft.');return
    if not args.resume and not (args.domain and args.db_name and args.db_user):parser.error('--domain, --db-name und --db-user angeben.')
    for folder in (INSTALL,CONFIG,DATA):
        if folder.exists() and not args.resume:raise ValueError('Ziel bereits vorhanden: '+str(folder)+'. Bestehende Installation bleibt unverändert.')
        if folder.is_symlink():raise ValueError('Symlink als Installationsziel nicht zulässig.')
    password=None
    if not args.resume:
        if args.db_password_file:
            secret=Path(args.db_password_file)
            if secret.is_symlink() or secret.stat().st_uid!=0 or secret.stat().st_mode&0o077:raise ValueError('Passwortdatei muss root gehören und darf nur für root lesbar sein.')
            password=secret.read_text()
        else:password=getpass.getpass('Passwort des vorhandenen ISPConfig-Datenbankbenutzers: ')
        if not password:raise ValueError('Datenbankpasswort darf nicht leer sein.')
        dburl=database_url(args.db_host,args.db_port,args.db_name,args.db_user,password)
    os.umask(0o022)
    # A non-login application account is separate from ISPConfig web users.
    try:
        account=pwd.getpwnam(ACCOUNT)
        if account.pw_uid>=1000 or account.pw_shell not in ('/usr/sbin/nologin','/sbin/nologin'):raise ValueError('Vorhandenes Anwendungskonto hat unerwartete Eigenschaften.')
    except KeyError:
        subprocess.run(['useradd','--system','--user-group','--home-dir',str(DATA),'--no-create-home','--shell','/usr/sbin/nologin',ACCOUNT],check=True)
        account=pwd.getpwnam(ACCOUNT)
    INSTALL.mkdir(mode=0o755,exist_ok=True);CONFIG.mkdir(mode=0o700,exist_ok=True);DATA.mkdir(mode=0o700,exist_ok=True)
    os.chown(DATA,account.pw_uid,account.pw_gid)
    with open(CONFIG/'install.lock','w') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('Eine Installation läuft bereits.') from None
        if not args.resume:
            env={'DATABASE_URL':dburl,'PUBLIC_ORIGIN':origin(args.domain,args.http),'COOKIE_SECURE':'false' if args.http else 'true',
                 'LOKZEITLEISTE_FILES_ROOT':str(DATA/'files'),'MAILBOX_ENCRYPTION_KEY':base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
                 'SMTP_HOST':'','SMTP_FROM':'','WORK_REPORT_RECEIPT_EMAIL':'','PYTHONPATH':str(INSTALL/'backend'),'PYTHONDONTWRITEBYTECODE':'1','PYTHONUNBUFFERED':'1'}
            private_write(CONFIG/'environment.json',json.dumps(env))
            private_write(CONFIG/'app.env',env_file(env))
            private_write(CONFIG/'admin-initial-password',secrets.token_urlsafe(24)+'\n')
            state=dict(domain=args.domain,port=args.port,http=args.http,webserver=args.webserver,admin_user=args.admin_user,db_checked=False,complete=False)
            private_write(state_file,json.dumps(state))
        else:env=json.loads((CONFIG/'environment.json').read_text())
        backend=INSTALL/'backend';backend.mkdir(exist_ok=True)
        shutil.copytree(SOURCE/'backend/lokzeitleiste',backend/'lokzeitleiste',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        # Checkout permissions may come from a restrictive root umask. Code is not secret.
        for path in (backend/'lokzeitleiste',*(backend/'lokzeitleiste').rglob('*')):
            path.chmod(0o755 if path.is_dir() else 0o644)
        shutil.copy2(SOURCE/'backend/requirements.txt',INSTALL/'requirements.txt')
        shutil.copy2(APP_HELPER,INSTALL/'ispconfig_app.py')
        (INSTALL/'ispconfig_app.py').chmod(0o644)
        if not (INSTALL/'venv/bin/python').exists():subprocess.run([sys.executable,'-m','venv',str(INSTALL/'venv')],check=True)
        subprocess.run([str(INSTALL/'venv/bin/python'),'-m','pip','install','--disable-pip-version-check','-r',str(INSTALL/'requirements.txt')],check=True)
        helper=str(INSTALL/'ispconfig_app.py')
        if not state['db_checked']:
            run_application([helper,'empty'],env,account)
            state['db_checked']=True;private_write(state_file,json.dumps(state))
        run_application(['-m','lokzeitleiste.init_db'],env,account)
        run_application(['-m','lokzeitleiste.bootstrap_admin',args.admin_user],env,account,input=(CONFIG/'admin-initial-password').read_text())
        try:
            result=run_application(['-m','lokzeitleiste.accounts.import_demo_tf','--seed','23'],env,account,capture=True)
        except subprocess.CalledProcessError as exc:
            private_write(CONFIG/'demo-import-error.log',(exc.stderr or '')+'\n'+(exc.stdout or ''))
            raise ValueError('TF-Import fehlgeschlagen. Details: sudo cat '+str(CONFIG/'demo-import-error.log')) from None
        private_write(CONFIG/'demo-tf.json',result.stdout)
        run_application([helper,'verify'],env,account)
        private_write(CONFIG/'ispconfig-directives.conf',proxy_config(args.port,args.webserver,args.http))
        for name,worker in ((SERVICE,False),(SERVICE+'-worker',True)):
            path=UNIT_DIR/(name+'.service')
            if path.exists() and not path.read_text().startswith('# Managed by LokZeitleiste application-only ISPConfig setup'):raise ValueError('Fremde systemd-Unit wird nicht überschrieben: '+str(path))
            path.write_text(unit(args.port,worker));path.chmod(0o644)
        subprocess.run(['systemctl','daemon-reload'],check=True)
        subprocess.run(['systemctl','enable',SERVICE+'.service',SERVICE+'-worker.service'],check=True)
        subprocess.run(['systemctl','restart',SERVICE+'.service',SERVICE+'-worker.service'],check=True)
        for attempt in range(30):
            try:
                with urlopen(f'http://127.0.0.1:{args.port}/health',timeout=2) as response:
                    if response.status==200:break
            except OSError:time.sleep(1)
        else:raise ValueError('API nicht erreichbar. sudo journalctl -u '+SERVICE+' -n 100 prüfen; danach --resume möglich.')
        subprocess.run(['systemctl','is-active','--quiet',SERVICE+'.service',SERVICE+'-worker.service'],check=True)
        state['complete']=True;private_write(state_file,json.dumps(state))
        print('\nAnwendung und 20 Test-TF mit Bildern installiert. API: http://127.0.0.1:'+str(args.port))
        if not args.standalone:print('In ISPConfig noch die Website-Weiterleitung eintragen: sudo cat '+str(CONFIG/'ispconfig-directives.conf'))
        print('Danach öffentlich prüfen: '+origin(args.domain,args.http)+'/health')
        print('Backend: '+origin(args.domain,args.http)+'/admin/start | TF: '+origin(args.domain,args.http)+'/tf')
        print('Admin: '+args.admin_user+' | Passwortdatei: sudo cat '+str(CONFIG/'admin-initial-password'))
        print('TF-Liste: sudo cat '+str(CONFIG/'demo-tf.json')+' | Initialpasswort: tomcom123456 (Wechsel beim ersten Login).')
        print('Anwendung installiert; das äußere Server-Setup ergänzt Apache und Email.' if args.standalone else 'Echter Emailversand ist für diese Testinstallation deaktiviert.')

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,subprocess.CalledProcessError) as exc:
        print('FEHLER: '+str(exc),file=sys.stderr)
        print('Keine Datenbank gelöscht. Bei unterbrochener eigener Installation: sudo bash setup-ispconfig.sh --resume',file=sys.stderr)
        sys.exit(1)
CTL_FRESH_ENGINE
cat > "$work_dir/fresh_ubuntu.py" <<'CTL_FRESH_SERVER'
"""Fresh Ubuntu 26.04 server installer; rendered into install-ctlsoftware-test.sh."""
import argparse
import base64
import getpass
import grp
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import shutil
import smtplib
import socket
import sqlite3
import ssl
import subprocess
import sys
import time
import imaplib

DOMAIN='ctl-software.io-goerlitz.eu'
IP='212.227.86.251'
FORWARD='omueller369@gmail.com'
MAIL_USERS=('info','diso','vkplanung','railpool')
MAIL_PASSWORD='tomcom123456'
DB_NAME='db_ctl'
DB_USER='dbo_ctl'
STATE=Path('/etc/ctlsoftware-test-setup')
APP_CONFIG=Path('/etc/ctlsoftware-test')
MARKER='# Managed by install-ctlsoftware-test.sh\n'
PACKAGES=('apache2','mariadb-server','postfix','postfix-pcre','dovecot-core','dovecot-imapd',
          'dovecot-lmtpd','dovecot-sieve','bind9','bind9-utils','dnsutils','opendkim','opendkim-tools',
          'postsrsd','certbot','python3-venv','python3-pip','python3-pymysql','git','ca-certificates',
          'fonts-dejavu-core','openssl','ufw','rsyslog','curl','iproute2','openssh-server','php-fpm','php-cli','php-mysql','php-mbstring','php-xml',
          'php-curl','php-zip','php-gd','php-intl','php-sqlite3','phpmyadmin','roundcube-core',
          'dbconfig-no-thanks')


def run(args,**kwargs):
    return subprocess.run(args,check=True,**kwargs)


def output(args):return run(args,capture_output=True,text=True).stdout.strip()


def write(path,content,mode=0o644):
    path=Path(path)
    if path.is_symlink():raise ValueError('Symlink als Konfigurationsziel abgelehnt: '+str(path))
    path.parent.mkdir(parents=True,exist_ok=True)
    # Preserve the initial package config before replacing it; no backup contains CLI secrets.
    backup=STATE/'original-configs'/path.relative_to('/')
    if path.exists() and not backup.exists():
        backup.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,backup);backup.chmod(0o600)
    fd=os.open(path,os.O_CREAT|os.O_TRUNC|os.O_WRONLY,mode)
    with os.fdopen(fd,'w') as stream:stream.write(content)
    path.chmod(mode)


def dovecot_config():
    return f'''dovecot_config_version = 2.4.0
dovecot_storage_version = 2.4.0
# Managed by install-ctlsoftware-test.sh; Dovecot 2.4 syntax.
protocols {{
  imap = yes
  lmtp = yes
}}
listen = *
auth_mechanisms = plain login
auth_allow_cleartext = no
auth_username_format = %{{user | lower}}
ssl = required
ssl_min_protocol = TLSv1.2
ssl_server_cert_file = /etc/letsencrypt/live/{DOMAIN}/fullchain.pem
ssl_server_key_file = /etc/letsencrypt/live/{DOMAIN}/privkey.pem
mail_driver = maildir
mail_path = ~/Maildir
passdb passwd-file {{
  passwd_file_path = /etc/dovecot/ctl-users
}}
userdb passwd-file {{
  passwd_file_path = /etc/dovecot/ctl-users
}}
namespace inbox {{
  inbox = yes
  separator = /
}}
service imap-login {{
  inet_listener imap {{
    port = 143
  }}
  inet_listener imaps {{
    port = 993
    ssl = yes
  }}
}}
service auth {{
  unix_listener /var/spool/postfix/private/auth {{
    mode = 0660
    user = postfix
    group = postfix
  }}
}}
service lmtp {{
  unix_listener /var/spool/postfix/private/dovecot-lmtp {{
    mode = 0600
    user = postfix
    group = postfix
  }}
}}
protocol lmtp {{
  postmaster_address = info@{DOMAIN}
  mail_plugins {{
    sieve = yes
  }}
}}
sieve_script ctl_forward {{
  type = before
  driver = file
  path = /etc/dovecot/sieve/ctl-forward.sieve
}}
'''


def postfix_config():
    return MARKER+f'''compatibility_level = 3.6
myhostname = {DOMAIN}
mydomain = {DOMAIN}
myorigin = $mydomain
mydestination = localhost.localdomain, localhost
inet_interfaces = all
inet_protocols = ipv4
mynetworks = 127.0.0.0/8
relay_domains =
relayhost =
virtual_mailbox_domains = {DOMAIN}
virtual_mailbox_maps = hash:/etc/postfix/ctl-mailboxes
virtual_alias_maps = hash:/etc/postfix/ctl-aliases
virtual_transport = lmtp:unix:private/dovecot-lmtp
smtpd_relay_restrictions = permit_mynetworks, permit_sasl_authenticated, reject_unauth_destination
smtpd_recipient_restrictions = reject_unlisted_recipient
smtpd_sasl_type = dovecot
smtpd_sasl_path = private/auth
smtpd_sasl_auth_enable = no
smtpd_sasl_security_options = noanonymous
smtpd_tls_cert_file = /etc/letsencrypt/live/{DOMAIN}/fullchain.pem
smtpd_tls_key_file = /etc/letsencrypt/live/{DOMAIN}/privkey.pem
smtpd_tls_security_level = may
smtpd_tls_auth_only = yes
smtpd_tls_mandatory_protocols = >=TLSv1.2
smtp_tls_security_level = may
smtp_tls_CApath = /etc/ssl/certs
smtp_address_preference = ipv4
smtpd_milters = inet:127.0.0.1:8891
non_smtpd_milters = $smtpd_milters
milter_default_action = tempfail
milter_protocol = 6
sender_canonical_maps = socketmap:inet:127.0.0.1:10003:forward
sender_canonical_classes = envelope_sender
recipient_canonical_maps = socketmap:inet:127.0.0.1:10003:reverse
recipient_canonical_classes = envelope_recipient
message_size_limit = 41943040
mailbox_size_limit = 0
recipient_delimiter = +
'''


def postfix_submission():
    return '''\n# CTL authenticated submission; port 25 remains non-relaying.
submission inet n - y - - smtpd
  -o syslog_name=postfix/submission
  -o smtpd_tls_security_level=encrypt
  -o smtpd_sasl_auth_enable=yes
  -o smtpd_relay_restrictions=permit_sasl_authenticated,reject
  -o milter_macro_daemon_name=ORIGINATING
submissions inet n - y - - smtpd
  -o syslog_name=postfix/submissions
  -o smtpd_tls_wrappermode=yes
  -o smtpd_sasl_auth_enable=yes
  -o smtpd_relay_restrictions=permit_sasl_authenticated,reject
  -o milter_macro_daemon_name=ORIGINATING
'''


def bind_zone(dkim,serial):
    return f'''$TTL 300
@ IN SOA ns1.{DOMAIN}. info.{DOMAIN}. (
 {serial} 3600 900 1209600 300 )
@ IN NS ns1.{DOMAIN}.
@ IN A {IP}
ns1 IN A {IP}
@ IN MX 10 {DOMAIN}.
@ IN TXT "v=spf1 ip4:{IP} -all"
_dmarc IN TXT "v=DMARC1; p=none; rua=mailto:info@{DOMAIN}"
{dkim}
'''


def apache_config(tls=False,php_version="8.5"):
    acme=f'''Alias /.well-known/acme-challenge/ /var/www/ctlsoftware-test-acme/.well-known/acme-challenge/
<Directory /var/www/ctlsoftware-test-acme>
  Require all granted
</Directory>'''
    if not tls:return MARKER+f'''<VirtualHost *:80>
ServerName {DOMAIN}
DocumentRoot /var/www/ctlsoftware-test-acme
{acme}
</VirtualHost>
'''
    return MARKER+f'''<VirtualHost *:80>
ServerName {DOMAIN}
{acme}
RewriteEngine On
RewriteCond %{{REQUEST_URI}} !^/\\.well-known/acme-challenge/
RewriteRule ^ https://{DOMAIN}%{{REQUEST_URI}} [R=301,L,NE]
</VirtualHost>
<VirtualHost *:443>
ServerName {DOMAIN}
SSLEngine On
SSLCertificateFile /etc/letsencrypt/live/{DOMAIN}/fullchain.pem
SSLCertificateKeyFile /etc/letsencrypt/live/{DOMAIN}/privkey.pem
SSLProtocol all -SSLv3 -TLSv1 -TLSv1.1
ProxyRequests Off
ProxyPreserveHost On
RequestHeader set X-Forwarded-Proto "https"
LimitRequestBody 33554432
ProxyPass /.well-known/acme-challenge/ !
ProxyPass /phpmyadmin !
ProxyPass /webmailer !
Alias /phpmyadmin /usr/share/phpmyadmin
Alias /webmailer /var/lib/roundcube/public_html
<Directory /usr/share/phpmyadmin>
  Options -Indexes +FollowSymLinks
  DirectoryIndex index.php
  Require all granted
  <FilesMatch "\\.php$">
    SetHandler "proxy:unix:/run/php/php{php_version}-fpm.sock|fcgi://localhost"
  </FilesMatch>
</Directory>
<Directory /var/lib/roundcube/public_html>
  Options -Indexes +FollowSymLinks
  AllowOverride All
  DirectoryIndex index.php
  Require all granted
  <FilesMatch "\\.php$">
    SetHandler "proxy:unix:/run/php/php{php_version}-fpm.sock|fcgi://localhost"
  </FilesMatch>
</Directory>
<LocationMatch "^/(phpmyadmin/(setup|libraries|templates)|webmailer/(config|temp|logs|SQL|installer))(/|$)">
  Require all denied
</LocationMatch>
ProxyPass / http://127.0.0.1:18080/ connectiontimeout=5 timeout=180
ProxyPassReverse / http://127.0.0.1:18080/
{acme}
</VirtualHost>
'''


def prepare_packages():
    env={**os.environ,'DEBIAN_FRONTEND':'noninteractive','NEEDRESTART_MODE':'l'}
    run(['debconf-set-selections'],input=f'postfix postfix/mailname string {DOMAIN}\npostfix postfix/main_mailer_type select Internet Site\nphpmyadmin phpmyadmin/dbconfig-install boolean false\nphpmyadmin phpmyadmin/reconfigure-webserver multiselect\nroundcube-core roundcube/dbconfig-install boolean false\nroundcube-core roundcube/reconfigure-webserver multiselect\n',text=True)
    run(['dpkg','--force-confold','--configure','-a'],env=env)
    run(['apt-get','update'],env=env)
    run(['apt-get','install','-y','--no-install-recommends','-o','Dpkg::Options::=--force-confold',*PACKAGES],env=env)
    if not output(['dovecot','--version']).startswith('2.4.'):
        raise ValueError('Dovecot 2.4 aus Ubuntu 26.04 erwartet; keine alte Syntax wird geschrieben.')
    for service in ('postfix','dovecot','opendkim','postsrsd'):
        run(['systemctl','stop',service])


def prepare_hostname():
    run(['hostnamectl','set-hostname',DOMAIN])
    write('/etc/mailname',DOMAIN+'\n')


def prepare_firewall():
    ssh=output(['sshd','-T'])
    ports=[line.split()[1] for line in ssh.splitlines() if line.startswith('port ')]
    if not ports:raise ValueError('SSH-Port nicht ermittelt. Firewall wird nicht aktiviert.')
    for port in ports:run(['ufw','allow',port+'/tcp'])
    for port in (25,53,80,143,443,465,587,993):run(['ufw','allow',str(port)+'/tcp'])
    run(['ufw','allow','53/udp'])
    run(['ufw','default','deny','incoming']);run(['ufw','default','allow','outgoing'])
    run(['ufw','--force','enable'])


def prepare_database():
    import pymysql
    write('/etc/mysql/mariadb.conf.d/60-ctlsoftware-test.cnf','[mysqld]\nbind-address=127.0.0.1\nmax_allowed_packet=64M\ncharacter-set-server=utf8mb4\ncollation-server=utf8mb4_unicode_ci\n')
    run(['systemctl','enable','--now','mariadb']);run(['systemctl','restart','mariadb'])
    password=(STATE/'database-password').read_text()
    with pymysql.connect(unix_socket='/run/mysqld/mysqld.sock',user='root',charset='utf8mb4',autocommit=True) as db:
        with db.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s",(DB_NAME,))
            if cursor.fetchone()[0]:raise ValueError('db_ctl enthält bereits Tabellen. Es wird nichts gelöscht.')
            cursor.execute('CREATE DATABASE IF NOT EXISTS db_ctl CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
            for host in ('localhost','127.0.0.1'):
                cursor.execute('CREATE USER IF NOT EXISTS %s@%s IDENTIFIED BY %s',(DB_USER,host,password))
                cursor.execute('ALTER USER %s@%s IDENTIFIED BY %s',(DB_USER,host,password))
                cursor.execute('GRANT ALL PRIVILEGES ON db_ctl.* TO %s@%s',(DB_USER,host))


def phpmyadmin_config(secret):
    return "<?php\n"+f"$cfg['blowfish_secret'] = '{secret}';\n"+"""$cfg['Servers'] = [];
$cfg['Servers'][1]['auth_type'] = 'cookie';
$cfg['Servers'][1]['host'] = '127.0.0.1';
$cfg['Servers'][1]['AllowRoot'] = false;
$cfg['Servers'][1]['AllowNoPassword'] = false;
$cfg['AllowArbitraryServer'] = false;
$cfg['ForceSSL'] = true;
"""


def roundcube_config(secret):
    return f"""<?php
$config['db_dsnw'] = 'sqlite:////var/lib/ctl-webmail/roundcube.sqlite?mode=0640';
$config['imap_host'] = 'ssl://{DOMAIN}:993';
$config['smtp_host'] = 'ssl://{DOMAIN}:465';
$config['smtp_user'] = '%u';
$config['smtp_pass'] = '%p';
$config['username_domain'] = '{DOMAIN}';
$config['des_key'] = '{secret}';
$config['force_https'] = true;
$config['enable_installer'] = false;
$config['product_name'] = 'CTL Webmailer';
$config['temp_dir'] = '/var/lib/ctl-webmail/temp';
$config['log_driver'] = 'syslog';
$config['plugins'] = [];
$config['imap_conn_options'] = ['ssl' => ['verify_peer' => true, 'verify_peer_name' => true]];
$config['smtp_conn_options'] = ['ssl' => ['verify_peer' => true, 'verify_peer_name' => true]];
"""


def prepare_php_apps():
    # Keep generated encryption keys stable when resuming a partially completed stage.
    keyfile=STATE/'php-app-keys.json'
    if not keyfile.exists():write(keyfile,json.dumps({'pma':secrets.token_hex(16),'roundcube':secrets.token_hex(12)}),0o600)
    keys=json.loads(keyfile.read_text())
    web=pwd.getpwnam('www-data')
    data=Path('/var/lib/ctl-webmail');data.mkdir(exist_ok=True)
    os.chown(data,web.pw_uid,web.pw_gid);data.chmod(0o750)
    temp=data/'temp';temp.mkdir(exist_ok=True);os.chown(temp,web.pw_uid,web.pw_gid);temp.chmod(0o700)
    database=data/'roundcube.sqlite'
    candidates=[Path('/usr/share/roundcube/SQL/sqlite.initial.sql'),
                Path('/usr/share/dbconfig-common/data/roundcube/install/sqlite3')]
    schema=next((p for p in candidates if p.is_file()),None)
    if schema is None:raise ValueError('Roundcube SQLite-Initialschema aus Ubuntu-Paket fehlt.')
    with sqlite3.connect(database) as db:
        if not db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'").fetchone():
            db.executescript(schema.read_text())
    os.chown(database,web.pw_uid,web.pw_gid);database.chmod(0o640)
    write('/etc/roundcube/config.inc.php',roundcube_config(keys['roundcube']),0o640)
    os.chown('/etc/roundcube/config.inc.php',0,web.pw_gid)
    write('/etc/phpmyadmin/conf.d/99-ctl.php',phpmyadmin_config(keys['pma']),0o640)
    os.chown('/etc/phpmyadmin/conf.d/99-ctl.php',0,web.pw_gid)
    version=output(['php','-r','echo PHP_MAJOR_VERSION.".".PHP_MINOR_VERSION;'])
    if not re.fullmatch(r'[0-9]+\.[0-9]+',version):raise ValueError('PHP-Version nicht ermittelt.')
    write(STATE/'php-version',version,0o600)
    write(f'/etc/php/{version}/fpm/conf.d/99-ctl.ini','upload_max_filesize=10M\npost_max_size=32M\nmemory_limit=256M\nsession.cookie_secure=1\nsession.cookie_httponly=1\n')
    for config in ('/etc/roundcube/config.inc.php','/etc/phpmyadmin/conf.d/99-ctl.php'):run(['php','-l',config])
    # Only the dedicated TLS vhost publishes these applications.
    for config in ('phpmyadmin','roundcube'):
        if Path('/etc/apache2/conf-enabled/'+config+'.conf').exists():run(['a2disconf',config])
    run(['a2enmod','proxy_fcgi','setenvif'])
    run(['systemctl','enable','--now',f'php{version}-fpm'])
    run(['systemctl','restart',f'php{version}-fpm'])


def prepare_dns():
    key_dir=Path('/etc/opendkim/keys')/DOMAIN;key_dir.mkdir(parents=True,exist_ok=True)
    if not (key_dir/'ctl.private').exists():run(['opendkim-genkey','-b','2048','-d',DOMAIN,'-s','ctl','-D',str(key_dir)])
    user=pwd.getpwnam('opendkim');os.chown(key_dir,user.pw_uid,user.pw_gid)
    os.chown(key_dir/'ctl.private',user.pw_uid,user.pw_gid);(key_dir/'ctl.private').chmod(0o600)
    key=(key_dir/'ctl.txt').read_text();zone=Path('/etc/bind/ctlsoftware-test.zone')
    write(zone,bind_zone(key,int(time.time())))
    write('/etc/bind/named.conf.local',MARKER+f'zone "{DOMAIN}" {{ type primary; file "{zone}"; allow-transfer {{ none; }}; }};\n')
    write('/etc/bind/named.conf.options',MARKER+f'''options {{
 directory "/var/cache/bind";
 listen-on port 53 {{ 127.0.0.1; {IP}; }};
 listen-on-v6 {{ none; }};
 recursion no;
 allow-query {{ any; }};
 allow-transfer {{ none; }};
 dnssec-validation auto;
 minimal-responses yes;
}};
''')
    run(['named-checkconf']);run(['named-checkzone',DOMAIN,str(zone)])
    run(['systemctl','enable','--now','named']);run(['systemctl','restart','named'])
    required=f'''Beim Provider muss eine echte NS-Delegation bestehen, nicht nur ein A-Eintrag:
{DOMAIN}. NS ns1.{DOMAIN}.
Glue/A: ns1.{DOMAIN}. A {IP}
PTR beim Serverprovider: {IP} -> {DOMAIN}
Es wird keine unzuständige lokale Reverse-Zone als Ersatz angelegt.
'''
    write(STATE/'provider-dns.txt',required,0o600)


def public_dns_check():
    errors=[]
    for resolver in ('1.1.1.1','8.8.8.8'):
        def query(name,kind):return output(['dig','@'+resolver,'+short','+time=5','+tries=1',name,kind]).splitlines()
        if query(DOMAIN,'A')!=[IP]:errors.append(resolver+': A-Eintrag stimmt nicht.')
        if query(DOMAIN,'AAAA'):errors.append(resolver+': AAAA vorhanden; diese IPv4-Routine konfiguriert kein IPv6.')
        if 'ns1.'+DOMAIN+'.' not in query(DOMAIN,'NS'):errors.append(resolver+': NS-Delegation fehlt.')
        if not any(line.split()[-1:]==[DOMAIN+'.'] for line in query(DOMAIN,'MX')):errors.append(resolver+': MX fehlt.')
        if not query('ctl._domainkey.'+DOMAIN,'TXT'):errors.append(resolver+': DKIM ist noch nicht öffentlich sichtbar.')
        reverse=output(['dig','@'+resolver,'+short','+time=5','+tries=1','-x',IP]).splitlines()
        if DOMAIN+'.' not in reverse:errors.append(resolver+': PTR/Reverse-DNS stimmt nicht.')
    if errors:raise ValueError('\n'.join(errors)+'\n'+(STATE/'provider-dns.txt').read_text()+'Nach DNS-Korrektur: sudo bash install-ctlsoftware-test.sh --resume')


def prepare_certificate():
    root=Path('/var/www/ctlsoftware-test-acme');root.mkdir(parents=True,exist_ok=True)
    write('/etc/apache2/sites-available/ctlsoftware-test.conf',apache_config())
    run(['a2enmod','proxy','proxy_http','headers','ssl','rewrite'])
    run(['a2dissite','000-default']);run(['a2ensite','ctlsoftware-test'])
    run(['apache2ctl','configtest']);run(['systemctl','enable','--now','apache2']);run(['systemctl','reload','apache2'])
    run(['certbot','certonly','--webroot','-w',str(root),'--cert-name',DOMAIN,'-d',DOMAIN,
         '--email',FORWARD,'--agree-tos','--non-interactive','--keep-until-expiring'])


def forward_script():return f'redirect \"{FORWARD}\";\nkeep;\n'


def prepare_mail():
    try:vmail=pwd.getpwnam('ctlvmail')
    except KeyError:
        run(['useradd','--system','--user-group','--home-dir','/var/vmail','--no-create-home','--shell','/usr/sbin/nologin','ctlvmail'])
        vmail=pwd.getpwnam('ctlvmail')
    root=Path('/var/vmail');root.mkdir(exist_ok=True);os.chown(root,vmail.pw_uid,vmail.pw_gid);root.chmod(0o750)
    entries=[]
    for local in MAIL_USERS:
        home=root/DOMAIN/local
        for path in (home,home/'Maildir',home/'Maildir/cur',home/'Maildir/new',home/'Maildir/tmp'):
            path.mkdir(parents=True,exist_ok=True);os.chown(path,vmail.pw_uid,vmail.pw_gid);path.chmod(0o700)
        # OpenSSL reads the default password from stdin, never argv.
        hashed=run(['openssl','passwd','-6','-stdin'],input=MAIL_PASSWORD,text=True,capture_output=True).stdout.strip()
        entries.append(f'{local}@{DOMAIN}:{{SHA512-CRYPT}}{hashed}:{vmail.pw_uid}:{vmail.pw_gid}::{home}::')
    # Parent domain directory was created by mkdir(parents=True).
    os.chown(root/DOMAIN,vmail.pw_uid,vmail.pw_gid);(root/DOMAIN).chmod(0o750)
    write('/etc/dovecot/ctl-users','\n'.join(entries)+'\n',0o640)
    os.chown('/etc/dovecot/ctl-users',0,grp.getgrnam('dovecot').gr_gid)
    write('/etc/dovecot/dovecot.conf',dovecot_config())
    # Force valid uid range for this single virtual-mail identity.
    with open('/etc/dovecot/dovecot.conf','a') as stream:stream.write(f'first_valid_uid = {vmail.pw_uid}\nlast_valid_uid = {vmail.pw_uid}\n')
    write('/etc/dovecot/sieve/ctl-forward.sieve',forward_script())
    run(['sievec','/etc/dovecot/sieve/ctl-forward.sieve'])
    write('/etc/postfix/main.cf',postfix_config())
    master=Path('/etc/postfix/master.cf');text=master.read_text()
    # Original package defaults have submission entries commented out; avoid duplicates on resume.
    text=text.split('# CTL authenticated submission;')[0].rstrip()+postfix_submission()
    write(master,text)
    write('/etc/postfix/ctl-mailboxes',''.join(f'{local}@{DOMAIN} 1\n' for local in MAIL_USERS))
    write('/etc/postfix/ctl-aliases',f'postmaster@{DOMAIN} info@{DOMAIN}\nabuse@{DOMAIN} info@{DOMAIN}\nroot@{DOMAIN} info@{DOMAIN}\n')
    for table in ('ctl-mailboxes','ctl-aliases'):run(['postmap','/etc/postfix/'+table])
    write('/etc/opendkim.conf',MARKER+'''Syslog yes
UMask 007
PidFile /run/opendkim/opendkim.pid
Mode sv
Canonicalization relaxed/simple
Socket inet:8891@127.0.0.1
UserID opendkim
KeyTable refile:/etc/opendkim/ctl-keys
SigningTable refile:/etc/opendkim/ctl-signing
InternalHosts refile:/etc/opendkim/ctl-trusted
OversignHeaders From
''')
    write('/etc/opendkim/ctl-keys',f'ctl._domainkey.{DOMAIN} {DOMAIN}:ctl:/etc/opendkim/keys/{DOMAIN}/ctl.private\n')
    write('/etc/opendkim/ctl-signing',f'*@{DOMAIN} ctl._domainkey.{DOMAIN}\n')
    write('/etc/opendkim/ctl-trusted','127.0.0.1\nlocalhost\n')
    if not (STATE/'srs-secret').exists():write(STATE/'srs-secret',secrets.token_hex(32)+'\n',0o600)
    # A service-private copy, not /etc/ctlsoftware-test-setup (which is root-only).
    write('/etc/postsrsd.secret',(STATE/'srs-secret').read_text(),0o600)
    # The packaged unit may start under a service user; initialize as root, then
    # let PostSRSd drop to its configured unprivileged account after reading secrets.
    try:pwd.getpwnam('postsrsd')
    except KeyError:run(['useradd','--system','--user-group','--no-create-home','--shell','/usr/sbin/nologin','postsrsd'])
    write('/etc/systemd/system/postsrsd.service.d/ctl.conf','[Service]\nUser=root\nGroup=root\n')
    run(['systemctl','daemon-reload'])
    write('/etc/postsrsd.conf',f'''domains = {{ "{DOMAIN}" }}
srs-domain = "{DOMAIN}"
socketmap = inet:127.0.0.1:10003
secrets-file = "/etc/postsrsd.secret"
unprivileged-user = "postsrsd"
chroot-dir = ""
''')
    run(['doveconf','-n'],stdout=subprocess.DEVNULL);run(['postfix','check']);run(['opendkim','-n','-x','/etc/opendkim.conf'])
    for service in ('opendkim','postsrsd','dovecot','postfix'):
        run(['systemctl','enable',service]);run(['systemctl','restart',service])


def prepare_application(args):
    source=Path(args.source) if args.source else Path('/opt/ctlsoftware-test-source')
    if not source.exists():run(['git','clone','--branch','setup/debian-testumgebung','--single-branch','https://github.com/omueller369/LokZeitleiste.git',str(source)])
    if not (source/'backend/requirements.txt').is_file():raise ValueError('Ungültiger Anwendungsquelltext.')
    env={**os.environ,'CTL_INSTALL_SOURCE':str(source.resolve()),'CTL_INSTALL_HELPER':str(Path(args.engine).with_name('ispconfig_app.py'))}
    app_state=APP_CONFIG/'installation.json'
    complete=app_state.exists() and json.loads(app_state.read_text()).get('complete')
    if not complete:
        command=['python3',args.engine,'--standalone','--domain',DOMAIN,'--webserver','apache',
                 '--db-name',DB_NAME,'--db-user',DB_USER,'--db-password-file',str(STATE/'database-password')]
        if app_state.exists():command.append('--resume')
        run(command,env=env)
    settings=json.loads((APP_CONFIG/'environment.json').read_text())
    settings.update(SMTP_HOST=DOMAIN,SMTP_PORT='465',SMTP_SECURITY='ssl',SMTP_FROM='info@'+DOMAIN,
                    SMTP_USERNAME='info@'+DOMAIN,SMTP_PASSWORD=MAIL_PASSWORD,WORK_REPORT_RECEIPT_EMAIL=FORWARD,
                    MAILBOX_IMAP_HOST=DOMAIN,MAILBOX_IMAP_PORT='993',MAILBOX_SMTP_HOST=DOMAIN,
                    MAILBOX_SMTP_PORT='465',MAILBOX_SMTP_SECURITY='ssl')
    spec=importlib.util.spec_from_file_location('ctl_setup_engine',args.engine);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    write(APP_CONFIG/'app.env',module.env_file(settings),0o600)
    write(APP_CONFIG/'environment.json',json.dumps(settings),0o600)
    run(['systemctl','restart','ctlsoftware-test','ctlsoftware-test-worker'])


def finish_web():
    write('/etc/apache2/sites-available/ctlsoftware-test.conf',apache_config(True,(STATE/'php-version').read_text().strip()))
    run(['apache2ctl','configtest']);run(['systemctl','reload','apache2'])
    hook='''#!/bin/sh
set -eu
apache2ctl configtest
postfix check
doveconf -n >/dev/null
systemctl reload apache2 postfix dovecot
'''
    write('/etc/letsencrypt/renewal-hooks/deploy/ctlsoftware-test',hook,0o755)
    run(['systemctl','enable','--now','certbot.timer'])


def verify():
    version=(STATE/'php-version').read_text().strip()
    run(['systemctl','is-active','--quiet',f'php{version}-fpm'])
    for path,marker in (('/phpmyadmin/','phpMyAdmin'),('/webmailer/','_token')):
        page=output(['curl','--fail','--silent','--show-error','--location','https://'+DOMAIN+path])
        if marker not in page:raise ValueError('Anmeldeseite nicht erkannt: '+path)
    for service in ('named','mariadb','apache2','opendkim','postsrsd','postfix','dovecot','ctlsoftware-test','ctlsoftware-test-worker'):
        run(['systemctl','is-active','--quiet',service])
    run(['curl','--fail','--silent','--show-error','https://'+DOMAIN+'/health'])
    # Verify outbound TCP/25 without sending any email.
    mx_rows=output(['dig','+short','gmail.com','MX']).splitlines()
    hosts=[line.split()[1].rstrip('.') for line in sorted(mx_rows,key=lambda row:int(row.split()[0])) if len(line.split())==2]
    reachable=False
    for host in hosts[:2]:
        try:
            with socket.create_connection((host,25),timeout=5):reachable=True
            break
        except OSError:continue
    if not reachable:raise ValueError('Ausgehender SMTP-Port 25 zu Gmail nicht erreichbar. Provider-Freigabe prüfen.')
    context=ssl.create_default_context()
    for local in MAIL_USERS:
        address=local+'@'+DOMAIN
        with imaplib.IMAP4_SSL(DOMAIN,993,ssl_context=context) as imap:
            imap.login(address,MAIL_PASSWORD);imap.select('INBOX');imap.logout()
        with smtplib.SMTP_SSL(DOMAIN,465,context=context,timeout=15) as smtp:smtp.login(address,MAIL_PASSWORD)
    # Probe only RCPT; no test message or email is sent.
    with smtplib.SMTP(IP,25,local_hostname='ctl-relay-check.invalid',source_address=(IP,0),timeout=15) as smtp:
        smtp.ehlo();smtp.mail('probe@example.net');code,_=smtp.rcpt(FORWARD)
        if code<500:raise ValueError('Unauthentifizierte externe Weiterleitung wurde nicht abgelehnt.')
        smtp.rset()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume',action='store_true');parser.add_argument('--source')
    parser.add_argument('--engine',required=True)
    args=parser.parse_args()
    if os.geteuid()!=0:raise ValueError('Als root/sudo ausführen.')
    state_file=STATE/'state.json'
    state=json.loads(state_file.read_text()) if state_file.exists() else {'completed':[]}
    if state.get('complete'):raise ValueError('Installation ist bereits abgeschlossen; dies ist kein Update-Script.')
    if not (STATE/'database-password').exists():
        first=getpass.getpass('Neues MariaDB-Passwort für dbo_ctl: ')
        second=getpass.getpass('Passwort wiederholen: ')
        if first!=second or len(first)<6 or any(c in first for c in '\r\n\x00'):raise ValueError('Passwörter müssen übereinstimmen und mindestens 6 Zeichen enthalten.')
        write(STATE/'database-password',first,0o600)
    # Require this exact public IP on an interface; no IPv6 or NAT configuration is guessed.
    interfaces=json.loads(output(['ip','-j','-4','addr']))
    if IP not in [a['local'] for item in interfaces for a in item.get('addr_info',[])]:raise ValueError(IP+' ist nicht als lokale IPv4 konfiguriert.')
    stages=[('packages',prepare_packages),('hostname',prepare_hostname),('firewall',prepare_firewall),('database',prepare_database),('php-apps',prepare_php_apps),('dns',prepare_dns),
            ('public-dns',public_dns_check),('certificate',prepare_certificate),('mail',prepare_mail),
            ('application',lambda:prepare_application(args)),('web',finish_web),('verify',verify)]
    for name,action in stages:
        if name in state['completed']:continue
        print('Schritt: '+name,flush=True);action();state['completed'].append(name)
        write(state_file,json.dumps(state),0o600)
    state['complete']=True;write(state_file,json.dumps(state),0o600)
    print('\nTestserver eingerichtet: https://'+DOMAIN+'/tf | Verwaltung: https://'+DOMAIN+'/admin/start')
    print('phpMyAdmin: https://'+DOMAIN+'/phpmyadmin | Benutzer: dbo_ctl | eingegebenes DB-Passwort')
    print('Webmailer: https://'+DOMAIN+'/webmailer | vollständige E-Mail-Adresse + Postfachpasswort')
    print('Admin-Passwort: sudo cat /etc/ctlsoftware-test/admin-initial-password')
    print('TF-Liste: sudo cat /etc/ctlsoftware-test/demo-tf.json | TF-Initialpasswort: tomcom123456')
    print('IMAP: '+DOMAIN+':993 (TLS), SMTP: '+DOMAIN+':465 (TLS) oder :587 (STARTTLS)')
    for local in MAIL_USERS:print(local+'@'+DOMAIN+' | Passwort: '+MAIL_PASSWORD+' | IMAP-Kopie + Weiterleitung an '+FORWARD)
    print('Eine echte Gmail-Zustellung wurde nicht durch eine Testmail geprüft; dafür eine Nachricht an info@'+DOMAIN+' senden.')


if __name__=='__main__':
    try:main()
    except Exception as exc:
        # Never format SQL exceptions: they may contain a password in bound parameters.
        if isinstance(exc,(ValueError,OSError,subprocess.CalledProcessError)):print('FEHLER: '+str(exc),file=sys.stderr)
        else:print('FEHLER ('+type(exc).__name__+'). Zugang/Journal prüfen; Zugangsdaten werden nicht ausgegeben.',file=sys.stderr)
        print('Nach Behebung mit --resume fortsetzen. Keine Datenbank wird gelöscht.',file=sys.stderr)
        sys.exit(1)
CTL_FRESH_SERVER
args=(--engine "$work_dir/ispconfig_install.py")
[[ $resume == false ]] || args+=(--resume)
[[ -z $source_dir ]] || args+=(--source "$source_dir")
python3 "$work_dir/fresh_ubuntu.py" "${args[@]}"
