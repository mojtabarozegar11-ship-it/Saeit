#!/usr/bin/env bash
# Read-only host preflight for the Zomorod management and accounting private files.
# Does NOT touch the database, create directories, deploy, or contact other services.
set -Eeuo pipefail
if [[ "$#" -ne 2 ]]; then echo 'PREFLIGHT=INVALID_ARGUMENTS' >&2; exit 2; fi
expected_app="$1"
expected_dossier="$2"
base="/home/zomorod2/.private/zomorod-business"
app="$base/app.php"
dossier="$base/genetics-center.php"
db="$base/management.sqlite3"
web="/home/zomorod2/public_html/business/index.php"
valid_sha() { [[ "$1" =~ ^[[:xdigit:]]{64}$ ]]; }
valid_sha "$expected_app" || { echo 'PREFLIGHT=BAD_APP_HASH' >&2; exit 2; }
[[ "$expected_dossier" == ABSENT ]] || valid_sha "$expected_dossier" || { echo 'PREFLIGHT=BAD_DOSSIER_HASH' >&2; exit 2; }
[[ "$(id -un)" == zomorod2 ]] || { echo 'PREFLIGHT=WRONG_USER' >&2; exit 3; }
for p in "$base" "$app" "$db" "$web"; do
  if [[ -L "$p" || ! -e "$p" ]]; then echo 'PREFLIGHT=MISSING_OR_SYMLINK' >&2; exit 3; fi
done
[[ -d "$base" && -f "$app" && -f "$db" && -f "$web" ]] || { echo 'PREFLIGHT=INVALID_FILE_TYPE' >&2; exit 3; }
current_app="$(sha256sum "$app" | awk '{print $1}')"
[[ "$current_app" == "$expected_app" ]] || { echo 'PREFLIGHT=APP_DRIFT' >&2; exit 4; }
if [[ -e "$dossier" || -L "$dossier" ]]; then
  [[ -f "$dossier" && ! -L "$dossier" ]] || { echo 'PREFLIGHT=INVALID_DOSSIER_FILE' >&2; exit 4; }
  [[ "$expected_dossier" != ABSENT ]] || { echo 'PREFLIGHT=DOSSIER_PRESENT_UNEXPECTED' >&2; exit 4; }
  [[ "$(sha256sum "$dossier" | awk '{print $1}')" == "$expected_dossier" ]] || { echo 'PREFLIGHT=DOSSIER_DRIFT' >&2; exit 4; }
  dossier_status=matched
else
  [[ "$expected_dossier" == ABSENT ]] || { echo 'PREFLIGHT=DOSSIER_MISSING' >&2; exit 4; }
  dossier_status=absent_confirmed
fi
command -v php >/dev/null || { echo 'PREFLIGHT=PHP_UNAVAILABLE' >&2; exit 5; }
command -v python3 >/dev/null || { echo 'PREFLIGHT=PYTHON_UNAVAILABLE' >&2; exit 5; }
command -v flock >/dev/null || { echo 'PREFLIGHT=FLOCK_UNAVAILABLE' >&2; exit 5; }
php -l "$app" >/dev/null || { echo 'PREFLIGHT=PHP_SYNTAX_BAD' >&2; exit 5; }
db_bytes="$(stat -c %s "$db")"
free_bytes="$(df --output=avail -B1 "$base" | tail -n 1 | tr -d ' ')"
[[ "$db_bytes" =~ ^[0-9]+$ && "$free_bytes" =~ ^[0-9]+$ ]] || { echo 'PREFLIGHT=DISK_UNKNOWN' >&2; exit 6; }
(( free_bytes > db_bytes * 2 + 104857600 )) || { echo 'PREFLIGHT=DISK_INSUFFICIENT' >&2; exit 6; }

# Fail closed when free filesystem space is misleading: cPanel account quota is binding.
python3 - "$db_bytes" <<'PY_QUOTA'
import json
import shutil
import subprocess
import sys

required = int(sys.argv[1]) * 2 + 104857600
cmd = shutil.which("uapi")
if not cmd:
    print("PREFLIGHT_CPANEL_QUOTA=UAPI_MISSING")
    raise SystemExit(7)
try:
    process = subprocess.run(
        [cmd, "--output=json", "Quota", "get_local_quota_info"],
        capture_output=True, timeout=15, check=False,
    )
    if process.returncode or len(process.stdout) > 1000000:
        raise ValueError("UAPI not verifiable")
    document = json.loads(process.stdout)
    result = document.get("result") if isinstance(document, dict) else None
    if not isinstance(result, dict) or result.get("status") not in (1, True, "1"):
        raise ValueError("quota status unavailable")
    data = result.get("data")
    if not isinstance(data, dict):
        raise ValueError("quota payload unavailable")
    def numeric(value):
        if type(value) is int:
            return value if 0 <= value <= 10**15 else None
        if isinstance(value, str) and value.isascii() and value.isdigit():
            number = int(value)
            return number if 0 <= number <= 10**15 else None
        return None
    limit = numeric(data.get("byte_limit"))
    used = numeric(data.get("bytes_used"))
    if limit is None or limit <= 0 or used is None or used > limit:
        raise ValueError("quota numbers invalid")
    if limit - used <= required:
        print("PREFLIGHT_CPANEL_QUOTA=INSUFFICIENT")
        raise SystemExit(7)
    print("PREFLIGHT_CPANEL_QUOTA=VERIFIED_ENOUGH")
except (OSError, ValueError, subprocess.TimeoutExpired):
    print("PREFLIGHT_CPANEL_QUOTA=UNVERIFIED")
    raise SystemExit(7)
PY_QUOTA
printf '%s\n' \
  'PREFLIGHT=PASS_READ_ONLY' \
  'PREFLIGHT_ACCOUNT=zomorod2' \
  'PREFLIGHT_APP_HASH=matched' \
  "PREFLIGHT_DOSSIER=$dossier_status" \
  "PREFLIGHT_DB_BYTES=$db_bytes" \
  "PREFLIGHT_FREE_BYTES=$free_bytes" \
  'PREFLIGHT_DATABASE_READ=not_performed' \
  'PREFLIGHT_DATABASE_WRITE=no' \
  'PREFLIGHT_DEPLOYMENT=no'
