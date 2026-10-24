"""Render the standalone full-server setup; no companion setup files needed by users."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
header=r'''#!/usr/bin/env bash
# Full fresh Ubuntu 26.04 CTL test server. Never execute on an existing production host.
set -Eeuo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
script_file="$script_dir/$(basename -- "${BASH_SOURCE[0]}")"
resume=false
update=false
source_dir=''
while (($#));do
 case "$1" in
  --resume) resume=true;shift ;;
  --update) update=true;resume=true;shift ;;
  --source) (($#>=2)) || { echo '--source benötigt einen Pfad.' >&2;exit 2; };source_dir=$2;shift 2 ;;
  --help|-h)
   echo 'sudo bash install-ctlsoftware-test.sh [--resume|--update] [--source /Pfad/zum/Projekt]'
   echo 'Neuinstallation: frisches Ubuntu 26.04. --update: vorhandenen eigenen CTL-Testserver aktualisieren.'
   echo 'Installiert Apache, MariaDB, lokales BIND, Postfix/Dovecot, Mitarbeiterpostfächer und CTL-Testdaten.'
   echo 'Domain: ctl-software.io-goerlitz.eu | IPv4: 212.227.86.251 | DB: db_ctl | Benutzer: dbo_ctl'
   echo 'Das neue Datenbankpasswort wird verdeckt abgefragt.'
   exit 0 ;;
  *) echo "Unbekannte Option: $1" >&2;exit 2 ;;
 esac
done
if ((EUID!=0));then
 args=();[[ $update == false ]] || args+=(--update);[[ $resume == false ]] || args+=(--resume);[[ -z $source_dir ]] || args+=(--source "$source_dir")
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
'''
text=header+(ROOT/'setup/ispconfig_app.py').read_text()+"CTL_FRESH_APP_HELPER\ncat > \"$work_dir/ispconfig_install.py\" <<'CTL_FRESH_ENGINE'\n"+(ROOT/'setup/ispconfig_install.py').read_text()+"CTL_FRESH_ENGINE\ncat > \"$work_dir/fresh_ubuntu.py\" <<'CTL_FRESH_SERVER'\n"+(ROOT/'setup/fresh_ubuntu.py').read_text()+r'''CTL_FRESH_SERVER
args=(--engine "$work_dir/ispconfig_install.py")
[[ $resume == false ]] || args+=(--resume)
[[ $update == false ]] || args+=(--update)
[[ -z $source_dir ]] || args+=(--source "$source_dir")
python3 "$work_dir/fresh_ubuntu.py" "${args[@]}"
'''
path=ROOT/'install-ctlsoftware-test.sh';path.write_text(text);path.chmod(0o755)
print('install-ctlsoftware-test.sh generated, complete full-server setup embedded.')
