#!/usr/bin/env bash
# Safely stage only the hash-verified, already-built SSE2 archive.
set -Eeuo pipefail
umask 077
[[ "$(id -un)" == "githubops" ]] || exit 2
parent="$HOME/comfyui-isolated/.control"
old="$parent/sd-cpp-runtime"
new="$parent/sd-cpp-runtime-sse2"
archive="$old/archive.tar"
expected="aef08d9f47a8366f894647a9eda31ee239b5398a4a347cf3a5576e8cfa3954e8"
test -d "$old" && test -d "$new"
test ! -L "$old" && test ! -L "$new"
test ! -e "$new/bin/sd-cli" || { echo SSE2_ALREADY_STAGED_REFUSE_REPLACEMENT; exit 2; }
test -f "$archive" && test ! -L "$archive" || { echo SSE2_ARCHIVE_NOT_FOUND; exit 3; }
echo "$expected  $archive" | sha256sum -c --status || { echo SSE2_ARCHIVE_HASH_FAILED; exit 4; }
echo SSE2_ARCHIVE_SHA256_VERIFIED
# Reject traversal or symlinks in the archive before extraction.
python3 - "$archive" <<'PY'
import sys,tarfile
with tarfile.open(sys.argv[1], "r:") as archive:
    members=archive.getmembers()
    assert any(member.name == "bin/sd-cli" and member.isfile() for member in members)
    for member in members:
        assert member.name.startswith("bin/") and ".." not in member.name.split("/")
        assert member.isfile() or member.isdir()
print("SSE2_ARCHIVE_MEMBERS_SAFE")
PY
tmp="$(mktemp -d "$parent/.sse2-install.XXXXXXXX")"
trap 'rm -rf -- "$tmp"' EXIT
tar -xf "$archive" -C "$tmp" --no-same-owner --no-same-permissions
test -x "$tmp/bin/sd-cli"
if [[ -f "$old/bin/libgomp.so.1" && ! -L "$old/bin/libgomp.so.1" ]]; then
  cp -- "$old/bin/libgomp.so.1" "$tmp/bin/libgomp.so.1"
fi
chmod -R go-rwx "$tmp"
export LD_LIBRARY_PATH="$tmp/bin"
# Launch only the help command: model inference is tested separately.
if ! timeout 20 "$tmp/bin/sd-cli" -h > "$tmp/help.log" 2>&1; then
  echo SSE2_HELP_EXIT_FAILURE
  exit 5
fi
grep -qiE 'usage|options|sampling-method' "$tmp/help.log"
echo SSE2_CPU_EXECUTABLE_HELP_PASS
# No production or ComfyUI service files are changed.
mv -- "$tmp/bin" "$new/bin"
rm -f -- "$tmp/help.log"
rm -f -- "$archive"
echo SSE2_CPU_RUNTIME_INSTALLED_ISOLATED
echo FACTORY_FILES_UNMODIFIED
