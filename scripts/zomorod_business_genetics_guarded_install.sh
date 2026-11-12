#!/usr/bin/env bash
# Manual, fail-closed installer for the isolated Zomorod management desk.
# Never run this against a host whose fingerprint or live source has not been verified.
set -Eeuo pipefail
umask 077

if [[ "$#" -ne 6 ]]; then
  echo 'GUARD=invalid_arguments' >&2
  exit 2
fi
expected_app="$1"
expected_dossier="$2"
candidate_app_hash="$3"
candidate_dossier_hash="$4"
release_sha="$5"
stage="$6"
private="/home/zomorod2/.private/zomorod-business"
live_app="$private/app.php"
live_dossier="$private/genetics-center.php"
db_file="$private/management.sqlite3"
backup="/home/zomorod2/.backups/zomorod-business-genetics/$release_sha"

valid_sha() { [[ "$1" =~ ^[0-9a-f]{64}$ ]]; }
valid_sha "$expected_app" && valid_sha "$candidate_app_hash" && valid_sha "$candidate_dossier_hash" || exit 2
if [[ "$expected_dossier" != 'ABSENT' ]]; then valid_sha "$expected_dossier" || exit 2; fi
[[ "$release_sha" =~ ^[0-9a-f]{40}$ ]] || exit 2
[[ "$stage" == "$private/.stage-$release_sha" ]] || exit 2
[[ "$(id -un)" == 'zomorod2' ]] || exit 2
[[ -d "$private" && ! -L "$private" && -d "$stage" && ! -L "$stage" ]] || exit 2
[[ -f "$live_app" && ! -L "$live_app" && -f "$db_file" && ! -L "$db_file" ]] || exit 2
[[ -f "$stage/app.php" && ! -L "$stage/app.php" ]] || exit 2
[[ -f "$stage/genetics-center.php" && ! -L "$stage/genetics-center.php" ]] || exit 2
[[ -f "$stage/install.sh" && ! -L "$stage/install.sh" ]] || exit 2
[[ -f "$stage/homepage-guard.sh" && ! -L "$stage/homepage-guard.sh" ]] || exit 2
[[ -f "$stage/public-surface.py" && ! -L "$stage/public-surface.py" ]] || exit 2
[[ -f "$stage/public-references.py" && ! -L "$stage/public-references.py" ]] || exit 2
[[ -f "$stage/pre-switch.py" && ! -L "$stage/pre-switch.py" ]] || exit 2
[[ -f "$stage/rollback.py" && ! -L "$stage/rollback.py" ]] || exit 2
[[ -d "/home/zomorod2/public_html" && ! -L "/home/zomorod2/public_html" ]] || exit 2
[[ -f "/home/zomorod2/public_html/business/index.php" ]] || exit 2
command -v flock >/dev/null
command -v python3 >/dev/null
phpbin="$(command -v php || true)"
[[ -n "$phpbin" ]] || exit 2

# Lock against simultaneous manual releases. Do not modify accounting data.
exec 9>"$private/.genetics-publish.lock"
flock -n 9 || { echo 'GUARD=concurrent_release' >&2; exit 2; }

actual_app="$(sha256sum "$live_app" | awk '{print $1}')"
[[ "$actual_app" == "$expected_app" ]] || { echo 'GUARD=app_drift' >&2; exit 3; }
dossier_was_present=0
if [[ -e "$live_dossier" || -L "$live_dossier" ]]; then
  [[ -f "$live_dossier" && ! -L "$live_dossier" ]] || exit 3
  dossier_was_present=1
  actual_dossier="$(sha256sum "$live_dossier" | awk '{print $1}')"
  [[ "$expected_dossier" != 'ABSENT' && "$actual_dossier" == "$expected_dossier" ]] || {
    echo 'GUARD=dossier_drift' >&2
    exit 3
  }
else
  [[ "$expected_dossier" == 'ABSENT' ]] || { echo 'GUARD=dossier_absence_mismatch' >&2; exit 3; }
fi

[[ "$(sha256sum "$stage/app.php" | awk '{print $1}')" == "$candidate_app_hash" ]] || exit 3
[[ "$(sha256sum "$stage/genetics-center.php" | awk '{print $1}')" == "$candidate_dossier_hash" ]] || exit 3
"$phpbin" -l "$stage/app.php" >/dev/null
"$phpbin" -l "$stage/genetics-center.php" >/dev/null
grep -Fq "genetics-center.php" "$stage/app.php" || exit 3
grep -Fq "ZM-AGRC-GEN-1405-001" "$stage/genetics-center.php" || exit 3
bash -n "$stage/homepage-guard.sh" || exit 3
python3 -B -m py_compile "$stage/public-surface.py" || exit 3
[[ ! -e "$backup" ]] || { echo 'GUARD=release_already_attempted' >&2; exit 3; }

# Reserve room for the SQLite online backup and both source copies.
db_bytes="$(stat -c %s "$db_file")"
free_bytes="$(df --output=avail -B1 "$private" | tail -n 1 | tr -d ' ')"
[[ "$db_bytes" =~ ^[0-9]+$ && "$free_bytes" =~ ^[0-9]+$ ]] || exit 3
(( free_bytes > db_bytes * 2 + 104857600 )) || { echo 'GUARD=insufficient_disk_for_backup' >&2; exit 3; }

# Fail closed when free filesystem space is misleading: cPanel account quota is binding.
python3 - "$db_bytes" <<'PY_QUOTA'
import json
import shutil
import subprocess
import sys

required = int(sys.argv[1]) * 2 + 104857600
cmd = shutil.which("uapi")
if not cmd:
    print("GUARD_CPANEL_QUOTA=UAPI_MISSING")
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
        print("GUARD_CPANEL_QUOTA=INSUFFICIENT")
        raise SystemExit(7)
    print("GUARD_CPANEL_QUOTA=VERIFIED_ENOUGH")
except (OSError, ValueError, subprocess.TimeoutExpired):
    print("GUARD_CPANEL_QUOTA=UNVERIFIED")
    raise SystemExit(7)
PY_QUOTA

mkdir -p "$backup"
chmod 700 "$backup"
cp -p "$live_app" "$backup/app.php"
if (( dossier_was_present == 1 )); then cp -p "$live_dossier" "$backup/genetics-center.php"; fi
python3 - "$db_file" "$backup/management.sqlite3" <<'PY'
import os, sqlite3, sys
src, dst = sys.argv[1:]
if os.path.islink(src) or os.path.lexists(dst):
    raise SystemExit('Unsafe backup target')
with sqlite3.connect('file:' + src + '?mode=ro', uri=True, timeout=15) as source:
    with sqlite3.connect(dst, timeout=15) as target:
        source.backup(target, pages=128, sleep=0.05)
        if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise SystemExit('Invalid backup integrity')
os.chmod(dst, 0o600)
PY
test -s "$backup/management.sqlite3"

# Capture two stable HTTPS fingerprints of the *public homepage* before switching
# the private business app. If homepage is dynamic or unavailable, fail closed.
homepage_baseline="$(bash "$stage/homepage-guard.sh" capture)"
[[ "$homepage_baseline" =~ ^[0-9a-f]{64}$ ]] || { echo 'PUBLIC_HOMEPAGE_BASELINE=INVALID' >&2; exit 5; }
echo 'PUBLIC_HOMEPAGE_BASELINE=VERIFIED_STABLE'
# Also protect the actual homepage files, local CSS/JS, images and .htaccess.
# Two identical read-only snapshots are required before any live file switch.
surface_baseline="$(python3 -B "$stage/public-surface.py" capture)"
surface_second="$(python3 -B "$stage/public-surface.py" capture)"
[[ "$surface_baseline" =~ ^[0-9a-f]{64}$ && "$surface_second" == "$surface_baseline" ]] || {
  echo 'PUBLIC_SURFACE_BASELINE=UNSTABLE_OR_INVALID' >&2
  exit 5
}
echo 'PUBLIC_SURFACE_BASELINE=VERIFIED_STABLE'
# Cross-check that HTML/CSS local visual dependencies are included in the
# protected public file fingerprint. A missing or untracked file is NO-GO.
python3 -B "$stage/public-references.py" enforce
echo 'PUBLIC_REFERENCES_PROTECTED=VERIFIED'

# Create both staged files before switching; the app is installed last.
install -m 600 "$stage/genetics-center.php" "$private/.genetics-center.new-$release_sha"
install -m 600 "$stage/app.php" "$private/.app.new-$release_sha"
# Recheck concurrently mutable live PHP, exact backups and the actual .new
# files before any live rename. A conflict stops without touching live files.
python3 -B "$stage/pre-switch.py" \
  "$live_app" "$live_dossier" \
  "$backup/app.php" "$backup/genetics-center.php" \
  "$private/.app.new-$release_sha" "$private/.genetics-center.new-$release_sha" \
  "$expected_app" "$expected_dossier" "$candidate_app_hash" "$candidate_dossier_hash"
changed=0
rollback() {
  local rc="$1"
  if (( changed == 1 )); then
    # Never claim success until the actual restored PHP bytes have been
    # independently hash-verified. Preserve unexpected concurrent edits.
    if python3 -B "$stage/rollback.py" \
      "$private" "$backup" "$release_sha" \
      "$expected_app" "$expected_dossier" "$candidate_app_hash" "$candidate_dossier_hash"; then
      echo 'BUSINESS_GENETICS_ROLLBACK=verified' >&2
    else
      echo 'BUSINESS_GENETICS_ROLLBACK=FAILED_MANUAL_RECOVERY_REQUIRED' >&2
      rc=97
    fi
  fi
  exit "$rc"
}
trap 'rollback "$?"' EXIT
changed=1
mv -f "$private/.genetics-center.new-$release_sha" "$live_dossier"
mv -f "$private/.app.new-$release_sha" "$live_app"

"$phpbin" -l "$live_app" >/dev/null
"$phpbin" -l "$live_dossier" >/dev/null
[[ "$(sha256sum "$live_app" | awk '{print $1}')" == "$candidate_app_hash" ]] || exit 4
[[ "$(sha256sum "$live_dossier" | awk '{print $1}')" == "$candidate_dossier_hash" ]] || exit 4
[[ "$(stat -c %a "$live_app")" == 600 ]] || exit 4
[[ "$(stat -c %a "$live_dossier")" == 600 ]] || exit 4
# A failed comparison triggers the existing private-file rollback trap.
bash "$stage/homepage-guard.sh" verify "$homepage_baseline" || exit 5
python3 -B "$stage/public-surface.py" verify "$surface_baseline" || exit 5
python3 -B "$stage/public-surface.py" verify "$surface_baseline" || exit 5

trap - EXIT
echo 'BUSINESS_GENETICS_RELEASE=verified_private_files'
echo 'BUSINESS_ACCOUNTING_DATABASE_WRITES=none'
echo 'BUSINESS_GENETICS_BACKUP=preserved_on_host'
