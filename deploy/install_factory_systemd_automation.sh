#!/usr/bin/env bash
set -euo pipefail
umask 077
repo="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
runtime="/home/githubops/factory-runtime/operations/autonomous-product-runtime"

if [ "${SAEIT_FACTORY_SYSTEMD_INSTALL_APPROVED:-}" != "1" ]; then
  echo FACTORY_SYSTEMD_INSTALL_APPROVAL_REQUIRED >&2
  exit 1
fi
test "$(id -u)" -eq 0
test -d /home/githubops/factory-runtime
test -x "$runtime/run-local-cycle.sh"
test -f "$repo/scripts/factory-runtime-watchdog.sh"
test -f deploy/systemd/saeit-factory-cycle.service
test -f deploy/systemd/saeit-factory-cycle.timer
test -f deploy/systemd/saeit-factory-watchdog.service
test -f deploy/systemd/saeit-factory-watchdog.timer

install -d -m 700 "$runtime"
install -m 700 "$repo/scripts/factory-runtime-watchdog.sh" "$runtime/factory-runtime-watchdog.sh"
install -m 644 deploy/systemd/saeit-factory-cycle.service /etc/systemd/system/saeit-factory-cycle.service
install -m 644 deploy/systemd/saeit-factory-cycle.timer /etc/systemd/system/saeit-factory-cycle.timer
install -m 644 deploy/systemd/saeit-factory-watchdog.service /etc/systemd/system/saeit-factory-watchdog.service
install -m 644 deploy/systemd/saeit-factory-watchdog.timer /etc/systemd/system/saeit-factory-watchdog.timer
systemctl daemon-reload
systemctl enable --now saeit-factory-cycle.timer
systemctl enable --now saeit-factory-watchdog.timer
systemctl --no-pager --full status saeit-factory-cycle.timer saeit-factory-watchdog.timer
