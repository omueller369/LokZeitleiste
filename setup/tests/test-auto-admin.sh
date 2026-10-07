#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT
export SETUP_TEST_DIR="$test_dir"
cat > "$test_dir/compose" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
if [[ "$*" == *' python -c '* ]]; then
  cat "$SETUP_TEST_DIR/count"
else
  [[ "$*" == 'exec -T api python -m lokzeitleiste.bootstrap_admin administrator' ]]
  IFS= read -r password
  [[ "$password" =~ ^[0-9a-f]{48}$ ]]
  [[ ! -e "$SETUP_TEST_DIR/fail" ]] || exit 1
  printf '%s\n' "$password" > "$SETUP_TEST_DIR/received"
  echo 1 > "$SETUP_TEST_DIR/count"
fi
MOCK
chmod 700 "$test_dir/compose"
echo 0 > "$test_dir/count"
touch "$test_dir/fail"
password_file="$test_dir/credentials/password"
if bash "$root/setup/auto-admin.sh" "$password_file" "$test_dir/compose"; then exit 1; fi
[[ -s "$password_file" && $(stat -c %a "$password_file") == 600 ]]
[[ $(stat -c %a "$test_dir/credentials") == 700 ]]
cp "$password_file" "$test_dir/original"
rm "$test_dir/fail"
bash "$root/setup/auto-admin.sh" "$password_file" "$test_dir/compose"
cmp -s "$password_file" "$test_dir/original"
cmp -s "$password_file" "$test_dir/received"
# Bei bestehendem Admin darf kein neues Passwort erzeugt werden.
bash "$root/setup/auto-admin.sh" "$test_dir/unused/password" "$test_dir/compose"
[[ ! -e "$test_dir/unused" ]]
echo 0 > "$test_dir/count"
ln -s "$test_dir/received" "$test_dir/link"
if bash "$root/setup/auto-admin.sh" "$test_dir/link" "$test_dir/compose"; then exit 1; fi
echo 'Auto-Admin: Passwortschutz, Wiederholung nach Fehler und bestehende Konten geprüft.'
