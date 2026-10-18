#!/usr/bin/env bash
set -Eeuo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
case_dir=$(mktemp -d)
trap 'rm -rf -- "$case_dir"' EXIT
export HOST_BACKUP_TEST_DIR="$case_dir"
mkdir -p "$case_dir/project/backend/testenv" "$case_dir/bin"
cp "$root/backend/testenv/control-host.sh" "$case_dir/project/backend/testenv/"
touch "$case_dir/project/backend/.env.host"
cat > "$case_dir/bin/docker" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "$HOST_BACKUP_TEST_DIR/calls"
if [[ "$*" == *' ps --services --filter status=running' ]];then cat "$HOST_BACKUP_TEST_DIR/running";fi
MOCK
cat > "$case_dir/bin/python3" <<'MOCK'
#!/usr/bin/env bash
exit 7
MOCK
chmod +x "$case_dir/bin/"*
export PATH="$case_dir/bin:$PATH"
for running in '' api;do
 printf '%s\n' "$running" > "$case_dir/running"
 : > "$case_dir/calls"
 status=0
 bash "$case_dir/project/backend/testenv/control-host.sh" backup || status=$?
 [[ $status == 7 ]]
 if [[ -z "$running" ]];then
  ! rg -q ' start ' "$case_dir/calls"
 else
  rg -q ' start api$' "$case_dir/calls"
  ! rg -q ' start .*mailer' "$case_dir/calls"
 fi
done
echo 'Backup-Abbruch: nur zuvor laufende Dienste wiederhergestellt; keine fehlenden Container gestartet.'
