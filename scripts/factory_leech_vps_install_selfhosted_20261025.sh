#!/usr/bin/env bash
# Execute exclusively as githubops on the owner's VPS; no customer/site changes.
set -euo pipefail
umask 077
test "$(id -un)" = "githubops"
BASE="/home/githubops/factory-runtime/operations/production-instructions"
ENG="$BASE/leech-offline-engine-20261025"
MODEL="$ENG/models/Qwen3-1.7B-Q4_K_M.gguf"
PART="$ENG/models/Qwen3-1.7B-Q4_K_M.gguf.partial"
EXPECTED="d2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5"
URL="https://huggingface.co/ggml-org/Qwen3-1.7B-GGUF/resolve/daeb8e2d528a760970442092f6bf1e55c3b659eb/Qwen3-1.7B-Q4_K_M.gguf"
test -d "$BASE" && test ! -L "$BASE"
test ! -L "$ENG" && test ! -L "$ENG/bin" && test ! -L "$ENG/models"
test ! -L "$MODEL" && test ! -L "$PART"
install -d -m 700 "$ENG" "$ENG/bin" "$ENG/models"
test -f "$ENG/bin/llama-server" && test -x "$ENG/bin/llama-server"
test -f "$BASE/leech-professional-author.py"
test -f "$BASE/leech-vps-resource-guarded-author.py"
free_kib="$(df -Pk "$ENG" | awk 'NR==2{print $4}')"
test "${free_kib:-0}" -ge 7340032 || { echo LEECH_MODEL_DOWNLOAD_REFUSED_PRESERVE_7_GIB; exit 2; }
if ! test -f "$MODEL"; then
  echo "LEECH_MODEL_OFFICIAL_DOWNLOAD_TO_OWNER_VPS=begin"
  curl --fail --location --silent --show-error --retry 4 --retry-delay 5 --connect-timeout 30 --max-time 2400 --limit-rate 4M --continue-at - --output "$PART" "$URL"
  printf '%s  %s\n' "$EXPECTED" "$PART" | sha256sum --check --status || { echo LEECH_MODEL_SHA256_MISMATCH; exit 2; }
  chmod 400 "$PART"
  mv --no-clobber "$PART" "$MODEL"
fi
printf '%s  %s\n' "$EXPECTED" "$MODEL" | sha256sum --check --status
test "$(head -c 4 "$MODEL")" = 'GGUF'
echo LEECH_OFFICIAL_MODEL_SHA256_VERIFIED=true
python3 - <<'PY'
from pathlib import Path
import subprocess
base=Path("/home/githubops/factory-runtime/operations/production-instructions")
script=str(base/"leech-vps-resource-guarded-author.py")
marker="saeit-private-leech-vps-selfhosted-author-20261025"
entry="*/10 * * * * /usr/bin/python3 -B "+script+" >/dev/null 2>&1 # "+marker
prior=subprocess.run(["crontab","-l"],capture_output=True,text=True)
if prior.returncode not in (0,1):
    raise SystemExit("LEECH_CRON_READ_ERROR")
original=prior.stdout if prior.returncode==0 else ""
lines=[line for line in original.splitlines() if marker not in line]
lines.append(entry)
new="\n".join(lines)+"\n"
if new != original:
    subprocess.run(["crontab","-"],input=new,text=True,check=True)
print("LEECH_OWNER_VPS_RECURRING_LOCAL_AUTHOR_CRON=installed")
PY
# This initial process runs exclusively on the VPS at lowest normal priority.
# A process-wide non-blocking flock in the author prevents overlapping cron runs.
nohup /usr/bin/python3 -B "$BASE/leech-vps-resource-guarded-author.py" </dev/null >/dev/null 2>&1 &
echo LEECH_OWNER_VPS_SELFHOSTED_FIRST_AUTHOR_STARTED=true
echo LEECH_NO_PAID_MODEL_API=true
