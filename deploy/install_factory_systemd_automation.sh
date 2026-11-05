#!/usr/bin/env bash
set -euo pipefail
umask 077

if [ "${SAEIT_FACTORY_SYSTEMD_INSTALL_APPROVED:-}" != "1" ]; then
  echo FACTORY_SYSTEMD_INSTALL_APPROVAL_REQUIRED >&2
  exit 1
fi
test "$(id -u)" -eq 0
test -d /home/githubops/factory-runtime
test -x /home/githubops/factory-runtime/operations/autonomous-product-runtime/run-local-cycle.sh
test -f /home/githubops/factory-runtime/operations/autonomous-product-runtime/factory-runtime-watchdog.sh
test -f deploy/systemd/saeit-factory-cycle.service
test -f deploy/systemd/saeit-factory-cycle.timer
test -f deploy/systemd/saeit-factory-watchdog.service
test -f deploy/systemd/saeit-factory-watchdog.timer

install -m 644 deploy/systemd/saeit-factory-cycle.service /etc/systemd/system/saeit-factory-cycle.service
install -m 644 deploy/systemd/saeit-factory-cycle.timer /etc/systemd/system/saeit-factory-cycle.timer
install -m 644 deploy/systemd/saeit-factory-watchdog.service /etc/systemd/system/saeit-factory-watchdog.service
install -m 644 deploy/systemd/saeit-factory-watchdog.timer /etc/systemd/system/saeit-factory-watchdog.timer
systemctl daemon-reload
systemctl enable --now saeit-factory-cycle.timer
systemctl enable --now saeit-factory-watchdog.timer
systemctl --no-pager --full status saeit-factory-cycle.timer saeit-factory-watchdog.timer
