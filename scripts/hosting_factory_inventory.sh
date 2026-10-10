#!/usr/bin/env bash
# Read-only staging-host footprint inventory. Never prints environment values.
set -uo pipefail
export LC_ALL=C
root=/home/zomorod2/Saeit-staging
printf 'HOST_STAGING_PRESENT='
if [ -d "$root" ]; then echo yes; else echo no; exit 2; fi
printf 'HOST_STAGING_TOTAL_KIB='
du -sk "$root" 2>/dev/null | awk 'NR==1 {print $1}'
for sub in core master_agent media staticfiles static logs backups; do
 if [ -d "$root/$sub" ]; then
  printf 'HOST_COMPONENT_KIB %s ' "$sub"
  du -sk "$root/$sub" 2>/dev/null | awk 'NR==1 {print $1}'
 fi
done
printf 'HOST_FILESYSTEM_KIB_TOTAL_USED_AVAILABLE='
df -Pk "$root" | awk 'NR==2 {print $2, $3, $4}'
printf 'HOST_POSTGRES_CLIENT='
if command -v psql >/dev/null 2>&1; then echo present; else echo absent; fi
printf 'HOST_STAGING_CONFIG_PRESENT='
if [ -f "$root/.env" ]; then echo yes; else echo no; fi
printf 'NOTE=No secrets, database rows, or file contents are printed.\n'
