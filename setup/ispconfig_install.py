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
    if not Path('/usr/local/ispconfig').is_dir():problems.append('Bestehende ISPConfig-Installation unter /usr/local/ispconfig nicht gefunden.')
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
        password=getpass.getpass('Passwort des vorhandenen ISPConfig-Datenbankbenutzers: ')
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
        print('In ISPConfig noch die Website-Weiterleitung eintragen: sudo cat '+str(CONFIG/'ispconfig-directives.conf'))
        print('Danach öffentlich prüfen: '+origin(args.domain,args.http)+'/health')
        print('Backend: '+origin(args.domain,args.http)+'/admin/start | TF: '+origin(args.domain,args.http)+'/tf')
        print('Admin: '+args.admin_user+' | Passwortdatei: sudo cat '+str(CONFIG/'admin-initial-password'))
        print('TF-Liste: sudo cat '+str(CONFIG/'demo-tf.json')+' | Initialpasswort: tomcom123456 (Wechsel beim ersten Login).')
        print('Echter Emailversand ist für diese Testinstallation deaktiviert.')

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,subprocess.CalledProcessError) as exc:
        print('FEHLER: '+str(exc),file=sys.stderr)
        print('Keine Datenbank gelöscht. Bei unterbrochener eigener Installation: sudo bash setup-ispconfig.sh --resume',file=sys.stderr)
        sys.exit(1)
