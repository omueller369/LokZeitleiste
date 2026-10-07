#!/usr/bin/env bash
# LokZeitleiste: eigenständige Debian-Testumgebung mit Apache/MySQL/Python/Mailpit.
set -Eeuo pipefail
ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
BACKEND_DIR="$ROOT_DIR/backend"
CHECK_ONLY=false
ADMIN_USER=''
ADMIN_PASSWORD_FILE=''
SKIP_ADMIN=false
usage() {
  cat <<'HELP'
Verwendung:
  bash setup/install-debian.sh --check
  sudo bash setup/install-debian.sh
  sudo bash setup/install-debian.sh --admin-user USER --admin-password-file /pfad/passwort
  sudo bash setup/install-debian.sh --skip-admin
--check ist lesend und installiert nichts. Ohne Optionen wird ein Admin interaktiv angelegt.
HELP
}
die() { echo "FEHLER: $*" >&2; exit 1; }
while (($#)); do
  case "$1" in
    --check) CHECK_ONLY=true; shift ;;
    --skip-admin) SKIP_ADMIN=true; shift ;;
    --admin-user) (($# >= 2)) || die 'Benutzername fehlt'; ADMIN_USER=$2; shift 2 ;;
    --admin-password-file) (($# >= 2)) || die 'Passwortdatei fehlt'; ADMIN_PASSWORD_FILE=$2; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) die "Unbekannte Option: $1" ;;
  esac
done
[[ -r /etc/os-release ]] || die 'Betriebssystem nicht erkennbar'
# shellcheck source=/dev/null
. /etc/os-release
[[ "${ID:-}" == debian ]] || die 'Nur Debian wird unterstützt'
[[ "${VERSION_ID:-}" == 12 || "${VERSION_ID:-}" == 13 ]] || die 'Debian 12 oder 13 erforderlich'
[[ "${VERSION_CODENAME:-}" == bookworm || "${VERSION_CODENAME:-}" == trixie ]] || die 'Nicht unterstützte Debian-Paketquelle'
arch=$(dpkg --print-architecture)
[[ "$arch" == amd64 || "$arch" == arm64 ]] || die 'Der MySQL-Teststack unterstützt hier amd64 oder arm64'
[[ -d /run/systemd/system ]] || die 'Debian muss mit systemd gestartet sein'
for file in backend/compose.test.yaml backend/Dockerfile backend/requirements.txt backend/testenv/prepare.sh backend/testenv/control.sh backend/apache/lokzeitleiste-local.conf; do
  [[ -r "$ROOT_DIR/$file" ]] || die "Projektdatei fehlt: $file"
done
if [[ -n "$ADMIN_USER" || -n "$ADMIN_PASSWORD_FILE" ]]; then
  [[ -n "$ADMIN_USER" && -n "$ADMIN_PASSWORD_FILE" ]] || die 'Admin-Benutzername und Passwortdatei gemeinsam angeben'
  [[ "$SKIP_ADMIN" == false ]] || die '--skip-admin nicht mit Admin-Optionen kombinieren'
  [[ "$ADMIN_USER" =~ ^[a-z0-9._-]{3,64}$ ]] || die 'Admin-Name: 3–64 Kleinbuchstaben, Ziffern, Punkt, Unterstrich oder Bindestrich'
  [[ -f "$ADMIN_PASSWORD_FILE" && -r "$ADMIN_PASSWORD_FILE" ]] || die 'Passwortdatei nicht lesbar'
  ADMIN_PASSWORD_FILE=$(realpath -- "$ADMIN_PASSWORD_FILE")
  mode=$(stat -c %a -- "$ADMIN_PASSWORD_FILE")
  (( (8#$mode & 077) == 0 )) || die 'Passwortdatei darf nur für ihren Eigentümer lesbar sein (chmod 600)'
fi
if [[ "$CHECK_ONLY" == false ]]; then
  (( EUID == 0 )) || die 'Installation mit sudo ausführen'
  if [[ "$SKIP_ADMIN" == false && -z "$ADMIN_USER" && ! -t 0 ]]; then
    die 'Ohne Terminal: --admin-user und --admin-password-file verwenden'
  fi
fi
SITE=/etc/apache2/sites-available/lokzeitleiste-local.conf
SOURCE_SITE="$BACKEND_DIR/apache/lokzeitleiste-local.conf"
[[ ! -e "$SITE" ]] || cmp -s "$SITE" "$SOURCE_SITE" || die 'Vorhandene abweichende Apache-Site bitte zuerst prüfen'
# Andere Listen-Direktiven für denselben Port würden Apache am Start hindern.
if [[ -d /etc/apache2 ]]; then
  matches=$(grep -RInE '^[[:space:]]*Listen[[:space:]]+([^#[:space:]]*:)?8080([[:space:]]|$)' /etc/apache2/ports.conf /etc/apache2/conf-enabled /etc/apache2/sites-enabled 2>/dev/null || true)
  foreign=$(printf '%s\n' "$matches" | grep -v '/lokzeitleiste-local.conf:' || true)
  [[ -z "$foreign" ]] || die 'Port 8080 ist bereits durch eine andere Apache-Listen-Direktive konfiguriert'
fi
if command -v ss >/dev/null; then
  for port in 8000 8025 8080; do
    listening=$(ss -H -ltn "sport = :$port")
    [[ -n "$listening" ]] || continue
    if [[ "$port" == 8080 && -e "$SITE" ]] && cmp -s "$SITE" "$SOURCE_SITE"; then
      continue
    fi
    owned=''
    if command -v docker >/dev/null && [[ "$port" != 8080 ]]; then
      owned=$(docker ps --filter label=com.docker.compose.project=lokzeitleiste-test --format '{{.Ports}}' 2>/dev/null | grep -F "127.0.0.1:$port->" || true)
    fi
    [[ -n "$owned" ]] || die "Port $port ist belegt; anderen Dienst zuerst prüfen"
  done
fi
free_mb=$(df -Pm "$ROOT_DIR" | awk 'NR==2 {print $4}')
(( free_mb >= 5120 )) || die 'Mindestens 5 GB freier Speicher für Container erforderlich (20 GB empfohlen)'
echo "Debian $VERSION_ID ($arch); Projekt und Ports geprüft; freier Speicher: ${free_mb} MB."
missing=()
for pkg in apache2 openssh-server git python3 openssl ca-certificates curl iproute2; do
  if ! dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -qx 'install ok installed'; then
    missing+=("$pkg")
  fi
done
if ((${#missing[@]})); then echo "Fehlende Pakete: ${missing[*]}"; else echo 'Systempakete vorhanden.'; fi
docker_ready=false
if command -v docker >/dev/null && docker compose version >/dev/null 2>&1; then
  docker compose up --help | grep -q -- --wait-timeout || die 'Docker Compose ist zu alt; Version mit --wait-timeout installieren'
  docker_ready=true
  echo 'Docker und Compose vorhanden.'
else
  echo 'Docker Engine und/oder Compose fehlen.'
  # Keine bestehenden Containerplattformen automatisch deinstallieren.
  for pkg in docker.io docker-compose docker-doc docker-buildx podman-docker containerd runc; do
    if dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -qx 'install ok installed'; then
      die "Paket $pkg kollidiert mit Docker CE; bestehende Installation manuell abgleichen"
    fi
  done
fi
if [[ "$CHECK_ONLY" == true ]]; then
  echo 'Vorprüfung beendet. Netzwerkdownloads, Docker-Daemon und Laufzeitdienste werden erst bei Installation geprüft.'
  exit 0
fi
trap 'echo "Setup fehlgeschlagen (Zeile $LINENO). Testdaten bleiben erhalten. Hinweise: sudo bash backend/testenv/control.sh logs" >&2' ERR
export DEBIAN_FRONTEND=noninteractive
if ((${#missing[@]})); then
  apt-get update
  apt-get install -y "${missing[@]}"
fi
if [[ "$docker_ready" == false ]]; then
  # Bestehende benutzerdefinierte Docker-Quellen nicht überschreiben.
  if grep -Rqs 'download.docker.com/linux/debian' /etc/apt/sources.list /etc/apt/sources.list.d 2>/dev/null; then
    echo 'Vorhandene Docker-APT-Quelle wird verwendet.'
  else
    [[ ! -e /etc/apt/sources.list.d/docker.sources && ! -e /etc/apt/keyrings/docker.asc ]] || die 'Vorhandene Docker-Quelldateien zuerst prüfen'
    install -d -m 0755 /etc/apt/keyrings
    curl --fail --silent --show-error --location --retry 3 --connect-timeout 15 https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
    chmod 0644 /etc/apt/keyrings/docker.asc
    cat > /etc/apt/sources.list.d/docker.sources <<DOCKER_SOURCE
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: $VERSION_CODENAME
Components: stable
Architectures: $arch
Signed-By: /etc/apt/keyrings/docker.asc
DOCKER_SOURCE
  fi
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker
systemctl enable --now apache2
systemctl enable --now ssh
docker info >/dev/null
docker compose version
bash "$BACKEND_DIR/testenv/prepare.sh"
bash "$BACKEND_DIR/testenv/control.sh" start
# Kein Stoppen/Löschen vorhandener Datenbanken und kein automatischer Import.
a2enmod proxy proxy_http
created_site=false
[[ -e "$SITE" ]] || { install -m 0644 "$SOURCE_SITE" "$SITE"; created_site=true; }
was_enabled=false
[[ -e /etc/apache2/sites-enabled/lokzeitleiste-local.conf ]] && was_enabled=true
a2ensite lokzeitleiste-local.conf
if ! apache2ctl configtest; then
  [[ "$was_enabled" == true ]] || a2dissite lokzeitleiste-local.conf
  [[ "$created_site" == false ]] || rm -- "$SITE"
  die 'Apache-Konfiguration ungültig; neue Site zurückgenommen, Apache wurde nicht neu geladen'
fi
systemctl reload apache2
curl --fail --silent --show-error --retry 5 --retry-connrefused http://localhost:8080/health
curl --fail --silent --show-error http://localhost:8080/admin >/dev/null
curl --fail --silent --show-error http://localhost:8025/api/v1/messages >/dev/null
compose=(docker compose --project-directory "$BACKEND_DIR" --env-file "$BACKEND_DIR/.env.test" -f "$BACKEND_DIR/compose.test.yaml")
if [[ "$SKIP_ADMIN" == false ]]; then
  admin_count=$("${compose[@]}" exec -T api python -c 'from sqlalchemy import select, func; from sqlalchemy.orm import Session; from lokzeitleiste.db import engine; from lokzeitleiste.models import User; db=Session(engine()); print(db.scalar(select(func.count()).select_from(User).where(User.role=="admin", User.active==True)))')
  if [[ -n "$ADMIN_USER" ]]; then
    "${compose[@]}" exec -T api python -m lokzeitleiste.bootstrap_admin "$ADMIN_USER" < "$ADMIN_PASSWORD_FILE"
  elif (( admin_count == 0 )); then
    bash "$BACKEND_DIR/testenv/control.sh" admin
  else
    echo 'Aktives Admin-Konto vorhanden; Zugangsdaten werden beibehalten.'
  fi
fi
echo
echo 'LokZeitleiste-Testumgebung gestartet.'
echo 'Admin: http://localhost:8080/admin | Testpostfach: http://localhost:8025'
echo 'API: http://localhost:8080/docs'
echo 'Von außerhalb der VM den SSH-Tunnel aus setup/README.md verwenden.'
echo 'End-to-End-Test: python3 backend/testenv/smoke.py'
[[ "$SKIP_ADMIN" == false ]] || echo 'Admin-Anlage übersprungen: sudo bash backend/testenv/control.sh admin'
