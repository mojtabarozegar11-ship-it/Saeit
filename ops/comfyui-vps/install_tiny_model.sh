#!/usr/bin/env bash
# Install a single hash-verified lightweight text-to-image candidate.
# Only touches the existing private ComfyUI checkpoints directory.
set -Eeuo pipefail
umask 077
test "$(id -un)" = githubops
base="$HOME/comfyui-isolated"
src="$base/source-v0.40.0"
dir="$src/models/checkpoints"
dest="$dir/segmind_tiny_sd_candidate.safetensors"
url="https://huggingface.co/turingevo/tiny-sd-safetensors/resolve/main/segmind_tiny-sd.safetensors"
sha="92e00b860c409f8cfc521a94f779009c6ebd28bf07670bf50e747682ab7b3b72"
test -f "$src/main.py" && test -x "$base/env-cpu/bin/python"
test -d "$dir" && test ! -L "$dir"
test ! -L "$dest"
p="$HOME/factory-runtime/operations/vps-only-loop.pid"
test -r "$p" || { echo "FACTORY_PID_NOT_FOUND_REFUSING_DOWNLOAD"; exit 3; }
read -r factory_pid < "$p"
[[ "$factory_pid" =~ ^[0-9]+$ ]] && kill -0 "$factory_pid"
echo "FACTORY_LOOP_ALIVE_PRE_INSTALL"
ram="$(awk '/^MemAvailable:/{print $2}' /proc/meminfo)"
disk="$(df -Pk "$dir" | awk 'NR==2{print $4}')"
(( ram >= 2500000 && disk >= 5500000 )) || { echo "RESOURCE_BUDGET_INSUFFICIENT"; exit 4; }
if [[ -f "$dest" ]]; then
  echo "$sha  $dest" | sha256sum -c --status
  echo "MODEL_ALREADY_INSTALLED_HASH_VERIFIED"
  exit 0
fi
tmp="$(mktemp "$dir/.candidate-download.XXXXXXXX")"
trap 'rm -f -- "$tmp"' EXIT
chmod 600 "$tmp"
echo "MODEL_DOWNLOAD_BEGIN_EXPECTED_ABOUT_1GB"
nice -n 15 timeout 900s curl --fail --location --silent --show-error \
  --retry 3 --retry-delay 3 --connect-timeout 20 --max-time 880 \
  "$url" -o "$tmp"
size="$(stat -c %s "$tmp")"
(( size > 900000000 && size < 1200000000 )) || { echo "MODEL_FILE_SIZE_INVALID"; exit 5; }
echo "$sha  $tmp" | sha256sum -c --status || { echo "MODEL_SHA256_MISMATCH"; exit 6; }
echo "MODEL_SHA256_VERIFIED"
# A source-level .safetensors schema check does not load model tensors into memory.
"$base/env-cpu/bin/python" - "$tmp" <<'PY'
from safetensors import safe_open
import sys
with safe_open(sys.argv[1], framework="pt", device="cpu") as fp:
    keys=list(fp.keys())
print("MODEL_SAFETENSORS_KEY_COUNT="+str(len(keys)))
assert len(keys) > 200, "NOT_A_DIFFUSION_CHECKPOINT"
PY
test -r "$p"
read -r after < "$p"
[[ "$after" =~ ^[0-9]+$ ]] && kill -0 "$after"
echo "FACTORY_LOOP_ALIVE_POST_DOWNLOAD"
mv -n -- "$tmp" "$dest"
chmod 600 "$dest"
test -f "$dest"
echo "$sha  $dest" | sha256sum -c --status
echo "COMFYUI_TINY_MODEL_INSTALLED_SHA256_VERIFIED"
echo "NO_IMAGE_GENERATION_CLAIM"
