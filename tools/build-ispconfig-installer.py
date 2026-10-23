"""Build the single-file interactive installer from the reviewed setup engine/helpers."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
header=r'''#!/usr/bin/env bash
# CTL-Software: interactive application installation on an existing Ubuntu/ISPConfig server.
# Standalone setup file: engine and helper are embedded; application source is cloned if needed.
set -Eeuo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
script_file="$script_dir/$(basename -- "${BASH_SOURCE[0]}")"
source_dir=''
resume=false
while (($#)); do
 case "$1" in
  --source) (($#>=2)) || { echo 'Pfad nach --source fehlt.' >&2;exit 2; };source_dir=$2;shift 2 ;;
  --resume) resume=true;shift ;;
  -h|--help)
   echo 'sudo bash install-ctl-software.sh [--source /Pfad/zum/LokZeitleiste] [--resume]'
   echo 'Fragt bestehende Subdomain, Datenbankname, MariaDB-Benutzer und verdeckt dessen Passwort ab.'
   echo 'Installiert fehlende Python-/Anwendungswerkzeuge; nutzt vorhandene ISPConfig-Web-/Datenbankdienste.'
   echo 'Importiert 20 Test-TF samt Bildern. Kein vorhandener Datenbankinhalt wird gelöscht.'
   exit 0 ;;
  *) echo "Unbekannte Option: $1" >&2;exit 2 ;;
 esac
done
if ((EUID!=0)); then
 command -v sudo >/dev/null || { echo 'sudo fehlt. Als root starten.' >&2;exit 1; }
 elevated_args=();[[ -z "$source_dir" ]] || elevated_args+=(--source "$source_dir")
 [[ $resume == false ]] || elevated_args+=(--resume)
 exec sudo -- bash "$script_file" "${elevated_args[@]}"
fi
umask 022
[[ $resume == true || -t 0 ]] || { echo 'Interaktive Eingabe erforderlich: sudo bash install-ctl-software.sh' >&2;exit 1; }
trap 'echo "Installation bei Zeile $LINENO abgebrochen. Keine Datenbank wurde gelöscht." >&2' ERR
[[ -f /etc/os-release ]] || { echo 'Ubuntu wird benötigt.' >&2;exit 1; }
# shellcheck disable=SC1091
. /etc/os-release
[[ ${ID:-} == ubuntu ]] || { echo 'Diese Routine ist für Ubuntu vorgesehen.' >&2;exit 1; }
[[ -d /usr/local/ispconfig ]] || { echo 'Eine bestehende ISPConfig-Installation wird benötigt.' >&2;exit 1; }
command -v apt-get >/dev/null || { echo 'apt-get fehlt.' >&2;exit 1; }
command -v dpkg-query >/dev/null || { echo 'dpkg-query fehlt.' >&2;exit 1; }
# Only application prerequisites; no Apache/nginx/MariaDB/PHP/ISPConfig/Docker install.
packages=(python3 python3-venv python3-pip git ca-certificates fonts-dejavu-core)
missing=()
for package in "${packages[@]}";do
 if [[ $(dpkg-query -W -f='${Status}' "$package" 2>/dev/null || true) != 'install ok installed' ]];then missing+=("$package");fi
done
if ((${#missing[@]}));then
 printf 'Fehlende Anwendungsabhängigkeiten werden installiert: %s\n' "${missing[*]}"
 export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l
 apt-get update
 apt-get install -y --no-install-recommends "${missing[@]}"
fi
python3 -c 'import sys,venv,ensurepip;sys.exit(0 if sys.version_info>=(3,11) else "Python >=3.11 erforderlich; bitte Ubuntu 24.04 oder neuer verwenden.")'
if [[ $resume == true ]];then
 [[ -f /etc/lokzeitleiste-ispconfig/installation.json ]] || { echo 'Keine eigene unterbrochene Installation gefunden.' >&2;exit 1; }
 webserver=$(python3 -c 'import json;print(json.load(open("/etc/lokzeitleiste-ispconfig/installation.json"))["webserver"])')
 installer_args=(--resume --require-existing-site)
else
 [[ -t 0 ]] || { echo 'Interaktive Eingabe erforderlich: sudo bash install-ctl-software.sh' >&2;exit 1; }
 read -r -p 'Bestehende Subdomain (ohne http:// und ohne Pfad): ' domain
 [[ $domain =~ ^[A-Za-z0-9][A-Za-z0-9.-]*[A-Za-z0-9]$ && $domain != *..* ]] || { echo 'Ungültige Subdomain.' >&2;exit 1; }
 read -r -p 'MariaDB-Datenbankname (inkl. ISPConfig-Präfix): ' database
 read -r -p 'MariaDB-Benutzername (inkl. ISPConfig-Präfix): ' db_user
 [[ $database =~ ^[A-Za-z0-9_]{1,64}$ && -n $db_user ]] || { echo 'Datenbankname/Benutzer fehlen oder sind ungültig.' >&2;exit 1; }
 read -r -p 'MariaDB-Host [127.0.0.1]: ' db_host;db_host=${db_host:-127.0.0.1}
 read -r -p 'Zugriff [http/https] [http]: ' scheme;scheme=${scheme:-http}
 [[ $scheme == http || $scheme == https ]] || { echo 'http oder https angeben.' >&2;exit 1; }
 default_webserver=apache
 if ! command -v apache2ctl >/dev/null && command -v nginx >/dev/null;then default_webserver=nginx;fi
 read -r -p "Vorhandener Webserver [apache/nginx] [$default_webserver]: " webserver;webserver=${webserver:-$default_webserver}
 [[ $webserver == apache || $webserver == nginx ]] || { echo 'apache oder nginx angeben.' >&2;exit 1; }
 read -r -p 'Freier interner API-Port [18080]: ' api_port;api_port=${api_port:-18080}
 [[ $api_port =~ ^[0-9]+$ ]] || { echo 'Ungültiger API-Port.' >&2;exit 1; }
 installer_args=(--domain "$domain" --db-name "$database" --db-user "$db_user" --db-host "$db_host" --webserver "$webserver" --port "$api_port" --require-existing-site)
 [[ $scheme != http ]] || installer_args+=(--http)
 echo 'Das Datenbankpasswort wird vor der Einrichtung verdeckt abgefragt.'
fi
if [[ $webserver == apache ]];then
 command -v apache2ctl >/dev/null && command -v a2enmod >/dev/null || { echo 'Der vorhandene Apache wurde nicht gefunden.' >&2;exit 1; }
 # Activate only necessary modules already supplied by the installed Apache package.
 modules=$(apache2ctl -M)
 newly_enabled=()
 for module in proxy proxy_http headers;do
  if [[ $modules != *"${module}_module"* ]];then newly_enabled+=("$module");fi
 done
 if ((${#newly_enabled[@]}));then
  a2enmod "${newly_enabled[@]}"
  if ! apache2ctl configtest;then
   for ((index=${#newly_enabled[@]}-1;index>=0;index--));do a2dismod "${newly_enabled[index]}" || true;done
   echo 'Apache-Konfiguration ungültig; neu aktivierte Module zurückgenommen.' >&2;exit 1
  fi
  systemctl reload apache2
 fi
fi
if [[ -z $source_dir ]];then
 if [[ -f "$script_dir/backend/requirements.txt" && -d "$script_dir/backend/lokzeitleiste" ]];then source_dir=$script_dir
 else source_dir=/opt/ctl-software-source;fi
fi
if [[ ! -d $source_dir ]];then
 git clone --branch setup/debian-testumgebung --single-branch https://github.com/omueller369/LokZeitleiste.git "$source_dir"
fi
[[ -f "$source_dir/backend/requirements.txt" && -d "$source_dir/backend/lokzeitleiste" ]] || { echo 'Anwendungsquelltext fehlt im angegebenen Verzeichnis.' >&2;exit 1; }
source_dir=$(cd -- "$source_dir" && pwd -P)
work_dir=$(mktemp -d)
trap 'rm -rf -- "$work_dir"' EXIT
cat > "$work_dir/ispconfig_app.py" <<'CTL_APP_HELPER'
'''
footer=r'''CTL_INSTALL_ENGINE
export CTL_INSTALL_SOURCE="$source_dir" CTL_INSTALL_HELPER="$work_dir/ispconfig_app.py"
python3 "$work_dir/ispconfig_install.py" "${installer_args[@]}"
echo 'Weiterleitung für die bestehende Subdomain in ISPConfig eintragen:'
echo 'sudo cat /etc/lokzeitleiste-ispconfig/ispconfig-directives.conf'
'''
text=header+(ROOT/'setup/ispconfig_app.py').read_text()+"CTL_APP_HELPER\ncat > \"$work_dir/ispconfig_install.py\" <<'CTL_INSTALL_ENGINE'\n"+(ROOT/'setup/ispconfig_install.py').read_text()+footer
output=ROOT/'install-ctl-software.sh'
output.write_text(text);output.chmod(0o755)
print('install-ctl-software.sh generated (embedded engine and helper).')
