"""Small validated configuration builder used by the external demo installer."""
import os
import re
import socket
import sys
import tempfile
from pathlib import Path


def domain_name(value):
    if len(value)>253 or not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}',value):
        raise ValueError('Ungültige Domain')
    return value


def dns(domain, expected):
    records=socket.getaddrinfo(domain,80,type=socket.SOCK_STREAM)
    ipv4={row[4][0] for row in records if row[0]==socket.AF_INET}
    ipv6={row[4][0] for row in records if row[0]==socket.AF_INET6}
    if ipv4!={expected} or ipv6:
        raise ValueError(f'DNS prüfen: A={sorted(ipv4)}, AAAA={sorted(ipv6)}. Erwartet ausschließlich A={expected}. AAAA erst nach IPv6-Konfiguration verwenden.')
    print(f'DNS korrekt: {domain} → {expected}')


def apache(kind,domain):
    domain_name(domain)
    base='# Managed by LokZeitleiste demo setup\n'
    if kind=='http':
        return base+f'''<VirtualHost *:80>
    ServerName {domain}
    Alias /.well-known/acme-challenge/ /var/www/lokzeitleiste-acme/.well-known/acme-challenge/
    <Directory /var/www/lokzeitleiste-acme>
        Require all granted
        Options None
        AllowOverride None
    </Directory>
    RewriteEngine On
    RewriteCond %{{REQUEST_URI}} !^/\\.well-known/acme-challenge/
    RewriteRule ^ https://{domain}%{{REQUEST_URI}} [R=301,L,NE]
</VirtualHost>
'''
    if kind!='https':raise ValueError('Unknown virtual host type')
    return base+f'''<VirtualHost *:443>
    ServerName {domain}
    SSLEngine On
    SSLCertificateFile /etc/letsencrypt/live/{domain}/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/{domain}/privkey.pem
    SSLProtocol all -SSLv3 -TLSv1 -TLSv1.1
    ProxyRequests Off
    ProxyPreserveHost On
    RequestHeader set X-Forwarded-Proto "https"
    Header always set X-Content-Type-Options "nosniff"
    ProxyPass / http://127.0.0.1:8000/
    ProxyPassReverse / http://127.0.0.1:8000/
    ErrorLog ${{APACHE_LOG_DIR}}/lokzeitleiste-demo-error.log
    CustomLog ${{APACHE_LOG_DIR}}/lokzeitleiste-demo-access.log combined
</VirtualHost>
'''


def update_env(path,domain):
    domain_name(domain)
    path=Path(path)
    if path.is_symlink() or not path.is_file():raise ValueError('Konfiguration fehlt oder ist ein Symlink')
    lines=path.read_text().splitlines()
    lines=[line for line in lines if not re.match(r'^\s*(?:PUBLIC_ORIGIN|COOKIE_SECURE)\s*=',line)]
    lines += [f'PUBLIC_ORIGIN=https://{domain}','COOKIE_SECURE=true']
    fd,name=tempfile.mkstemp(dir=path.parent,prefix='.demo-env-')
    try:
        with os.fdopen(fd,'w') as stream:
            stream.write('\n'.join(lines)+'\n');stream.flush();os.fsync(stream.fileno())
        os.chmod(name,0o600);os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


if __name__=='__main__':
    try:
        command=sys.argv[1]
        if command=='dns':dns(domain_name(sys.argv[2]),sys.argv[3])
        elif command=='apache':print(apache(sys.argv[2],sys.argv[3]),end='')
        elif command=='env':update_env(sys.argv[2],sys.argv[3])
        else:raise ValueError('Unknown command')
    except (ValueError,OSError,IndexError) as error:
        raise SystemExit(str(error))
