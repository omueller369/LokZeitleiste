#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
[[ $EUID -eq 0 ]] || { echo 'Benutzerdienst benötigt root.' >&2; exit 1; }
command -v setfacl >/dev/null
# The root-run helper is copied to a root-owned path; it never imports project code.
install -d -m 755 /usr/local/lib/lokzeitleiste
install -m 644 "$root/setup/provision-users.py" /usr/local/lib/lokzeitleiste/provision-users.py
# Encode the project path for systemd's EnvironmentFile instead of shell interpolation.
python3 - "$root/backend" <<'PY'
import sys
from pathlib import Path
path=sys.argv[1]
if any(c in path for c in '\n\r\x00'):raise SystemExit('Invalid installation path')
encoded=path.replace('\\','\\\\').replace('"','\\"')
Path('/etc/lokzeitleiste-users.env').write_text('LOKZEITLEISTE_BACKEND="'+encoded+'"\n')
Path('/etc/lokzeitleiste-users.env').chmod(0o600)
PY
cat > /etc/systemd/system/lokzeitleiste-users.service <<'UNIT'
[Unit]
Description=LokZeitleiste Linux user directories and ACLs
After=docker.service
Requires=docker.service
[Service]
Type=oneshot
EnvironmentFile=/etc/lokzeitleiste-users.env
ExecStart=/usr/bin/python3 /usr/local/lib/lokzeitleiste/provision-users.py --backend ${LOKZEITLEISTE_BACKEND}
UMask=0077
UNIT
cat > /etc/systemd/system/lokzeitleiste-users.timer <<'UNIT'
[Unit]
Description=Provision new LokZeitleiste accounts
[Timer]
OnBootSec=60
OnUnitActiveSec=60
Persistent=true
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now lokzeitleiste-users.timer
systemctl start lokzeitleiste-users.service
