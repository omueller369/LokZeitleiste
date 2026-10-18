#!/usr/bin/env bash
set -Eeuo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
case_dir=$(mktemp -d)
trap 'rm -rf -- "$case_dir"' EXIT
mkdir -p "$case_dir/project/backend/testenv/certs" "$case_dir/bin"
cp "$root/setup-new.sh" "$root/setup-update.sh" "$case_dir/project/"
export CASE_DIR="$case_dir"
cat > "$case_dir/project/setup.sh" <<'MOCK'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$CASE_DIR/setup-calls"
MOCK
cat > "$case_dir/bin/docker" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "$CASE_DIR/docker-calls"
case "$*" in
  info) exit 0 ;;
  'volume ls --format {{.Name}}') echo lokzeitleiste-test_mysql_test_data ;;
  *'exec -T db sh -c '*) echo 'CREATE TABLE sample (id INT);' ;;
esac
MOCK
chmod +x "$case_dir/bin/docker"
export PATH="$case_dir/bin:$PATH"
bash "$case_dir/project/setup-new.sh" --check
[[ $(cat "$case_dir/setup-calls") == --check ]]
[[ ! -e "$case_dir/docker-calls" ]]
if ((EUID != 0)); then echo 'Root-Ausführungsfälle übersprungen; --check geprüft.'; exit 0; fi
if bash "$case_dir/project/setup-new.sh"; then echo 'Vorhandenes Volume akzeptiert'; exit 1; fi
if bash "$case_dir/project/setup-update.sh"; then echo 'Fehlende Konfiguration akzeptiert'; exit 1; fi
printf 'MYSQL_PASSWORD=private-test\n' > "$case_dir/project/backend/.env.test"
printf certificate > "$case_dir/project/backend/testenv/certs/cert"
mkdir -p "$case_dir/project/TF/787123/Dokumente"
printf original > "$case_dir/project/TF/787123/Dokumente/test.txt"
bash "$case_dir/project/setup-update.sh" --skip-admin
backup=$(find "$case_dir/project/backend/testenv/backups" -mindepth 1 -maxdepth 1 -type d)
[[ $(stat -c %a "$backup") == 700 ]]
gzip -dc "$backup/database.sql.gz" | rg -q 'CREATE TABLE'
tar -xOf "$backup/documents.tar.gz" TF/787123/Dokumente/test.txt | rg -q original
tar -xOf "$backup/config.tar.gz" backend/.env.test | rg -q private-test
[[ $(cat "$case_dir/project/TF/787123/Dokumente/test.txt") == original ]]
[[ $(tail -n1 "$case_dir/setup-calls") == --skip-admin ]]
! rg -q 'down|--volumes|reset' "$case_dir/docker-calls"
echo 'Setup-Einstiege: read-only, Schutz vorhandener Daten, Sicherungen und Argumentweitergabe geprüft.'
