#!/usr/bin/env bash
# Durable, non-destructive, license-gated source acquisition on PRIVATE factory.
set -euo pipefail
umask 077
test "$#" = 1
staged="$1"
root='/home/githubops/factory-runtime/private/autonomous-product-cycle'
ops='/home/githubops/factory-runtime/operations/production-instructions'
py='/home/githubops/factory-runtime/.venv/bin/python'
worker="$ops/license-safe-primary-fulltext-acquisition.py"
marker='SAEIT_LICENSED_PRIMARY_SOURCE_ACQUISITION_20261024'
test "$(id -un)" = githubops
test -f "$staged" && test ! -L "$staged"
test -d "$root/production-instructions/stage-02/primary-fulltext-repair-inbox"
test -x "$py"
test -d "$ops" && test ! -L "$ops"
backup_dir='/home/githubops/factory-runtime/operations/backups'
install -d -m 700 "$backup_dir"
if test -e "$worker"; then
  test ! -L "$worker" && test -f "$worker"
  oldhash="$(sha256sum "$worker" | awk '{print $1}')"
  newhash="$(sha256sum "$staged" | awk '{print $1}')"
  if test "$oldhash" != "$newhash"; then
    backup_worker="$backup_dir/primary-acquisition-worker-$GITHUB_RUN_ID-$oldhash.py"
    test ! -e "$backup_worker"
    cp -p "$worker" "$backup_worker"
    test "$(sha256sum "$backup_worker" | awk '{print $1}')" = "$oldhash"
    newer="$(mktemp "$ops/.primary-worker.XXXXXX")"
    trap 'rm -f -- "$newer"' EXIT
    install -m 600 "$staged" "$newer"
    test "$(sha256sum "$newer" | awk '{print $1}')" = "$newhash"
    mv -f -- "$newer" "$worker"
  fi
else
  install -m 600 "$staged" "$worker"
fi
timeout 90s "$py" -B "$worker" --factory-private "$root" --batch 24 --dry-run
timeout 265s "$py" -B "$worker" --factory-private "$root" --batch 24

backup_dir='/home/githubops/factory-runtime/operations/backups'
install -d -m 700 "$backup_dir"
exec 9>"$ops/.primary-acquisition-cron-install.lock"
flock -x 9
backup="$backup_dir/primary-acquisition-crontab-$GITHUB_RUN_ID-$(date -u +%Y%m%dT%H%M%SZ).txt"
(crontab -l 2>/dev/null || true) > "$backup"
chmod 600 "$backup"
if ! grep -Fq "$marker" "$backup"; then
  temp_cron="$(mktemp "$ops/.primary-acquisition-cron.XXXXXX")"
  trap 'rm -f -- "$temp_cron"' EXIT
  cp "$backup" "$temp_cron"
  printf '%s\n' "* * * * * /usr/bin/flock -n '$ops/.primary-acquisition-minute.lock' /usr/bin/timeout 265s '$py' -B '$worker' --factory-private '$root' --batch 20 >> '$ops/license-safe-primary-fulltext-acquisition.log' 2>&1 # $marker" >> "$temp_cron"
  crontab "$temp_cron"
fi
crontab -l | grep -F "$marker"
printf '%s\n' 'PRIVATE_LICENSE_GATED_FULLTEXT_FETCH=ACTIVE' 'ALL_184_REWORK_QUEUE=IN_SCOPE' 'SOURCE_METADATA_AND_XML=IMMUTABLE' 'QC1000_APPROVALS=0' 'NEW_PUBLICATIONS=0' "CRONTAB_BACKUP=$backup"
