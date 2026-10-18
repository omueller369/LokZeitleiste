#!/usr/bin/env bash
# Öffentliche Demo auf einem dedizierten Ubuntu-Server, mit internem Test-Mailversand.
set -Eeuo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
domain=ctl-software.io-goerlitz.eu
server_ip=212.227.86.251
email=''
bind_update=false
check=false
while (($#)); do
 case "$1" in
  --email) (($#>=2)) || { echo 'E-Mail fehlt' >&2; exit 2; };email=$2;shift 2 ;;
  --check) check=true;shift ;;
  --bind-update) bind_update=true;shift ;;
  --help|-h) echo 'sudo bash setup-demo.sh --email DEINE-EMAIL [--check] [--bind-update]';exit 0 ;;
  *) echo "Unbekannte Option: $1" >&2;exit 2 ;;
 esac
done
die(){ echo "FEHLER: $*" >&2;exit 1; }
[[ $(uname -s) == Linux ]] || die 'Im Ubuntu-Server ausführen.'
command -v python3 >/dev/null || die 'Zuerst sudo apt install python3 ausführen.'
# Optional nur den Demo-Host in einer bereits lokal dynamisch aktualisierbaren Zone ändern.
if [[ $bind_update == true && $check == false ]]; then
 [[ $EUID == 0 ]] || die '--bind-update benötigt sudo.'
 command -v nsupdate >/dev/null || die 'nsupdate fehlt: sudo apt install bind9-dnsutils'
 nsupdate -l <<'DNS'
zone io-goerlitz.eu.
prereq nxrrset ctl-software.io-goerlitz.eu. CNAME
prereq nxrrset ctl-software.io-goerlitz.eu. AAAA
update delete ctl-software.io-goerlitz.eu. A
update add ctl-software.io-goerlitz.eu. 300 A 212.227.86.251
send
DNS
fi
# DNS muss ausschließlich auf diesen IPv4-Server zeigen. IPv6 nicht stillschweigend ignorieren.
python3 "$root/setup/demo-config.py" dns "$domain" "$server_ip"
for site in http https; do
 file="/etc/apache2/sites-available/lokzeitleiste-ctl-demo-$site.conf"
 [[ ! -e "$file" ]] || head -1 "$file" | grep -qx '# Managed by LokZeitleiste demo setup' || die "Fremde Konfiguration: $file"
done
if [[ -d /etc/apache2/sites-enabled ]]; then
 conflicts=$(grep -RilE '^[[:space:]]*Server(Name|Alias)[[:space:]]+([^#]*[[:space:]])?ctl-software\.io-goerlitz\.eu([[:space:]]|$)' /etc/apache2/sites-enabled 2>/dev/null | grep -v '/lokzeitleiste-ctl-demo-' || true)
 [[ -z "$conflicts" ]] || die "Domain bereits anderweitig in Apache eingerichtet: $conflicts"
fi
if [[ $check == true ]]; then
 bash "$root/setup.sh" --check
 echo "Demo-Vorprüfung beendet: https://$domain. TCP 80/443 müssen beim Provider freigegeben sein."
 exit 0
fi
[[ $EUID == 0 ]] || die 'Mit sudo ausführen.'
[[ "$email" =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]] || die '--email für das Zertifikatskonto angeben.'
# Der bestehende Stack bleibt erhalten und wird vor Änderungen gesichert.
if [[ -e "$root/backend/.env.test" ]]; then bash "$root/setup-update.sh";else bash "$root/setup-new.sh";fi
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y certbot
for port in 80 443; do
 listening=$(ss -H -ltnp "sport = :$port")
 [[ -z "$listening" || "$listening" == *'"apache2"'* ]] || die "Port $port durch anderen Dienst belegt."
done
a2enmod proxy proxy_http headers ssl rewrite
install -d -m 0755 /var/www/lokzeitleiste-acme
activate_site(){
 local source=$1 name=$2 target="/etc/apache2/sites-available/$2" old enabled=false existed=false
 old=$(mktemp)
 [[ ! -e "$target" ]] || { cp -p "$target" "$old";existed=true; }
 [[ ! -e "/etc/apache2/sites-enabled/$name" ]] || enabled=true
 install -m 0644 "$source" "$target"
 a2ensite "$name"
 if ! apache2ctl configtest; then
  [[ $enabled == true ]] || a2dissite "$name"
  if [[ $existed == true ]];then cp -p "$old" "$target";else rm -f "$target";fi
  rm -f "$old";die 'Apache-Konfiguration zurückgenommen; keine neue Konfiguration geladen.'
 fi
 rm -f "$old"
 systemctl reload apache2
}
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
python3 "$root/setup/demo-config.py" apache http "$domain" > "$work/http.conf"
activate_site "$work/http.conf" lokzeitleiste-ctl-demo-http.conf
# HTTP veröffentlicht nur ACME-Challenges; die Anwendung wird ausschließlich über TLS proxiert.
certbot certonly --webroot -w /var/www/lokzeitleiste-acme --cert-name "$domain" -d "$domain" \
 --non-interactive --agree-tos --email "$email" --keep-until-expiring
python3 "$root/setup/demo-config.py" apache https "$domain" > "$work/https.conf"
# Sichere Cookies und Origin vor Freigabe des HTTPS-Proxys aktivieren.
python3 "$root/setup/demo-config.py" env "$root/backend/.env.test" "$domain"
compose=(docker compose --project-directory "$root/backend" --env-file "$root/backend/.env.test" -f "$root/backend/compose.test.yaml")
"${compose[@]}" up -d --build --wait --wait-timeout 240 api mailer
activate_site "$work/https.conf" lokzeitleiste-ctl-demo-https.conf
install -d -m 0755 /etc/letsencrypt/renewal-hooks/deploy
cat > /etc/letsencrypt/renewal-hooks/deploy/lokzeitleiste-ctl-apache <<'HOOK'
#!/usr/bin/env sh
apache2ctl configtest && systemctl reload apache2
HOOK
chmod 0755 /etc/letsencrypt/renewal-hooks/deploy/lokzeitleiste-ctl-apache
systemctl enable --now certbot.timer
curl --fail --silent --show-error --resolve "$domain:443:127.0.0.1" "https://$domain/health"
echo
printf 'Demo bereit: https://%s/admin\nTF-Portal: https://%s/tf\n' "$domain" "$domain"
echo 'Admin-Passwort (nur bei erstmaliger Anlage): sudo cat /var/lib/lokzeitleiste/admin-initial-password'
echo 'Testpostfach ausschließlich über SSH-Tunnel auf localhost:8025. Keine echten E-Mails versendet.'
