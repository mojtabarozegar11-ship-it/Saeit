#!/usr/bin/env bash
# Install, query or safely remove ONLY the private factory evidence monitor.
# No modifications to the autonomous factory loop, business DB, site or payments.
set -euo pipefail
umask 077
mode="${1:-status}"
[[ "$mode" =~ ^(status|install|remove)$ ]] || { echo INVALID_MODE; exit 2; }
[[ "$(id -un)" == "githubops" && "$(id -u)" != 0 ]] || { echo SERVICE_USER_REQUIRED; exit 3; }
base="$HOME/factory-runtime"
ops="$base/operations"
stage="$ops/evidence-sidecar-candidate"
script="$stage/scripts/factory_research_sidecar.py"
python="$base/.venv/bin/python"
pidfile="$ops/vps-only-loop.pid"
marker="SAEIT_FACTORY_RESEARCH_EVIDENCE_V1"
run="$stage/run-evidence-hourly.sh"

test -d "$base" && test -d "$ops"
command -v crontab >/dev/null
command -v flock >/dev/null
if [[ "$mode" == status ]]; then
  count="$(crontab -l 2>/dev/null | grep -cF "$marker" || true)"
  echo "PRIVATE_EVIDENCE_MONITOR_CRON_ENTRIES=$count"
  [[ "$count" -le 1 ]] || exit 5
  exit 0
fi
test -r "$pidfile"
read -r pid < "$pidfile"
[[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid"
echo "FACTORY_MAIN_LOOP_ALIVE_PRE_MONITOR_CHANGE"
if ! systemctl is-active --quiet cron 2>/dev/null && ! systemctl is-active --quiet crond 2>/dev/null; then
  echo CRON_SERVICE_INACTIVE
  exit 4
fi
mkdir -p "$ops/backups"
chmod 700 "$ops/backups"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="$ops/backups/evidence-sidecar-crontab-$stamp.txt"
crontab -l > "$backup" 2>/dev/null || : > "$backup"
chmod 600 "$backup"
tmp="$(mktemp "$ops/.evidence-cron.XXXXXXXX")"
trap 'rm -f -- "$tmp"' EXIT
grep -vF "$marker" "$backup" > "$tmp" || true
if [[ "$mode" == install ]]; then
  test -x "$python"
  test -f "$script" && test ! -L "$script"
  test -f "$stage/scripts/factory_evidence_quality.py"
  test -f "$stage/scripts/factory_first_product_pilot.py"
  "$python" -m py_compile "$script" "$stage/scripts/factory_evidence_quality.py"
  wrapper_tmp="$(mktemp "$stage/.evidence-run.XXXXXXXX")"
  trap 'rm -f -- "$tmp" "$wrapper_tmp"' EXIT
  cat > "$wrapper_tmp" <<'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
umask 077
base="$HOME/factory-runtime"
ops="$base/operations"
stage="$ops/evidence-sidecar-candidate"
exec 9>"$ops/evidence-sidecar-monitor.lock"
flock -n 9 || exit 0
# Obtain the live ORM database path from Django settings, not a guessed db.sqlite3.
django_db="$(cd "$base/django-app" && \
  DJANGO_SETTINGS_MODULE=config.settings SAEIT_ENV=production MOJ_FACTORY_LOCAL_MODE=1 \
  "$base/.venv/bin/python" -c 'from django.conf import settings; print(settings.DATABASES["default"]["NAME"])')"
test -s "$django_db"
exec nice -n 15 timeout 50s "$base/.venv/bin/python" \
  "$stage/scripts/factory_research_sidecar.py" \
  --db "$base/private/factory-fresh-isolated.sqlite3" \
  --compare-db "$django_db" \
  --out "$base/private/research-evidence-sidecar" \
  --limit 50 > "$ops/evidence-sidecar-monitor-last.log" 2>&1
WRAPPER
  chmod 700 "$wrapper_tmp"
  bash -n "$wrapper_tmp"
  mv -f "$wrapper_tmp" "$run"
  printf '43 * * * * /bin/bash %s # %s\n' "$run" "$marker" >> "$tmp"
fi
chmod 600 "$tmp"
if ! crontab "$tmp"; then
  echo CRONTAB_INSTALL_FAILED_OR_DENIED
  exit 6
fi
count="$(crontab -l | grep -cF "$marker" || true)"
if [[ "$mode" == install && "$count" != 1 ]] ||
   [[ "$mode" == remove && "$count" != 0 ]]; then
  crontab "$backup" || true
  echo CRON_VERIFICATION_FAILED_RESTORED_BACKUP
  exit 7
fi
read -r after < "$pidfile"
[[ "$after" =~ ^[0-9]+$ ]] && kill -0 "$after"
echo FACTORY_MAIN_LOOP_ALIVE_POST_MONITOR_CHANGE
echo "PRIVATE_EVIDENCE_MONITOR_CRON_ENTRIES=$count"
echo "PRIVATE_EVIDENCE_MONITOR_MODE=$mode"
echo "MAIN_FACTORY_CRON_ENTRIES_PRESERVED"
echo "STORE_PUBLICATION_UNCHANGED"
