#!/usr/bin/env bash
# Nur lokale Dateien vorbereiten; keine Systemänderungen.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
command -v openssl >/dev/null
umask 077
if [[ ! -e .env.test ]]; then
  db_password=$(openssl rand -hex 24)
  root_password=$(openssl rand -hex 24)
  printf 'MYSQL_PASSWORD=%s\nMYSQL_ROOT_PASSWORD=%s\n' "$db_password" "$root_password" > .env.test
fi
mkdir -p testenv/certs
if [[ ! -e testenv/certs/mailpit.crt && ! -e testenv/certs/mailpit.key ]]; then
  openssl req -x509 -newkey rsa:3072 -nodes -days 365 \
    -keyout testenv/certs/mailpit.key -out testenv/certs/mailpit.crt \
    -subj '/CN=mailpit' -addext 'subjectAltName=DNS:mailpit' \
    -addext 'basicConstraints=critical,CA:TRUE' >/dev/null 2>&1
fi
[[ -s testenv/certs/mailpit.crt && -s testenv/certs/mailpit.key ]] || {
  echo 'Unvollständiges Zertifikatspaar. Bitte prüfen.' >&2; exit 1;
}
openssl x509 -in testenv/certs/mailpit.crt -checkend 86400 -noout >/dev/null || {
  echo 'Testzertifikat läuft ab. Zertifikate bei gestopptem Stack neu erzeugen.' >&2; exit 1;
}
# Öffentliches Zertifikat muss vom nicht privilegierten API-Benutzer lesbar sein.
chmod 755 testenv/certs
chmod 644 testenv/certs/mailpit.crt
chmod 600 testenv/certs/mailpit.key .env.test
echo 'Testkonfiguration vorbereitet. Passwörter wurden nicht ausgegeben.'
