#!/usr/bin/env bash
# Non-destructive discovery of license-verified literature alternatives.
set -euo pipefail
umask 077
test "$#" -eq 1
staged="$1"
test "$(id -un)" = githubops
root='/home/githubops/factory-runtime/private/autonomous-product-cycle'
ops='/home/githubops/factory-runtime/operations/production-instructions'
backups='/home/githubops/factory-runtime/operations/backups'
py='/home/githubops/factory-runtime/.venv/bin/python'
primary="$ops/license-safe-primary-fulltext-acquisition.py"
worker="$ops/license-safe-qc184-alternative-discovery.py"
marker='SAEIT_QC184_LICENSED_ALTERNATIVE_DISCOVERY_20261024'
test -d "$root/production-instructions/stage-02/primary-fulltext-repair-inbox"
test -f "$staged" && test ! -L "$staged"
test -f "$primary" && test ! -L "$primary"
test -x "$py" && test -d "$ops" && test ! -L "$ops"
install -d -m 700 "$backups"
new_hash="$(sha256sum "$staged" | awk '{print $1}')"
if test -e "$worker"; then
  test -f "$worker" && test ! -L "$worker"
  old_hash="$(sha256sum "$worker" | awk '{print $1}')"
  if test "$old_hash" != "$new_hash"; then
    backup="$backups/qc184-alternative-worker-$GITHUB_RUN_ID-$old_hash.py"
    test ! -e "$backup"
    cp -p "$worker" "$backup"
    test "$(sha256sum "$backup" | awk '{print $1}')" = "$old_hash"
  fi
fi
temp_worker="$(mktemp "$ops/.qc184-alternative.XXXXXX")"
trap 'rm -f -- "$temp_worker"' EXIT
install -m 600 "$staged" "$temp_worker"
test "$(sha256sum "$temp_worker" | awk '{print $1}')" = "$new_hash"
mv -f -- "$temp_worker" "$worker"
timeout 100s "$py" -B "$worker" --factory-private "$root" \
  --primary-worker "$primary" --batch 8 --dry-run
timeout 230s "$py" -B "$worker" --factory-private "$root" \
  --primary-worker "$primary" --batch 6
exec 9>"$ops/.qc184-alternative-cron-install.lock"
flock -x 9
cron_backup="$backups/qc184-alternative-crontab-$GITHUB_RUN_ID-$(date -u +%Y%m%dT%H%M%SZ).txt"
(crontab -l 2>/dev/null || true) > "$cron_backup"
chmod 600 "$cron_backup"
if ! grep -Fq "$marker" "$cron_backup"; then
  tmp_cron="$(mktemp "$ops/.qc184-alternative-cron.XXXXXX")"
  trap 'rm -f -- "$temp_worker" "$tmp_cron"' EXIT
  cp "$cron_backup" "$tmp_cron"
  printf '%s\n' "*/5 * * * * /usr/bin/flock -n '$ops/.qc184-alternative-minute.lock' /usr/bin/timeout 230s '$py' -B '$worker' --factory-private '$root' --primary-worker '$primary' --batch 8 >> '$ops/license-safe-qc184-alternative-discovery.log' 2>&1 # $marker" >> "$tmp_cron"
  crontab "$tmp_cron"
fi
crontab -l | grep -F "$marker"
printf '%s\n' 'QC184_ALTERNATIVE_DISCOVERY=PRIVATE_ACTIVE' \
 'ALTERNATIVES_ONLY=NOT_SOURCE_SUBSTITUTIONS' \
 'INDEPENDENT_REVIEW=REQUIRED' 'QC1000_APPROVALS=0' 'PUBLICATIONS=0' \
 "CRONTAB_BACKUP=$cron_backup"
