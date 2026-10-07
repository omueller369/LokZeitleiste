#!/usr/bin/env bash
# Argumente: geschützte Passwortdatei, dann Compose-Kommando als einzelne Argumente.
set -euo pipefail
password_file=$1
shift
admin_count=$("$@" exec -T api python -c 'from sqlalchemy import select, func; from sqlalchemy.orm import Session; from lokzeitleiste.db import engine; from lokzeitleiste.models import User; db=Session(engine()); print(db.scalar(select(func.count()).select_from(User).where(User.role=="admin", User.active==True)))')
[[ "$admin_count" =~ ^[0-9]+$ ]] || { echo 'Admin-Anzahl nicht ermittelbar.' >&2; exit 1; }
if (( admin_count > 0 )); then
  echo 'Aktives Admin-Konto vorhanden; Zugangsdaten werden beibehalten.'
  exit 0
fi
umask 077
password_dir=$(dirname -- "$password_file")
[[ ! -L "$password_dir" && ! -L "$password_file" ]] || { echo 'Passwortpfad darf kein symbolischer Link sein.' >&2; exit 1; }
install -d -m 0700 -- "$password_dir"
if [[ ! -e "$password_file" ]]; then
  # Bei einem fehlgeschlagenen Bootstrap dasselbe Passwort erneut verwenden.
  password=$(openssl rand -hex 24)
  (set -o noclobber; printf '%s\n' "$password" > "$password_file")
  unset password
fi
[[ -f "$password_file" && -O "$password_file" ]] || { echo 'Passwortdatei gehört nicht dem Setup-Benutzer.' >&2; exit 1; }
chmod 0600 -- "$password_file"
"$@" exec -T api python -m lokzeitleiste.bootstrap_admin administrator < "$password_file"
echo "Admin-Benutzer: administrator; Passwortdatei: $password_file (nur für root lesbar)."
