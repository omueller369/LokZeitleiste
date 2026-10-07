#!/usr/bin/env bash
# Ubuntu Server 26.04.1 LTS verwendet den gemeinsamen Installer.
set -euo pipefail
exec bash "$(dirname -- "${BASH_SOURCE[0]}")/install.sh" "$@"
