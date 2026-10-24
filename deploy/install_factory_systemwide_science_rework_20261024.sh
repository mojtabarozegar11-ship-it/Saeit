#!/usr/bin/env bash
# Install permanent ALL-product Stage-2 original-source repair handoff on VPS.
# No old archive, product, order, webroot, payment or QC evidence is replaced.
set -euo pipefail
umask 077
test "$#" -ge 1
staged="$1"
root='/home/githubops/factory-runtime/private/autonomous-product-cycle'
ops='/home/githubops/factory-runtime/operations/production-instructions'
python_bin='/home/githubops/factory-runtime/.venv/bin/python'
worker="$ops/systemwide-scientific-source-rework.py"
marker='SAEIT_SCIENCE_REWORK_ALL_20261024'
test "$(id -un)" = githubops
test -f "$staged" && test ! -L "$staged"
test -x "$python_bin"
test -d "$root/production-instructions/stage-05/source-grounded-v003-manifests"
test -d "$root/production-instructions/stage-06/scientific-review-inbox-v003"
test -d "$ops" && test ! -L "$ops"
expected="$(sha256sum "$staged" | awk '{print $1}')"
if test -e "$worker"; then
  test ! -L "$worker"
  test "$(sha256sum "$worker" | awk '{print $1}')" = "$expected"
else
  install -m 600 "$staged" "$worker"
  test "$(sha256sum "$worker" | awk '{print $1}')" = "$expected"
fi
timeout 240s "$python_bin" -B "$worker" --factory-private "$root" --batch 2000 --dry-run
timeout 300s "$python_bin" -B "$worker" --factory-private "$root" --batch 2000

backup_dir='/home/githubops/factory-runtime/operations/backups'
install -d -m 700 "$backup_dir"
exec 9>"$ops/.science-rework-cron-install.lock"
flock -x 9
backup="$backup_dir/science-rework-crontab-$GITHUB_RUN_ID-$(date -u +%Y%m%dT%H%M%SZ).txt"
(crontab -l 2>/dev/null || true) > "$backup"
chmod 600 "$backup"
if ! grep -Fq "$marker" "$backup"; then
  temp_cron="$(mktemp "$ops/.science-cron.XXXXXX")"
  trap 'rm -f -- "$temp_cron"' EXIT
  cp "$backup" "$temp_cron"
  printf '%s\n' "* * * * * /usr/bin/flock -n '$ops/.science-rework-minute.lock' /usr/bin/timeout 180s '$python_bin' -B '$worker' --factory-private '$root' --batch 2000 >> '$ops/systemwide-scientific-source-rework.log' 2>&1 # $marker" >> "$temp_cron"
  crontab "$temp_cron"
fi
crontab -l | grep -F "$marker"
printf '%s\n' "SYSTEMWIDE_SCIENCE_REWORK=ACTIVE_ALL_ORDERS" "ORIGINAL_ARCHIVES=UNCHANGED" "QC1000_APPROVALS=NOT_ASSERTED" "CRONTAB_BACKUP=$backup"
