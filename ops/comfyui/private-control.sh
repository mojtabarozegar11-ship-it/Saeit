#!/usr/bin/env bash
# On-demand private ComfyUI control. Does not alter factory-runtime.
set -euo pipefail
umask 077
root="$HOME/comfyui-isolated"
app="$root/source-v0.40.0"
py="$root/env-cpu/bin/python"
pidfile="$root/private-ui.pid"
logfile="$root/private-ui.log"
cmd=status
if (( $# > 0 )); then cmd="$1"; fi
test "$(id -un)" = githubops
test -d "$root" && test ! -L "$root" && test -f "$app/main.py" && test -x "$py"
cd "$root"
exec 9>"$root/private-ui.lock"
flock -n 9 || { echo COMFY_CONTROL_BUSY; exit 1; }
is_ours() {
  test -s "$pidfile" || return 1
  local p args
  p="$(cat "$pidfile")"
  [[ "$p" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$p" 2>/dev/null || return 1
  args="$(ps -p "$p" -o args= 2>/dev/null || true)"
  [[ "$args" == *"$app/main.py"* && "$args" == *"--listen 127.0.0.1"* ]] || return 1
}
factory_check() {
  local f="$HOME/factory-runtime/operations/vps-only-loop.pid"
  test -f "$f" || { echo FACTORY_PIDFILE_MISSING; return 1; }
  local p
  p="$(cat "$f")"
  [[ "$p" =~ ^[0-9]+$ ]] && kill -0 "$p" 2>/dev/null || { echo FACTORY_LOOP_NOT_VERIFIED; return 1; }
  echo FACTORY_LOOP_ALIVE
}
case "$cmd" in
  status)
    if is_ours; then echo COMFY_PRIVATE_RUNNING; else echo COMFY_PRIVATE_STOPPED; fi
    factory_check
    ;;
  start)
    factory_check
    if is_ours; then echo COMFY_PRIVATE_ALREADY_RUNNING; exit 0; fi
    if test -f "$pidfile"; then echo COMFY_STALE_PIDFILE_REQUIRES_INSPECTION; exit 1; fi
    avail="$(awk '/^MemAvailable:/{print $2}' /proc/meminfo)"
    disk="$(df -Pk "$HOME" | awk 'NR==2{print $4}')"
    echo "AVAILABLE_RAM_KIB=$avail"
    echo "FREE_DISK_KIB=$disk"
    ((avail>=2800000 && disk>=10000000)) || { echo COMFY_START_BLOCKED_RESOURCE_GUARD; exit 1; }
    if ss -lntH '( sport = :18188 )' | grep -q .; then
      echo COMFY_START_BLOCKED_PORT_OCCUPIED
      exit 1
    fi
    cd "$app"
    export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
    nohup nice -n 18 "$py" -u "$app/main.py" --cpu --listen 127.0.0.1 --port 18188 --disable-auto-launch --disable-all-custom-nodes >> "$logfile" 2>&1 9>&- < /dev/null &
    p=$!
    printf '%s\n' "$p" > "$pidfile"
    ready=0
    for i in $(seq 1 80); do
      if curl -fsS --connect-timeout 1 --max-time 2 http://127.0.0.1:18188/system_stats >/dev/null 2>&1; then
        ready=1
        break
      fi
      if ! kill -0 "$p" 2>/dev/null; then break; fi
      sleep 1
    done
    if ((ready != 1)); then
      echo COMFY_PRIVATE_FAILED_TO_START
      if is_ours; then kill -TERM "$p" 2>/dev/null || true; fi
      rm -f -- "$pidfile"
      tail -n 12 "$logfile" || true
      exit 1
    fi
    echo COMFY_PRIVATE_READY_LOCALHOST_ONLY
    factory_check
    ;;
  stop)
    if ! is_ours; then
      echo COMFY_PRIVATE_NOT_RUNNING_OR_UNRECOGNIZED
      exit 1
    fi
    p="$(cat "$pidfile")"
    kill -TERM "$p"
    for i in $(seq 1 25); do
      if ! kill -0 "$p" 2>/dev/null; then break; fi
      sleep 1
    done
    if kill -0 "$p" 2>/dev/null; then
      echo COMFY_STOP_NOT_CONFIRMED
      exit 1
    fi
    rm -f -- "$pidfile"
    echo COMFY_PRIVATE_STOPPED
    factory_check
    ;;
  *)
    echo 'Usage: private-control.sh status|start|stop'
    exit 2
    ;;
esac
