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
  executable=unknown
  resolved_version=unverified
  binary_match=unverified
  target_file_kind=unverified
  pyvenv_version=unverified
  while read -r directive value _ || [[ -n "${directive:-}" ]]; do
    if [[ "${directive:-}" != PassengerPython ]]; then continue; fi
    count=$((count + 1))
    # Directives may quote their path. Strip only surrounding quote marks;
    # never evaluate or execute an untrusted configuration value.
    value=${value#\"}
    value=${value%\"}
    value=${value#\'}
    value=${value%\'}
    case "${value:-}" in
      /home/zomorod2/virtualenv/Saeit/3.10/bin/python) hint=prod_3_10 ;;
      /home/zomorod2/virtualenv/Saeit-staging/3.11/bin/python) hint=staging_3_11 ;;
      /home/zomorod2/Saeit/.venv/bin/python) hint=project_venv_unverified ;;
      /home/zomorod2/virtualenv/Saeit/3.11/bin/python) hint=legacy_prod_3_11_previously_missing ;;
      /home/zomorod2/virtualenv/Saeit/3.10/bin/python3*) hint=prod_3_10_alt_binary ;;
      /home/zomorod2/virtualenv/Saeit/*) hint=other_saeit_virtualenv ;;
      /usr/bin/python*) hint=system_python ;;
      *) hint=other_unverified ;;
    esac
    if [[ "${value:-}" == /* && -x "$value" ]]; then
      executable=yes
      # Resolving a symlink and comparing device/inode never invokes Python.
      # This identifies an executable binary, NOT sys.prefix or a live worker.
      resolved=$(readlink -f -- "$value" 2>/dev/null || true)
      # Four-byte magic inspection is read-only and never starts the target.
      magic=''
      if [[ -f "$value" ]]; then
        magic=$(head -c 4 -- "$value" 2>/dev/null | od -An -tx1 | tr -d '[:space:]' || true)
      fi
      case "$magic" in
        7f454c46*) target_file_kind=elf_binary ;;
        2321*) target_file_kind=shebang_script ;;
        *) target_file_kind=other_or_unreadable ;;
      esac
      case "${resolved##*/}" in
        python3.9) resolved_version=3.9 ;;
        python3.10) resolved_version=3.10 ;;
        python3.11) resolved_version=3.11 ;;
        python3.12) resolved_version=3.12 ;;
        python3.13) resolved_version=3.13 ;;
        *) resolved_version=unverified ;;
      esac
      # An adjacent pyvenv.cfg is only a version hint; its `home` and other
      # contents are never printed. Limit inspection to the target account.
      if [[ "$value" == /home/zomorod2/*/bin/python* ]]; then
        candidate_venv=$(dirname -- "$(dirname -- "$value")")
        candidate_venv=$(cd -P -- "$candidate_venv" 2>/dev/null && pwd -P || true)
        if [[ "$candidate_venv" == /home/zomorod2/* && -f "$candidate_venv/pyvenv.cfg" && ! -L "$candidate_venv/pyvenv.cfg" ]]; then
          cfg_version=$(awk -F= 'tolower($1) ~ /^[[:space:]]*version[[:space:]]*$/ {gsub(/[[:space:]]/, "", $2); print $2; exit}' "$candidate_venv/pyvenv.cfg" 2>/dev/null || true)
          if [[ "$cfg_version" =~ ^3\.(9|10|11|12|13)(\.[0-9]+)?$ ]]; then pyvenv_version="$cfg_version"; fi
        fi
      fi
      configured_inode=$(stat -Lc '%d:%i' -- "$value" 2>/dev/null || true)
      matches=''
      for candidate in \
        /home/zomorod2/virtualenv/Saeit/3.10/bin/python \
        /home/zomorod2/virtualenv/Saeit-staging/3.11/bin/python \
        /home/zomorod2/Saeit/.venv/bin/python; do
        [[ -x "$candidate" ]] || continue
        candidate_inode=$(stat -Lc '%d:%i' -- "$candidate" 2>/dev/null || true)
        [[ -n "$configured_inode" && "$candidate_inode" == "$configured_inode" ]] || continue
        case "$candidate" in
          */virtualenv/Saeit/3.10/bin/python) label_match=prod_3_10_binary ;;
          */virtualenv/Saeit-staging/3.11/bin/python) label_match=staging_3_11_binary ;;
          *) label_match=project_venv_binary ;;
        esac
        matches=${matches:+$matches,}$label_match
      done
      if [[ "$matches" == *','* ]]; then
        binary_match=multiple_binary_matches
      elif [[ -n "$matches" ]]; then
        binary_match="$matches"
      else
        binary_match=none_of_three_candidates
      fi
    else
      executable=no
    fi
  done < "$site"
  if (( count > 1 )); then
    hint=multiple_ambiguous
    executable=ambiguous
    resolved_version=unverified
    binary_match=unverified
    target_file_kind=unverified
    pyvenv_version=unverified
  fi
  printf 'PASSENGER_PYTHON_HINT_%s=%s\n' "$label" "$hint"
  printf 'PASSENGER_PYTHON_HINT_EXECUTABLE_%s=%s\n' "$label" "$executable"
  printf 'PASSENGER_PYTHON_RESOLVED_VERSION_HINT_%s=%s\n' "$label" "$resolved_version"
  printf 'PASSENGER_PYTHON_BINARY_MATCH_%s=%s\n' "$label" "$binary_match"
  printf 'PASSENGER_PYTHON_TARGET_KIND_%s=%s\n' "$label" "$target_file_kind"
  printf 'PASSENGER_PYTHON_PYVENV_VERSION_HINT_%s=%s\n' "$label" "$pyvenv_version"
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
