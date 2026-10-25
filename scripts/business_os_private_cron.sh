#!/usr/bin/env bash
# Private staging diagnostics only. No production Django code, websites,
# payment rails, approvals, AgentTask queues or wallets are changed.
set -euo pipefail
umask 077
test "$#" -eq 2
mode="$1"
node="$2"
case "$node" in vps|cpanel) ;; *) exit 64;; esac
case "$mode" in --run|--install|--uninstall) ;; *) exit 64;; esac
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
release="${root##*/}"
[[ "$release" =~ ^business-os-[0-9a-f]{12}$ ]]
if test "$node" = vps; then
  test "$root" = "$HOME/saeit-business-os-staging/releases/$release"
else
  test "$root" = "/home/zomorod2/Saeit-staging/releases/$release"
fi
test ! -L "$root/private"
test -d "$root/private"
test "$(stat -c %a "$root/private")" = 700
command -v flock >/dev/null
command -v timeout >/dev/null
if test "$mode" = --run; then
  cd "$root"
  if test "$node" = vps; then
    python3 -B scripts/business_os_vps_private_factory_metrics.py >/dev/null 2>&1
    python3 -B scripts/business_os_private_control.py --node vps >/dev/null 2>&1
    export SAEIT_ENV=production MOJ_FACTORY_LOCAL_MODE=1 DJANGO_SETTINGS_MODULE=config.settings
    "$HOME/factory-runtime/.venv/bin/python" -B scripts/business_os_vps_private_master_probe.py >/dev/null 2>&1
  else
    bash scripts/business_os_cpanel_private_run.sh >/dev/null 2>&1
    python3 -B scripts/business_os_private_control.py --node cpanel >/dev/null 2>&1
  fi
  exit 0
fi
command -v crontab >/dev/null || exit 71
marker=SAEIT_BUSINESS_OS_PRIVATE_V1
back="$root/private/cron-before-$(date -u +%Y%m%dT%H%M%SZ)-$$"
error="$root/private/.cron-list-error-$$"
if ! crontab -l > "$back" 2> "$error"; then
  if ! grep -qi 'no crontab for' "$error"; then
    rm -f "$back" "$error"
    echo PRIVATE_CRON_SOURCE_UNAVAILABLE >&2
    exit 72
  fi
fi
rm -f "$error"
chmod 600 "$back"
next="$root/private/.cron-new-$$"
grep -Fv "# $marker" "$back" > "$next" || :
if test "$mode" = --install; then
  flock_bin="$(command -v flock)"
  timeout_bin="$(command -v timeout)"
  { test "$flock_bin" = /usr/bin/flock || test "$flock_bin" = /bin/flock; } || exit 76
  { test "$timeout_bin" = /usr/bin/timeout || test "$timeout_bin" = /bin/timeout; } || exit 76
  printf '*/15 * * * * %s -n %s/private/cycle.lock %s 110s /bin/bash %s/scripts/business_os_private_cron.sh --run %s >/dev/null 2>&1 # %s\n' \
    "$flock_bin" "$root" "$timeout_bin" "$root" "$node" "$marker" >> "$next"
fi
chmod 600 "$next"
# Detect unrelated edits before the single, narrow cron replacement.
current="$root/private/.cron-current-$$"
crontab -l > "$current" 2>/dev/null || :
if ! cmp -s "$back" "$current"; then
  rm -f "$next" "$current"
  echo PRIVATE_CRON_CHANGED_CONCURRENTLY >&2
  exit 73
fi
rm -f "$current"
rollback() {
  if test "${installed:-0}" = 1; then
    crontab "$back" || :
  fi
}
trap rollback EXIT
crontab "$next" || exit 74
installed=1
count="$(crontab -l | grep -Fc "# $marker" || :)"
if test "$mode" = --install; then test "$count" = 1 || exit 75
else test "$count" = 0 || exit 75
fi
installed=0
trap - EXIT
rm -f "$next"
echo BUSINESS_OS_PRIVATE_CRON_APPLIED
