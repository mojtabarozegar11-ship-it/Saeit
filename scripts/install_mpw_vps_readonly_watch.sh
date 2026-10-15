#!/usr/bin/env bash
# User-only installation: no live website edits, secrets or payment writes.
set -euo pipefail
umask 077
test "$(id -un)" = "githubops"
version="$1"
[[ "$version" =~ ^[0-9a-f]{40}$ ]] || exit 2
root="$HOME/mojplaywin-wallet-watch"
release="$root/releases/$version"
test -f "$release/scripts/mojplaywin_vps_readonly_watch.py"
test -f "$release/scripts/mojplaywin_direct_wallet_discovery.py"
test -f "$release/scripts/mojplaywin_native_chain_verify.py"
python3 -m py_compile "$release/scripts/mojplaywin_vps_readonly_watch.py" "$release/scripts/mojplaywin_direct_wallet_discovery.py" "$release/scripts/mojplaywin_native_chain_verify.py"
ln -sfn "releases/$version" "$root/next-link"
mv -Tf "$root/next-link" "$root/current"
cat > "$root/ensure.sh" <<'ENSURE'
#!/usr/bin/env bash
set -euo pipefail
umask 077
base="$HOME/mojplaywin-wallet-watch"
exec 9>"$base/supervisor.lock"
flock -n 9 || exit 0
pid="$(cat "$base/watch.pid" 2>/dev/null || true)"
if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
    cmd="$(ps -p "$pid" -o args= 2>/dev/null || true)"
    if [[ "$cmd" == *"$base/current/scripts/mojplaywin_vps_readonly_watch.py"* ]]; then
        exit 0
    fi
fi
nohup env PYTHONPATH="$base/current" python3 "$base/current/scripts/mojplaywin_vps_readonly_watch.py" --home "$base" >> "$base/launcher.log" 2>&1 9>&- </dev/null &
printf '%s\n' "$!" > "$base/watch.pid"
sleep 2
kill -0 "$(cat "$base/watch.pid")"
ENSURE
chmod 700 "$root/ensure.sh"
# Gracefully restart ONLY the confirmed owned watcher, so updated Python code
# takes effect; never signal unrelated VPS services or the factory process.
exec 8>"$root/supervisor.lock"
flock -w 8 8
old_pid="$(cat "$root/watch.pid" 2>/dev/null || true)"
if [[ "$old_pid" =~ ^[0-9]+$ ]] && kill -0 "$old_pid" 2>/dev/null; then
  old_cmd="$(ps -p "$old_pid" -o args= 2>/dev/null || true)"
  if [[ "$old_cmd" == *"$root/current/scripts/mojplaywin_vps_readonly_watch.py"* ]]; then
    kill -TERM "$old_pid"
    # Python may be waiting on an in-flight indexer request (up to 15s per
    # network). Wait for graceful shutdown, never kill unrelated processes.
    for attempt in $(seq 1 120); do
      kill -0 "$old_pid" 2>/dev/null || break
      old_stat="$(ps -p "$old_pid" -o stat= 2>/dev/null || true)"
      if [[ "$old_stat" == Z* ]]; then break; fi
      sleep 0.5
    done
    old_stat="$(ps -p "$old_pid" -o stat= 2>/dev/null || true)"
    if kill -0 "$old_pid" 2>/dev/null && [[ "$old_stat" != Z* ]]; then
      echo "MPW_OLD_WATCHER_DID_NOT_STOP"
      exit 1
    fi
  else
    echo "MPW_PID_OWNERSHIP_MISMATCH"
    exit 1
  fi
fi
flock -u 8
bash "$root/ensure.sh"
pid="$(cat "$root/watch.pid")"
ps -p "$pid" -o args= | grep -F 'mojplaywin_vps_readonly_watch.py' >/dev/null
echo MPW_WATCH_PROCESS_ALIVE
if command -v crontab >/dev/null 2>&1; then
  old="$(crontab -l 2>/dev/null || true)"
  marker='# MPW_WALLET_READONLY_SUPERVISOR_V1'
  if ! printf '%s\n' "$old" | grep -Fq "$marker"; then
    {
      if test -n "$old"; then printf '%s\n' "$old"; fi
      printf '*/1 * * * * /bin/bash "$HOME/mojplaywin-wallet-watch/ensure.sh" >/dev/null 2>&1 %s\n' "$marker"
    } | crontab -
  fi
  echo MPW_CRON_SELF_HEAL_INSTALLED
else
  echo MPW_CRON_UNAVAILABLE_BACKGROUND_WATCH_RUNNING
fi
echo MPW_ACTIVE_MARKER_POLL_EVERY_15S
echo MPW_IDLE_INDEXER_REQUESTS_ZERO
echo MPW_WALLET_WATCH_READ_ONLY_NO_SETTLEMENT
echo MPW_LIVE_SITE_UNCHANGED
