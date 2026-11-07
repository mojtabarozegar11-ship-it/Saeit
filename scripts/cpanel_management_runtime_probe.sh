#!/usr/bin/env bash
# One-shot, strictly read-only cPanel Passenger/source fingerprint for PR #2127.
# Emit classifications and SHA-256 of application source ONLY, never config,
# environment contents, process arguments, database data, or private files.
set -euo pipefail

app_root=/home/zomorod2/Saeit
echo 'RECEIPT_CLASS=MANAGEMENT_RUNTIME_READONLY_V1'
echo 'PRODUCTION_MUTATION=false'

if [[ ! -d "$app_root" || ! -f "$app_root/passenger_wsgi.py" ]]; then
  echo 'APP_ROOT_ATTESTED=false'
  echo 'ACTIVE_INTERPRETER_ATTESTED=false'
  echo 'SOURCE_RUNTIME_MATCH_ATTESTED=false'
  echo 'RELEASE_PERMITTED=false'
  exit 0
fi
echo 'APP_ROOT_ATTESTED=true'

# A Git HEAD is informative only; a production tree may be copied without Git.
git_head=$(git -C "$app_root" rev-parse --verify HEAD 2>/dev/null || true)
if [[ "$git_head" =~ ^[0-9a-f]{40}$ ]]; then
  printf 'DEPLOYED_GIT_HEAD=%s\n' "$git_head"
else
  echo 'DEPLOYED_GIT_HEAD=unavailable'
fi

# File hashes can be compared with the reviewed repository without reading
# secrets or claiming that all modules loaded in a running process match.
for relative in passenger_wsgi.py config/wsgi.py accounting/services.py command_center/integrated_ledger_api.py; do
  key=${relative//\//_}
  key=${key//./_}
  if [[ -f "$app_root/$relative" && ! -L "$app_root/$relative" ]]; then
    digest=$(sha256sum -- "$app_root/$relative" | cut -d ' ' -f 1)
    printf 'SOURCE_SHA256_%s=%s\n' "$key" "$digest"
  else
    printf 'SOURCE_SHA256_%s=missing_or_symlink\n' "$key"
  fi
done

# These are *hints* only: the actual document root has not been proven here.
# Read PassengerPython lines into shell variables, but never echo their text.
for site in "$app_root/.htaccess" /home/zomorod2/public_html/.htaccess; do
  case "$site" in
    "$app_root/.htaccess") label=APP_ROOT ;;
    *) label=PUBLIC_HTML ;;
  esac
  if [[ ! -f "$site" || -L "$site" || ! -r "$site" ]]; then
    printf 'PASSENGER_PYTHON_HINT_%s=unavailable\n' "$label"
    continue
  fi
  count=0
  hint=none
  while read -r directive value _ || [[ -n "${directive:-}" ]]; do
    if [[ "${directive:-}" != PassengerPython ]]; then continue; fi
    count=$((count + 1))
    case "${value:-}" in
      /home/zomorod2/virtualenv/Saeit/3.10/bin/python) hint=prod_3_10 ;;
      /home/zomorod2/virtualenv/Saeit-staging/3.11/bin/python) hint=staging_3_11 ;;
      /home/zomorod2/Saeit/.venv/bin/python) hint=project_venv_unverified ;;
      *) hint=other_unverified ;;
    esac
  done < "$site"
  if (( count > 1 )); then hint=multiple_ambiguous; fi
  printf 'PASSENGER_PYTHON_HINT_%s=%s\n' "$label" "$hint"
done

# Bind a process to this app only if its process title explicitly names this
# exact root as a Passenger app. Generic Python/cron processes are excluded.
count=0
versions=''
current_uid=$(id -u)
for proc in /proc/[0-9]*; do
  [[ -r "$proc/status" && -r "$proc/cmdline" ]] || continue
  proc_uid=$(awk '/^Uid:/{print $2;exit}' "$proc/status" 2>/dev/null || true)
  [[ "$proc_uid" == "$current_uid" ]] || continue
  command_line=$(tr '\0' ' ' < "$proc/cmdline" 2>/dev/null || true)
  [[ "$command_line" == *'Passenger AppPreloader:'* && "$command_line" == *"$app_root"* ]] || continue
  ((count+=1))
  exe=$(readlink -f "$proc/exe" 2>/dev/null || true)
  case "${exe##*/}" in
    python3.10) version=3.10 ;;
    python3.11) version=3.11 ;;
    python3.12) version=3.12 ;;
    *) version=unverified ;;
  esac
  case ",$versions," in
    *,"$version",*) ;;
    *) versions=${versions:+$versions,}$version ;;
  esac
done
printf 'MATCHED_PASSENGER_PROCESS_COUNT=%s\n' "$count"
if [[ "$count" -gt 0 && "$versions" != *','* && "$versions" != unverified ]]; then
  printf 'PASSENGER_PROCESS_PYTHON_VERSION=%s\n' "$versions"
  echo 'PASSENGER_PROCESS_VERSION_ATTESTED=true'
else
  echo 'PASSENGER_PROCESS_PYTHON_VERSION=unverified'
  echo 'PASSENGER_PROCESS_VERSION_ATTESTED=false'
fi

# No method here proves the virtualenv prefix, full live source snapshot,
# migration state, recovery viability, or production isolation.
echo 'ACTIVE_INTERPRETER_ATTESTED=false'
echo 'SOURCE_RUNTIME_MATCH_ATTESTED=false'
echo 'MIGRATIONS_ATTESTED=false'
echo 'RECOVERABLE_BACKUP_ATTESTED=false'
echo 'RELEASE_PERMITTED=false'
