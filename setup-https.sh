#!/usr/bin/env bash
# Free Let's Encrypt HTTPS using the existing Apache demo installer.
set -Eeuo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
email=''
while (($#));do
 case "$1" in
  --email) (($#>=2)) || { echo 'E-Mail fehlt.' >&2;exit 2; };email=$2;shift 2;;
  --help|-h) echo 'sudo bash setup-https.sh [--email ZERTIFIKATSKONTO-EMAIL]';exit 0;;
  *) echo "Unbekannte Option: $1" >&2;exit 2;;
 esac
done
[[ $EUID == 0 ]] || { echo 'Mit sudo auf dem Ubuntu-Server ausführen.' >&2;exit 1; }
if [[ -z $email && -r /var/lib/lokzeitleiste/letsencrypt-email && ! -L /var/lib/lokzeitleiste/letsencrypt-email ]];then IFS= read -r email < /var/lib/lokzeitleiste/letsencrypt-email;fi
if [[ -z $email ]];then
 [[ -t 0 ]] || { echo '--email für das kostenlose Let’s-Encrypt-Konto angeben.' >&2;exit 2; }
 read -r -p 'E-Mail für das kostenlose Let’s-Encrypt-Zertifikatskonto: ' email
fi
exec bash "$root/setup-demo.sh" --https --email "$email"
