#!/usr/bin/env bash
# Private cPanel cron entrypoint: only refresh the public-numbered reports cache.
# This script has no SQL access and does not touch any web application source.
set -euo pipefail
umask 077
root="/home/zomorod2/.private/zomorod-business"
worker="$root/.chatgpt-report-sync"
target="$root/chatgpt_reports_snapshot.json"
test -d "$worker" && test ! -L "$worker"
test -f "$worker/refresh.py" && test ! -L "$worker/refresh.py"
test -f "$worker/enterprise_portal/github_chatgpt_reports.py"
test -f "$target" && test ! -L "$target"
test "$(stat -c '%a' "$worker")" = "700"
test "$(stat -c '%a' "$target")" = "600"
exec 9>"$worker/.lock"
if ! flock -n 9; then
  exit 0
fi
cd "$worker"
log="$worker/.last-result.tmp.$$"
status="$worker/last-status"
trap 'rm -f "$log"' EXIT
now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
if ZM_BUSINESS_REPORT_SNAPSHOT_INSTALL=1 PYTHONPATH="$worker" /usr/bin/python3 "$worker/refresh.py" --pages 5 --install --output "$target" > "$log" 2>&1; then
  count="$(grep '^VALID_NUMBERED_REPORTS=' "$log" | tail -1 || :)"
  result="$(grep '^ZM_CHATGPT_SNAPSHOT=' "$log" | tail -1 || :)"
  if [[ "$count" != VALID_NUMBERED_REPORTS=[0-9]* || "$result" == "" ]]; then
    printf 'utc=%s outcome=invalid_receipt\n' "$now" > "$worker/.last-status.tmp.$$"
    mv -f "$worker/.last-status.tmp.$$" "$status"
    exit 1
  fi
  printf 'utc=%s outcome=success %s %s\n' "$now" "$count" "$result" > "$worker/.last-status.tmp.$$"
  mv -f "$worker/.last-status.tmp.$$" "$status"
else
  # Do not publish raw remote comments, token, traceback or financial data.
  printf 'utc=%s outcome=failed\n' "$now" > "$worker/.last-status.tmp.$$"
  mv -f "$worker/.last-status.tmp.$$" "$status"
  exit 1
fi
