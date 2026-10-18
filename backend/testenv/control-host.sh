#!/usr/bin/env bash
set -Eeuo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
backend="$root/backend"
[[ -f "$backend/.env.host" ]] || { echo 'Zuerst sudo bash setup-demo.sh ausführen.' >&2;exit 1; }
compose=(docker compose --project-directory "$backend" --env-file "$backend/.env.host" -f "$backend/compose.host.yaml")
case ${1:-status} in
 start) "${compose[@]}" up -d --build --wait --wait-timeout 240 ;;
 stop) "${compose[@]}" stop ;;
 status) "${compose[@]}" ps ;;
 logs) "${compose[@]}" logs --tail 100 ;;
 admin) "${compose[@]}" exec api python -m lokzeitleiste.init_db --create-admin ;;
 backup)
  umask 077
  mkdir -p "$backend/testenv/backups"
  target=$(mktemp -d "$backend/testenv/backups/host-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")
  # Existing containers are stopped without building new code before the snapshot.
  "${compose[@]}" stop api mailer
  trap 'echo "Sicherung fehlgeschlagen/unvollständig: $target" >&2; "${compose[@]}" start api mailer || true' ERR
  python3 "$root/setup/host-mysql.py" backup "$backend/.env.host" "$target/database.sql.gz"
  files=(backend/.env.host)
  for name in TF VW backend/testenv/certs;do [[ ! -e "$root/$name" ]] || files+=("$name");done
  tar --acls --xattrs --numeric-owner -czf "$target/files.tar.gz" -C "$root" "${files[@]}"
  gzip -t "$target/database.sql.gz";tar -tzf "$target/files.tar.gz" >/dev/null
  trap - ERR
  echo "Host-Sicherung: $target (API/Mailer bis zum anschließenden Start gestoppt)" ;;
 *) echo 'control-host.sh start|stop|status|logs|admin|backup' >&2;exit 2 ;;
esac
