#!/usr/bin/env bash
set -Eeuo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
case_dir=$(mktemp -d)
trap 'rm -rf -- "$case_dir"' EXIT
export DEMO_BIND_TEST_DIR="$case_dir"
mkdir -p "$case_dir/project" "$case_dir/bin"
cp "$root/setup-demo.sh" "$case_dir/project/"
cat > "$case_dir/bin/python3" <<'MOCK'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$DEMO_BIND_TEST_DIR/python-calls"
MOCK
cat > "$case_dir/bin/nsupdate" <<'MOCK'
#!/usr/bin/env bash
[[ "$*" == -l ]] || exit 2
cat > "$DEMO_BIND_TEST_DIR/dns-update"
MOCK
cat > "$case_dir/project/setup.sh" <<'MOCK'
#!/usr/bin/env bash
[[ "$*" == --check ]]
MOCK
cat > "$case_dir/project/setup-new.sh" <<'MOCK'
#!/usr/bin/env bash
exit 77
MOCK
chmod +x "$case_dir/bin/"*
export PATH="$case_dir/bin:$PATH"
bash "$case_dir/project/setup-demo.sh" --bind-update --check
[[ ! -e "$case_dir/dns-update" ]]
rg -q 'dns ctl-software.io-goerlitz.eu 212.227.86.251' "$case_dir/python-calls"
if (( EUID == 0 )); then
 status=0
 bash "$case_dir/project/setup-demo.sh" --bind-update --email demo@example.org || status=$?
 [[ $status == 77 ]]
 rg -q '^zone io-goerlitz.eu\.$' "$case_dir/dns-update"
 [[ $(rg -c '^update (add|delete) ctl-software\.io-goerlitz\.eu\.' "$case_dir/dns-update") == 2 ]]
 ! rg -q '^update (add|delete) io-goerlitz\.eu\.' "$case_dir/dns-update"
 rg -q '^prereq nxrrset ctl-software.io-goerlitz.eu. AAAA$' "$case_dir/dns-update"
fi
echo 'Demo/BIND: Subdomain, read-only check und auf einzelnen Host begrenztes Update geprüft.'
