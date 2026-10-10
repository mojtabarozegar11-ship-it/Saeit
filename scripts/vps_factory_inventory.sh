#!/usr/bin/env bash
# Read-only, redacted VPS inventory. Run locally on the VPS using an authorized shell.
set -uo pipefail
export LC_ALL=C
printf 'INVENTORY_VERSION=1\n'
printf 'HOSTNAME=%s\n' "$(hostname 2>/dev/null || echo unknown)"
printf 'OS='; ( . /etc/os-release 2>/dev/null && printf '%s\n' "${PRETTY_NAME:-unknown}" ) || echo unknown
printf 'CPU_CORES='; nproc 2>/dev/null || echo unknown
printf 'MEMORY_KIB_TOTAL='; awk '/^MemTotal:/ {print $2}' /proc/meminfo
printf 'MEMORY_KIB_AVAILABLE='; awk '/^MemAvailable:/ {print $2}' /proc/meminfo
printf 'SWAP_KIB_TOTAL='; awk '/^SwapTotal:/ {print $2}' /proc/meminfo
printf 'DISK_ROOT_KIB_TOTAL_USED_AVAILABLE='; df -Pk / | awk 'NR==2 {print $2, $3, $4}'
printf 'FILESYSTEMS='; df -h -x tmpfs -x devtmpfs | tail -n +2 | awk '{print $1,$2,$3,$4,$5,$6}'
printf 'POSTGRES_SERVICE='; (systemctl is-active postgresql 2>/dev/null || echo unknown)
printf 'POSTGRES_BIN='; if command -v psql >/dev/null 2>&1; then echo present; else echo absent; fi
printf 'DOCKER_BIN='; if command -v docker >/dev/null 2>&1; then echo present; else echo absent; fi
printf 'PROCESS_CLASSES='; ps -eo comm= 2>/dev/null | grep -Ei 'postgres|gunicorn|celery|redis|python|uvicorn|nginx|docker' | sort | uniq -c || true
for base in /opt /srv /home /var/lib/postgresql /var/lib/docker; do
 if [ -d "$base" ]; then
   printf 'DIRECTORY_USAGE_KIB %s ' "$base"
   du -sk "$base" 2>/dev/null | awk 'NR==1 {print $1}' || echo unavailable
 fi
done
printf 'NOTE=No credentials, environment values, or database rows are read.\n'
