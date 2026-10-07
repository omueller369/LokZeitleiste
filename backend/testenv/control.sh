#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
[[ -f .env.test ]] || { echo 'Zuerst bash testenv/prepare.sh ausführen.' >&2; exit 1; }
compose=(docker compose --env-file .env.test -f compose.test.yaml)
case "${1:-status}" in
  start) "${compose[@]}" config --quiet; "${compose[@]}" up -d --build --wait --wait-timeout 240 ;;
  stop) "${compose[@]}" stop ;;
  status) "${compose[@]}" ps ;;
  logs) "${compose[@]}" logs --tail 100 ;;
  admin) "${compose[@]}" exec api python -m lokzeitleiste.init_db --create-admin ;;
  backup)
    umask 077
    mkdir -p testenv/backups
    target="testenv/backups/mysql-$(date -u +%Y%m%dT%H%M%SZ).sql"
    "${compose[@]}" exec -T db sh -c 'MYSQL_PWD="$MYSQL_PASSWORD" exec mysqldump --single-transaction --no-tablespaces -u "$MYSQL_USER" "$MYSQL_DATABASE"' > "$target"
    echo "Sicherung: $target" ;;
  *) echo 'Verwendung: control.sh start|stop|status|logs|admin|backup' >&2; exit 2 ;;
esac
