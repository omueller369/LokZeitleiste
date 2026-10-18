#!/usr/bin/env bash
# Gesicherte Aktualisierung einer vorhandenen Linux-Testumgebung.
set -Eeuo pipefail
umask 077
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
for arg in "$@"; do
  case "$arg" in
    --help|-h) echo 'sudo bash setup-update.sh [--check|--skip-admin|--auto-admin|--admin-user USER --admin-password-file DATEI]'; exit 0 ;;
    --check) exec bash "$root/setup.sh" "$@" ;;
  esac
done
[[ $EUID == 0 && $(uname -s) == Linux ]] || { echo 'Als root im Linux-Gastsystem ausführen.' >&2; exit 1; }
[[ -f "$root/backend/.env.test" && ! -L "$root/backend/.env.test" ]] || { echo 'Keine vorhandene Testkonfiguration. Für Neuinstallation setup-new.sh verwenden.' >&2; exit 1; }
for command in docker tar gzip; do command -v "$command" >/dev/null || { echo "Abhängigkeit fehlt: $command" >&2; exit 1; }; done
docker info >/dev/null
compose=(docker compose --project-directory "$root/backend" --env-file "$root/backend/.env.test" -f "$root/backend/compose.test.yaml")
"${compose[@]}" config --quiet
# Prüft Argumente und Plattform vor jeder Unterbrechung.
bash "$root/setup.sh" --check "$@"
backup=$(mktemp -d "$root/backend/testenv/backups/update-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX" 2>/dev/null) || {
  mkdir -p -- "$root/backend/testenv/backups"
  backup=$(mktemp -d "$root/backend/testenv/backups/update-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")
}
chmod 700 "$backup"
stopped=false
installing=false
finish() {
  status=$?
  if ((status != 0)); then
    echo "Aktualisierung abgebrochen. Sicherungen (ggf. unvollständig): $backup" >&2
    if [[ $stopped == true && $installing == false ]]; then "${compose[@]}" start api mailer || true; fi
    echo 'Kein automatischer Datenbank-Rollback. Status/Logs mit backend/testenv/control.sh prüfen.' >&2
  fi
}
trap finish EXIT
"${compose[@]}" up -d --wait --wait-timeout 180 db
stopped=true
"${compose[@]}" stop api mailer
# Variablen werden ausschließlich innerhalb des Datenbankcontainers ausgewertet.
"${compose[@]}" exec -T db sh -c 'MYSQL_PWD="$MYSQL_PASSWORD" exec mysqldump --single-transaction --no-tablespaces -u "$MYSQL_USER" "$MYSQL_DATABASE"' | gzip > "$backup/database.sql.gz"
gzip -t "$backup/database.sql.gz"
files=()
for role in TF VW; do
  [[ ! -L "$root/$role" ]] || { echo "Symlink als Benutzerwurzel nicht zulässig: $role" >&2; exit 1; }
  [[ ! -e "$root/$role" ]] || files+=("$role")
done
tar --acls --xattrs --numeric-owner -czf "$backup/documents.tar.gz" -C "$root" --files-from /dev/null "${files[@]}"
config=(backend/.env.test)
[[ ! -d "$root/backend/testenv/certs" ]] || config+=(backend/testenv/certs)
tar --acls --xattrs --numeric-owner -czf "$backup/config.tar.gz" -C "$root" "${config[@]}"
tar -tzf "$backup/documents.tar.gz" >/dev/null
tar -tzf "$backup/config.tar.gz" >/dev/null
printf '%s\n' "Projekt: $root" "Zeit: $(date -u +%FT%TZ)" > "$backup/README.txt"
if command -v git >/dev/null && git -C "$root" rev-parse HEAD > "$backup/source-commit.txt" 2>/dev/null; then :; else rm -f "$backup/source-commit.txt"; fi
printf 'Sicherung vollständig: %s\n' "$backup"
installing=true
bash "$root/setup.sh" "$@"
printf 'Aktualisierung abgeschlossen. Sicherung: %s\n' "$backup"
