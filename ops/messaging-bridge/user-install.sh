#!/usr/bin/env bash
# Rootless, idempotent install. Never changes factory, websites, shared crontab entries or live chats.
set -euo pipefail
umask 077
if [[ "$(id -u)" == 0 ]]; then echo "Refusing root; use githubops." >&2; exit 2; fi
if [[ "$#" != 2 ]]; then echo "Usage: user-install.sh BUNDLE_TAR_GZ GIT_REV_12" >&2; exit 2; fi
BUNDLE="$1"
REV="$2"
[[ "$REV" =~ ^[a-f0-9]{12}$ ]] || { echo 'Invalid revision'; exit 2; }
[[ -f "$BUNDLE" && ! -L "$BUNDLE" ]] || exit 2
BASE="$HOME/private-messaging-bridge"
[[ "$BASE" == "/home/githubops/private-messaging-bridge" ]] || { echo 'Unexpected home; abort.' >&2; exit 2; }
for path in "$BASE" "$BASE/runtime" "$BASE/state"; do
  [[ ! -L "$path" ]] || { echo 'Symlinked private directory; abort.' >&2; exit 2; }
done
mkdir -p -m 0700 "$BASE/runtime/versions" "$BASE/state/locks" "$BASE/secrets" "$BASE/backups"
chmod 0700 "$BASE" "$BASE/runtime" "$BASE/runtime/versions" "$BASE/state" "$BASE/state/locks" "$BASE/secrets" "$BASE/backups"
DEST="$BASE/runtime/versions/$REV"
if [[ -e "$DEST" || -L "$DEST" ]]; then
  [[ -f "$DEST/INSTALLED_OK" ]] || { echo 'Existing incomplete version; human review required.' >&2; exit 4; }
  echo 'MMSG_EXISTING_VERSION=PASS'
else
  # Reject escaping members before extraction.
  python3 - "$BUNDLE" <<'PY'
import pathlib, posixpath, sys, tarfile
allowed = {'app', 'bin', 'wheels'}
with tarfile.open(sys.argv[1], 'r:gz') as tar:
    for member in tar:
        name = member.name
        pure = pathlib.PurePosixPath(name)
        if pure.is_absolute() or '..' in pure.parts or not pure.parts or pure.parts[0] not in allowed:
            raise SystemExit('Unsafe archive member')
        if member.issym() or member.islnk():
            dest = posixpath.normpath(posixpath.join(posixpath.dirname(name), member.linkname))
            if member.linkname.startswith('/') or dest == '..' or dest.startswith('../'):
                raise SystemExit('Unsafe archive link')
        if member.isdev() or member.isfifo():
            raise SystemExit('Unexpected archive special file')
PY
  TEMP="$(mktemp -d "$BASE/runtime/versions/.staging-$REV.XXXXXX")"
  trap 'if [[ -n "$TEMP" && -d "$TEMP" ]]; then rm -rf -- "$TEMP"; fi' EXIT
  tar --no-same-owner --no-same-permissions -xzf "$BUNDLE" -C "$TEMP"
  [[ -s "$TEMP/bin/node" && -s "$TEMP/app/telegram.py" && -s "$TEMP/app/whatsapp.mjs" ]] || exit 3
  chmod 0700 "$TEMP/bin/node" "$TEMP/app/user-control.sh" "$TEMP/app/user-launch.sh"
  "$TEMP/bin/node" -e "import('node:crypto').then(()=>console.log('MMSG_NODE_RUNTIME=PASS'))"
  "$TEMP/bin/node" --check "$TEMP/app/whatsapp.mjs"
  (cd "$TEMP/app"; "$TEMP/bin/node" --input-type=module -e "import('@whiskeysockets/baileys').then(()=>console.log('MMSG_BAILEYS_PACKAGE=PASS'))")
  python3 -m venv "$TEMP/venv"
  "$TEMP/venv/bin/python" -m pip install --disable-pip-version-check --no-index --find-links "$TEMP/wheels" -r "$TEMP/app/requirements.txt" --quiet
  "$TEMP/venv/bin/python" -c "import telethon; print('MMSG_TELETHON_PACKAGE=PASS')"
  MOJMSG_STATE_DIR="$BASE/state" "$TEMP/venv/bin/python" "$TEMP/app/telegram.py" status >/dev/null
  MOJMSG_STATE_DIR="$BASE/state" "$TEMP/bin/node" "$TEMP/app/whatsapp.mjs" status --account primary >/dev/null
  printf 'installed version %s\n' "$REV" > "$TEMP/INSTALLED_OK"
  chmod -R go-rwx "$TEMP"
  mv -T "$TEMP" "$DEST"
  TEMP=''
fi
CURRENT="$BASE/runtime/current"
if [[ -e "$CURRENT" && ! -L "$CURRENT" ]]; then echo 'Refusing non-symlink current'; exit 4; fi
if [[ -L "$CURRENT" ]]; then readlink "$CURRENT" > "$BASE/backups/previous-current-$REV.txt"; fi
ln -s "$DEST" "$BASE/runtime/.next-$REV"
mv -Tf "$BASE/runtime/.next-$REV" "$CURRENT"
if ! command -v crontab >/dev/null 2>&1 || ! command -v flock >/dev/null 2>&1; then
  echo 'MMSG_RUNTIME_INSTALLED_CRON_UNAVAILABLE'
  exit 0
fi
# Preserve every existing cron entry byte-for-byte; add only unique marker jobs.
CRON_TMP="$(mktemp -d "$BASE/.cron-$REV.XXXXXX")"
trap 'rm -rf -- "$CRON_TMP"' EXIT
crontab -l > "$CRON_TMP/before" 2>/dev/null || :
cp "$CRON_TMP/before" "$BASE/backups/crontab-before-mmsg-$REV.txt"
cp "$CRON_TMP/before" "$CRON_TMP/after"
if ! grep -Fq 'MMSG_BRIDGE_ROOTLESS_20261028' "$CRON_TMP/after"; then
  if [[ -s "$CRON_TMP/after" ]] && [[ "$(tail -c 1 "$CRON_TMP/after" | wc -l)" == 0 ]]; then echo >> "$CRON_TMP/after"; fi
  cat >> "$CRON_TMP/after" <<'CRON'
* * * * * /home/githubops/private-messaging-bridge/runtime/current/app/user-launch.sh telegram >/dev/null 2>&1 # MMSG_BRIDGE_ROOTLESS_20261028
* * * * * /home/githubops/private-messaging-bridge/runtime/current/app/user-launch.sh whatsapp-primary >/dev/null 2>&1 # MMSG_BRIDGE_ROOTLESS_20261028
* * * * * /home/githubops/private-messaging-bridge/runtime/current/app/user-launch.sh whatsapp-secondary >/dev/null 2>&1 # MMSG_BRIDGE_ROOTLESS_20261028
CRON
  crontab "$CRON_TMP/after"
fi
grep -Fq 'MMSG_BRIDGE_ROOTLESS_20261028' <(crontab -l)
echo "MMSG_ROOTLESS_RUNTIME_INSTALL=PASS"
echo "MMSG_CRON_PERSISTENCE=PASS"
echo "MMSG_SAVED_ACCOUNT_SESSIONS=UNCHANGED"
echo "MMSG_FIRST_PRIVATE_PAIRING=REQUIRED"