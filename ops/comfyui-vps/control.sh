#!/usr/bin/env bash
# GitHub Actions -> VPS: on-demand, CPU-only controller for an EXISTING ComfyUI.
# Run as githubops. Never touches the factory runtime or public-facing ports.
set -Eeuo pipefail
umask 077
root="$HOME/comfyui-isolated"
source_dir="$root/source-v0.40.0"
python="$root/env-cpu/bin/python"
state="$root/.control"
pidfile="$state/comfyui.pid"
log="$state/comfyui.log"
port=18188
operation="${1:-status}"
session_minutes="${2:-15}"
[[ "$operation" =~ ^(status|start|stop|health)$ ]] || { echo INVALID_OPERATION; exit 2; }
[[ "$session_minutes" =~ ^(5|10|15|30|60)$ ]] || { echo INVALID_SESSION_DURATION; exit 2; }
[[ -d "$root" && -f "$source_dir/main.py" && -x "$python" ]] || { echo EXISTING_RUNTIME_NOT_FOUND; exit 3; }
install -d -m 700 "$state"
exec 9>"$state/lock"
flock -w 15 9 || { echo CONTROLLER_BUSY; exit 4; }
get_pid() {
  pid=''
  [[ -r "$pidfile" ]] || return 1
  read -r pid < "$pidfile" || return 1
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  return 0
}
is_ours() {
  get_pid || return 1
  [[ -r "/proc/$pid/cmdline" ]] || return 1
  grep -azFq -- "$python" "/proc/$pid/cmdline" || return 1
  grep -azFq -- "$port" "/proc/$pid/cmdline" || return 1
  return 0
}
health() { curl -fsS --max-time 3 "http://127.0.0.1:$port/system_stats" -o /dev/null 2>/dev/null; }
case "$operation" in
  status)
    if is_ours; then
      echo COMFYUI_PROCESS_RUNNING
      if health; then echo COMFYUI_LOCAL_API_HEALTHY; else echo COMFYUI_PROCESS_STARTING_OR_UNHEALTHY; fi
    else
      echo COMFYUI_CONTROLLER_IDLE
    fi
    ;;
  health)
    if is_ours && health; then echo COMFYUI_LOCAL_API_HEALTHY; else echo COMFYUI_LOCAL_API_UNAVAILABLE; exit 1; fi
    ;;
  stop)
    if is_ours; then
      kill -TERM "$pid" 2>/dev/null || true
      echo COMFYUI_CONTROLLER_STOP_SIGNAL_SENT
    elif [[ -f "$pidfile" ]]; then
      echo COMFYUI_STALE_PID_NOT_KILLED
    else
      echo COMFYUI_ALREADY_STOPPED
    fi
    rm -f "$pidfile"
    ;;
  start)
    if is_ours; then echo COMFYUI_ALREADY_RUNNING; exit 0; fi
    if ss -ltn "( sport = :$port )" | grep -q LISTEN; then
      echo COMFYUI_PORT_IN_USE_REFUSE
      exit 5
    fi
    ttl=$((session_minutes*60))
    echo COMFYUI_START_LOCAL_ONLY_SESSION_MINUTES="$session_minutes"
    (
      cd "$source_dir"
      exec nice -n 12 nohup timeout --signal=TERM --kill-after=10s "$ttl" \
        "$python" main.py --cpu --listen 127.0.0.1 --port "$port" --disable-auto-launch \
        </dev/null >>"$log" 2>&1
    ) 9>&- &
    child=$!
    printf '%s\n' "$child" > "$pidfile"
    for attempt in $(seq 1 50); do
      if health; then echo COMFYUI_LOCAL_API_HEALTHY; echo COMFYUI_STARTED_ON_DEMAND; exit 0; fi
      if ! kill -0 "$child" 2>/dev/null; then break; fi
      sleep 1
    done
    echo COMFYUI_FAILED_TO_START
    if is_ours; then kill -TERM "$child" 2>/dev/null || true; fi
    rm -f "$pidfile"
    exit 6
    ;;
esac
