#!/usr/bin/env bash
# Explicit, repeatable import of the packaged TF demo accounts on the Host-MySQL server.
set -Eeuo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
if [[ ${1:-} == --help || ${1:-} == -h ]];then
 echo 'sudo bash setup-demo-tf.sh'
 echo 'Aktualisiert die Host-MySQL-Demo, sichert Daten und ergänzt 20 Test-TF samt Bildern.'
 echo 'Vorhandene Konten, Passwörter, Arbeitsberichte und Pläne bleiben erhalten.'
 exit 0
fi
(($#==0)) || { echo 'Unbekannte Argumente; --help verwenden.' >&2;exit 2; }
[[ $EUID == 0 && $(uname -s) == Linux ]] || { echo 'Mit sudo auf dem Ubuntu-Server ausführen.' >&2;exit 1; }
[[ -f "$root/backend/.env.host" ]] || { echo 'Zuerst sudo bash setup-demo.sh für Host-MySQL ausführen.' >&2;exit 1; }
command -v flock >/dev/null || { echo 'flock fehlt (Paket util-linux).' >&2;exit 1; }
mkdir -p "$root/backend/testenv"
exec 9>"$root/backend/testenv/demo-tf-import.lock"
flock -n 9 || { echo 'Ein Testdatenimport läuft bereits.' >&2;exit 1; }
# Bring the code/image/schema up to date using the existing backed-up update path.
bash "$root/setup-demo.sh"
compose=(docker compose --project-directory "$root/backend" --env-file "$root/backend/.env.host" -f "$root/backend/compose.host.yaml")
# A second snapshot immediately precedes the data import and stops API/mailer.
bash "$root/backend/testenv/control-host.sh" backup
recover(){
 local status=$?
 trap - EXIT
 if ((status!=0));then
  echo 'Import/Neustart fehlgeschlagen; Sicherung bleibt erhalten. API/Mailer werden wieder gestartet.' >&2
  "${compose[@]}" start api mailer || true
 fi
 exit "$status"
}
trap recover EXIT
"${compose[@]}" run --rm --no-deps -T api python -m lokzeitleiste.accounts.import_demo_tf --seed 23
bash "$root/backend/testenv/control-host.sh" start
trap - EXIT
echo 'Test-TF inklusive Bildern importiert. Die TF-Nummern stehen in der Importausgabe.'
echo 'Neue Konten: Initialpasswort tomcom123456; Passwortwechsel beim ersten Login erforderlich.'
