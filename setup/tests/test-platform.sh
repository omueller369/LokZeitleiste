#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=setup/platform.sh
source "$(dirname -- "${BASH_SOURCE[0]}")/../platform.sh"
check() (
  ID=$1 VERSION_ID=$2 VERSION_CODENAME=$3 UBUNTU_CODENAME=$3
  select_platform || return 1
  [[ "$DOCKER_REPO" == "$4" && "$DOCKER_SUITE" == "$5" ]]
)
check ubuntu 26.04 resolute https://download.docker.com/linux/ubuntu resolute
check ubuntu 26.04.1 resolute https://download.docker.com/linux/ubuntu resolute
check debian 12 bookworm https://download.docker.com/linux/debian bookworm
check debian 13 trixie https://download.docker.com/linux/debian trixie
if check ubuntu 24.04 noble https://download.docker.com/linux/ubuntu noble; then exit 1; fi
if check ubuntu 26.04 noble https://download.docker.com/linux/ubuntu noble; then exit 1; fi
if check linuxmint 26.04 resolute https://download.docker.com/linux/ubuntu resolute; then exit 1; fi
echo 'Plattformprüfung: Ubuntu 26.04/26.04.1 und Debian 12/13 erfolgreich.'
