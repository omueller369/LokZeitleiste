#!/usr/bin/env bash
# Automatischer Einstieg für die vollständige Backend-Testumgebung.
set -euo pipefail
args=("$@")
auto_admin=true
for arg in "$@"; do
  case "$arg" in
    --auto-admin|--skip-admin|--admin-user|--admin-password-file) auto_admin=false ;;
  esac
done
if [[ "$auto_admin" == true ]]; then args=(--auto-admin "${args[@]}"); fi
exec bash "$(dirname -- "${BASH_SOURCE[0]}")/setup/install.sh" "${args[@]}"
