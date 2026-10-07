#!/usr/bin/env bash
# Ermittelt nur Paketquelle und Suite; keine Systemänderungen.
select_platform() {
  case "${ID:-}:${VERSION_ID:-}" in
    ubuntu:26.04|ubuntu:26.04.*)
      [[ "${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}" == resolute ]] || return 1
      DOCKER_REPO=https://download.docker.com/linux/ubuntu
      DOCKER_SUITE=resolute
      ;;
    debian:12)
      [[ "${VERSION_CODENAME:-}" == bookworm ]] || return 1
      DOCKER_REPO=https://download.docker.com/linux/debian
      DOCKER_SUITE=bookworm
      ;;
    debian:13)
      [[ "${VERSION_CODENAME:-}" == trixie ]] || return 1
      DOCKER_REPO=https://download.docker.com/linux/debian
      DOCKER_SUITE=trixie
      ;;
    *) return 1 ;;
  esac
  export DOCKER_REPO DOCKER_SUITE
}
