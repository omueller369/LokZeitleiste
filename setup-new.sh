#!/usr/bin/env bash
# Vollständige Neuinstallation ohne Wiederverwendung vorhandener Testdaten.
set -Eeuo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
for arg in "$@"; do
  case "$arg" in
    --help|-h) echo 'sudo bash setup-new.sh [--check|--skip-admin|--auto-admin|--admin-user USER --admin-password-file DATEI]'; exit 0 ;;
    --check) exec bash "$root/setup.sh" "$@" ;;
  esac
done
[[ $EUID == 0 && $(uname -s) == Linux ]] || { echo 'Als root im Linux-Gastsystem ausführen.' >&2; exit 1; }
[[ ! -e "$root/backend/.env.test" ]] || { echo 'Testkonfiguration vorhanden: setup-update.sh verwenden.' >&2; exit 1; }
for role in TF VW; do
  if [[ -L "$root/$role" ]] || { [[ -d "$root/$role" ]] && [[ -n $(find "$root/$role" -mindepth 1 -print -quit) ]]; }; then
    echo "Vorhandene Benutzerdateien in $role: setup-update.sh verwenden." >&2; exit 1
  fi
done
volume=lokzeitleiste-test_mysql_test_data
[[ ! -e "/var/lib/docker/volumes/$volume" ]] || { echo 'Testdatenbank vorhanden: setup-update.sh verwenden.' >&2; exit 1; }
if command -v docker >/dev/null; then
  docker info >/dev/null 2>&1 || { echo 'Docker zuerst starten: sudo systemctl start docker. Danach erneut ausführen.' >&2; exit 1; }
  volumes=$(docker volume ls --format '{{.Name}}')
  if [[ $'\n'"$volumes"$'\n' == *$'\n'"$volume"$'\n'* ]]; then
    echo 'Testdatenbank vorhanden: setup-update.sh verwenden.' >&2; exit 1
  fi
fi
exec bash "$root/setup.sh" "$@"
