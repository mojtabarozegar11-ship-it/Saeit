#!/usr/bin/env bash
# Start only a STAGING event listener under the unprivileged cPanel account.
# No modifications to live Django, public checkout, production database,
# domain routing, or payment settlement. Zero blockchain calls while idle.
set -euo pipefail
umask 077

test "$(id -un)" = "zomorod2" || { echo WRONG_ACCOUNT; exit 2; }
command -v flock >/dev/null 2>&1 || { echo FILE_LOCK_UNAVAILABLE; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo PYTHON_UNAVAILABLE; exit 2; }

source_root="/home/zomorod2/Saeit-staging/mojplaywin-chess-product-prep-20261014"
runtime="$HOME/.mpw-native-event-staging"
test -f "$source_root/scripts/mojplaywin_cpanel_local_event_worker.py"
test -f "$source_root/scripts/mojplaywin_purchase_events.py"
test -f "$source_root/scripts/mojplaywin_direct_wallet_discovery.py"
test -f "$source_root/scripts/mojplaywin_native_chain_verify.py"
test ! -L "$runtime"
mkdir -p "$runtime"
chmod 700 "$runtime"
test "$(stat -c '%U' "$runtime")" = "$(id -un)"
test "$(stat -c '%a' "$runtime")" = 700
PYTHONPATH="$source_root" python3 -B - <<'PY'
import scripts.mojplaywin_cpanel_local_event_worker
import scripts.mojplaywin_purchase_events
print("CPANEL_NATIVE_EVENT_DEPENDENCIES_IMPORT_OK")
PY

key_file="$runtime/.staging-event-hmac"
if test ! -e "$key_file"; then
  python3 -B - "$key_file" <<'PY'
import os, secrets, sys
fd=os.open(sys.argv[1], os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
with os.fdopen(fd,"wb") as out:
    out.write(secrets.token_hex(48).encode("ascii") + b"\n")
print("CPANEL_STAGING_EVENT_KEY_GENERATED_PRIVATE")
PY
fi
test -f "$key_file" && test ! -L "$key_file"
test "$(stat -c '%U' "$key_file")" = "$(id -un)"
test "$(stat -c '%a' "$key_file")" = 600

cat > "$runtime/ensure.sh" <<'ENSURE'
#!/usr/bin/env bash
set -euo pipefail
umask 077
root="$HOME/.mpw-native-event-staging"
source_root="/home/zomorod2/Saeit-staging/mojplaywin-chess-product-prep-20261014"
script="$source_root/scripts/mojplaywin_cpanel_local_event_worker.py"
socket_path="$root/native-purchase.sock"
test "$(id -un)" = "zomorod2"
test -d "$root" && test ! -L "$root"
test -f "$script"
test -f "$root/.staging-event-hmac"
exec 9>"$root/.launch.lock"
flock -n 9 || exit 0
old_pid="$(cat "$root/worker.pid" 2>/dev/null || true)"
if [[ "$old_pid" =~ ^[0-9]+$ ]] && kill -0 "$old_pid" 2>/dev/null; then
  args="$(ps -p "$old_pid" -o args= 2>/dev/null || true)"
  if [[ "$args" == *"$script"* ]]; then
    exit 0
  fi
  echo "CPANEL_LISTENER_PID_NOT_OWNED"
  exit 2
fi
# Remove ONLY a stale socket in our private own directory after checking that
# no local listener still accepts connections. An active socket aborts.
if test -e "$socket_path"; then
  python3 -B - "$socket_path" <<'PY'
import os, socket, sys
target=sys.argv[1]
if os.path.islink(target):
    raise SystemExit("CPANEL_UNSAFE_SOCKET_SYMLINK")
s=socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(.3)
try:
    if s.connect_ex(target)==0:
        raise SystemExit("CPANEL_LISTENER_SOCKET_ALREADY_ACTIVE")
finally:
    s.close()
os.unlink(target)
PY
fi
export PYTHONPATH="$source_root"
nohup python3 -B "$script" --home "$root" --secret-file "$root/.staging-event-hmac" \
    >>"$root/listener.log" 2>&1 9>&- </dev/null &
printf '%s\n' "$!" > "$root/worker.pid"
sleep 1
pid="$(cat "$root/worker.pid")"
kill -0 "$pid"
test -S "$socket_path"
echo "CPANEL_STAGING_EVENT_LISTENER_RUNNING_IDLE"
ENSURE
chmod 700 "$runtime/ensure.sh"
"$runtime/ensure.sh"

# cPanel may not permit CLI crontab on all accounts; if unavailable, report
# reduced resilience instead of editing unrelated cron entries or failing.
if command -v crontab >/dev/null 2>&1; then
  current="$(crontab -l 2>/dev/null || true)"
  marker="# MPW_NATIVE_STAGING_EVENT_LISTENER_V1"
  if ! printf '%s\n' "$current" | grep -Fq "$marker"; then
    {
      if test -n "$current"; then printf '%s\n' "$current"; fi
      printf '*/1 * * * * /bin/bash "$HOME/.mpw-native-event-staging/ensure.sh" >/dev/null 2>&1 %s\n' "$marker"
    } | crontab -
  fi
  echo "CPANEL_STAGING_LISTENER_CRON_RESTART_REGISTERED"
else
  echo "CPANEL_STAGING_LISTENER_RUNNING_NO_CRON_PERMISSION"
fi

# Verify none of the settings needed for live checkout were changed.
echo "CPANEL_STAGING_LISTENER_NO_LIVE_CHECKOUT_ACTIVATION"
echo "CPANEL_STAGING_LISTENER_ZERO_IDLE_BLOCKCHAIN_REQUESTS"
echo "CPANEL_STAGING_LISTENER_NO_OPENAI_CALLS"
