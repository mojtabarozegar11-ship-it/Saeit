#!/usr/bin/env bash
# Install ONLY a cron refresh of the existing private report snapshot.
# Refuses any unexpected existing installation. Never accesses finance SQLite.
set -euo pipefail
umask 077
test "${ZM_REPORT_CRON_RELEASE:-}" = 1
test "$#" = 1
sha="$1"
[[ "$sha" =~ ^[a-f0-9]{40}$ ]]
root="/home/zomorod2/.private/zomorod-business"
stage="$root/.report-cron-stage-$sha"
worker="$root/.chatgpt-report-sync"
backup="/home/zomorod2/.backups/zm-report-cron-release/$sha"
snapshot="$root/chatgpt_reports_snapshot.json"
test -d "$root" && test ! -L "$root"
test -d "$stage" && test ! -L "$stage"
test ! -e "$worker" && test ! -L "$worker"
test -f "$snapshot" && test ! -L "$snapshot"
test -f "$stage/refresh.py" && test -f "$stage/enterprise_portal/github_chatgpt_reports.py"
test -f "$stage/enterprise_portal/__init__.py"
test -f "$stage/run-hourly.sh"
test "$(stat -c %a "$snapshot")" = 600
test ! -e "$backup"
install -d -m 700 "$(dirname "$backup")" "$backup"
cp -p "$snapshot" "$backup/snapshot.before.json"
sha256sum "$snapshot" > "$backup/snapshot.before.sha256"
bash -n "$stage/run-hourly.sh"
python3 -m py_compile "$stage/refresh.py" "$stage/enterprise_portal/github_chatgpt_reports.py"
# A real external source read without writing anything (before installing).
(cd "$stage" && PYTHONPATH="$stage" python3 refresh.py --pages 5 > "$backup/preview.receipt")
grep -Fxq 'ZM_CHATGPT_SNAPSHOT=PREVIEW_ONLY' "$backup/preview.receipt"
if crontab -l > "$backup/crontab.before" 2>"$backup/crontab.err"; then
  :
elif grep -Eiq 'no crontab for|no crontab' "$backup/crontab.err"; then
  : > "$backup/crontab.before"
else
  echo 'CRONTAB_READ_NOT_AVAILABLE' >&2
  exit 1
fi
if grep -Fq '.chatgpt-report-sync' "$backup/crontab.before"; then
  echo 'REPORT_CRON_ALREADY_PRESENT' >&2
  exit 1
fi
schedule="50 * * * * /bin/bash $worker/run-hourly.sh >/dev/null 2>&1 # ZM_CHATGPT_REPORT_REFRESH"
{
  cat "$backup/crontab.before"
  printf '\n%s\n' "$schedule"
} > "$backup/crontab.proposed"
installed=0
cron_added=0
rollback(){
  rc=$?
  trap - EXIT
  if test "$rc" != 0; then
    if test "$cron_added" = 1; then crontab "$backup/crontab.before" || :; fi
    if test "$installed" = 1; then
      cp -p "$backup/snapshot.before.json" "$root/.chatgpt-snapshot.rollback-$sha" || :
      if test -f "$root/.chatgpt-snapshot.rollback-$sha"; then
        mv -f "$root/.chatgpt-snapshot.rollback-$sha" "$snapshot" || :
      fi
      if test -d "$worker" && test ! -e "$backup/failed-worker"; then
        mv "$worker" "$backup/failed-worker" || :
      fi
    fi
    echo 'REPORT_CRON_INSTALL=ROLLED_BACK' >&2
  fi
  exit "$rc"
}
trap rollback EXIT
# move only newly staged tools, leaving PHP application, role database and ledger intact.
mv "$stage" "$worker"
installed=1
chmod 700 "$worker"
chmod 600 "$worker/refresh.py" "$worker/enterprise_portal/github_chatgpt_reports.py"
chmod 700 "$worker/run-hourly.sh"
# Refresh once under the same lock/validation rules that the scheduled run will use.
bash "$worker/run-hourly.sh"
test -s "$worker/last-status"
grep -Fq 'outcome=success' "$worker/last-status"
crontab "$backup/crontab.proposed"
cron_added=1
crontab -l > "$backup/crontab.after"
grep -Fqx "$schedule" "$backup/crontab.after"
test "$(stat -c %a "$snapshot")" = 600
test "$(sha256sum "$backup/snapshot.before.json" | awk '{print $1}')" = "$(awk '{print $1}' "$backup/snapshot.before.sha256")"
trap - EXIT
echo 'REPORT_CRON_INSTALL=SUCCESS'
echo 'REPORT_CRON_SCHEDULE=minute_50_hourly'
echo 'REPORT_REFRESH_INITIAL=success'
echo 'FINANCIAL_DB_TOUCHED=no'
echo 'EXISTING_CRONTAB_PRESERVED=yes'
echo 'REPORT_BACKUP_AND_ROLLBACK=preserved'
