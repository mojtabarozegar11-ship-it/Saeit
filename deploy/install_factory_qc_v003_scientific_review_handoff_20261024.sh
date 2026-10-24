#!/usr/bin/env bash
# Install only the private source-grounded QC-to-scientific-review handoff.
set -euo pipefail
umask 077
test "$(id -un)" = githubops
test "$(id -u)" -ne 0
test "$#" -eq 1
incoming="$1"
test -f "$incoming" && test ! -L "$incoming"
base="/home/githubops/factory-runtime"
ops="$base/operations/production-instructions"
root="$base/private/autonomous-product-cycle"
py="$base/.venv/bin/python"
dest="$ops/qc-v003-scientific-review-handoff.py"
stage34="$ops/stage34-autonomous-handoff.py"
v003qc="$ops/agri200-source-grounded-v003-qc.py"
marker="SAEIT_QC_V003_SCIENTIFIC_REVIEW_HANDOFF_20261024"
test -x "$py" && test -d "$ops" && test ! -L "$ops"
test -f "$stage34" && test ! -L "$stage34"
test -f "$v003qc" && test ! -L "$v003qc"
test -d "$root/production-instructions/stage-05/source-grounded-v003-manifests"
command -v flock >/dev/null
exec 8>"$ops/.qc-v003-review-install.lock"
flock -w 60 8
backup="$base/operations/backups/qc-v003-review-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup"
crontab -l > "$backup/crontab.before"
chmod 600 "$backup/crontab.before"
previous=0
if test -e "$dest"; then
  test -f "$dest" && test ! -L "$dest"
  cp -p "$dest" "$backup/worker.before.py"
  previous=1
fi
rollback() {
  rc=$?
  trap - ERR
  crontab "$backup/crontab.before" || true
  if test "$previous" -eq 1; then
    cp -p "$backup/worker.before.py" "$dest" || true
  else
    test ! -f "$dest" || rm -f -- "$dest"
  fi
  echo "QC_V003_REVIEW_HANDOFF_ROLLBACK=1"
  exit "$rc"
}
trap rollback ERR
"$py" -B "$incoming" --selftest
stage="$(mktemp "$ops/.qc-v003-review.XXXXXX")"
install -m 600 "$incoming" "$stage"
mv -f "$stage" "$dest"
test "$(sha256sum "$incoming" | awk '{print $1}')" = "$(sha256sum "$dest" | awk '{print $1}')"
timeout 180s "$py" -B "$dest" --factory-private "$root" \
  --stage34-worker "$stage34" --v003-qc-worker "$v003qc" --batch 250
cron='* * * * * /usr/bin/flock -n /home/githubops/factory-runtime/operations/production-instructions/.qc-v003-scientific-minute.lock /usr/bin/timeout 90s /home/githubops/factory-runtime/.venv/bin/python -B /home/githubops/factory-runtime/operations/production-instructions/qc-v003-scientific-review-handoff.py --factory-private /home/githubops/factory-runtime/private/autonomous-product-cycle --stage34-worker /home/githubops/factory-runtime/operations/production-instructions/stage34-autonomous-handoff.py --v003-qc-worker /home/githubops/factory-runtime/operations/production-instructions/agri200-source-grounded-v003-qc.py --batch 25 >> /home/githubops/factory-runtime/operations/production-instructions/qc-v003-scientific-review-handoff.log 2>&1 # SAEIT_QC_V003_SCIENTIFIC_REVIEW_HANDOFF_20261024'
if grep -Fq "$marker" "$backup/crontab.before"; then
  test "$(grep -Fc "$marker" "$backup/crontab.before")" -eq 1
  if ! grep -Fxq "$cron" "$backup/crontab.before"; then
    awk -v marker="$marker" -v cron="$cron" 'index($0,marker) {print cron;next} {print}' "$backup/crontab.before" | crontab -
  fi
else
  { sed -n '1,$p' "$backup/crontab.before"; printf '%s\n' "$cron"; } | crontab -
fi
test "$(crontab -l | grep -Fc "$marker")" -eq 1
test -f "$root/production-instructions/stage-06/scientific-review-handoff-health.json"
echo "QC_V003_REVIEW_HANDOFF_CRON=INSTALLED"
echo "QC_V003_REVIEW_HANDOFF_BACKUP=$backup"
trap - ERR
