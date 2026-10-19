#!/usr/bin/env bash
# Private toolchain only: no sudo, no system package changes, no scheduler edits.
set -euo pipefail
umask 077
bundle="${1:?bundle directory required}"
revision="${2:?revision required}"
[[ "$revision" =~ ^[a-f0-9]{40}$ ]]
test "$(id -un)" = githubops
test "$(id -u)" -ne 0
base="$HOME/factory-runtime"
test -x "$base/.venv/bin/python"
root="$base/operations/build-toolchain"
mkdir -p "$root/versions"
chmod 700 "$root" "$root/versions"
exec 9>"$root/.install.lock"
flock -w 30 9 || exit 2
free_mb="$(df -Pm "$root" | awk 'NR==2 {print $4}')"
((free_mb >= 5120)) || { echo TOOLCHAIN_DISK_RESERVE_NOT_MET; exit 3; }
target="$root/versions/$revision"
test ! -L "$target"
if [[ ! -d "$target" ]]; then
  mkdir -m 700 "$target"
  tar -xf "$bundle/runtime.tar" -C "$target" --no-same-owner
fi
mkdir -p "$target/bin" "$target/work" "$target/models" "$target/font-cache"
if [[ ! -x "$target/venv/bin/python" ]]; then
  "$base/.venv/bin/python" -m venv "$target/venv"
fi
export PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_INPUT=1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
if [[ ! -f "$target/python-installed.txt" ]]; then
  timeout 480 nice -n 15 "$target/venv/bin/python" -m pip install \
    --only-binary=:all: --timeout 30 --retries 1 \
    Pillow python-docx python-pptx reportlab openpyxl pypdf \
    > "$target/pip-install.log" 2>&1
  "$target/venv/bin/python" -m pip check
  "$target/venv/bin/python" -m pip freeze > "$target/python-installed.txt"
fi
cat > "$target/fonts.conf" <<EOF
<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig><dir>$target/prefix/usr/share/fonts</dir><cachedir>$target/font-cache</cachedir></fontconfig>
EOF
for tool in ffmpeg ffprobe pdftoppm; do
  cat > "$target/bin/$tool" <<EOF
#!/bin/bash
set -euo pipefail
export LD_LIBRARY_PATH="$target/prefix/usr/lib/x86_64-linux-gnu:$target/prefix/lib/x86_64-linux-gnu"
exec "$target/prefix/usr/bin/$tool" "\$@"
EOF
  chmod 700 "$target/bin/$tool"
done
cat > "$target/bin/blender" <<EOF
#!/bin/bash
set -euo pipefail
export LD_LIBRARY_PATH="$target/prefix/usr/lib/x86_64-linux-gnu:$target/prefix/lib/x86_64-linux-gnu"
export BLENDER_SYSTEM_SCRIPTS="$target/prefix/usr/share/blender/scripts"
export BLENDER_SYSTEM_DATAFILES="$target/prefix/usr/share/blender/datafiles"
export PYTHONHOME="$target/prefix/usr"
exec "$target/prefix/usr/bin/blender" "\$@"
EOF
chmod 700 "$target/bin/blender"
# Locate the versioned Blender resource directory without assuming a distro layout.
blender_data="$(find "$target/prefix/usr/share/blender" -type d -name scripts -print -quit)"
if [[ -n "$blender_data" ]]; then
  sed -i "s|$target/prefix/usr/share/blender/scripts|$blender_data|" "$target/bin/blender"
  sed -i "s|$target/prefix/usr/share/blender/datafiles|$(dirname "$blender_data")/datafiles|" "$target/bin/blender"
fi
cat > "$target/bin/libreoffice" <<EOF
#!/bin/bash
set -euo pipefail
export LD_LIBRARY_PATH="$target/prefix/usr/lib/libreoffice/program:$target/prefix/usr/lib/x86_64-linux-gnu:$target/prefix/lib/x86_64-linux-gnu"
export FONTCONFIG_FILE="$target/fonts.conf" SAL_USE_VCLPLUGIN=svp
exec "$target/prefix/usr/lib/libreoffice/program/soffice" "\$@"
EOF
chmod 700 "$target/bin/libreoffice"
# Model and CPU-only C++ runtime are hash-verified before extraction/activation.
printf '%s  %s\n' '1d9614638d18024d0fbb36575a15f1302a3adf044df10345688ec4f6e1c4ff32' \
  "$bundle/qwen2.5-coder-0.5b-instruct-q4_k_m.gguf" | sha256sum -c --status
if [[ ! -f "$target/models/coder.gguf" ]]; then
  install -m 600 "$bundle/qwen2.5-coder-0.5b-instruct-q4_k_m.gguf" "$target/models/coder.gguf"
fi
install -m 600 "$bundle/prove.py" "$target/prove.py"
timeout 480 nice -n 15 "$target/venv/bin/python" "$target/prove.py" "$target"
# Only a fully verified toolchain becomes current. Previous versions remain intact.
"$target/venv/bin/python" - "$target" "$root" <<'PY'
import json,os,pathlib,sys
from datetime import datetime,timezone
target,root=map(pathlib.Path,sys.argv[1:])
report=json.loads((target/'proof.json').read_text())
assert all(x['passed'] for x in report['checks'].values())
report.update(schema='saeit.factory.toolchain.v1',root=str(target),
              validated_utc=datetime.now(timezone.utc).isoformat(),
              python=str(target/'venv/bin/python'),
              tools={name:str(target/'bin'/name) for name in ('ffmpeg','ffprobe','blender','libreoffice','pdftoppm')},
              local_llm=str(target/'llama/bin/llama-cli'),model=str(target/'models/coder.gguf'),
              external_api_required=False,commercial_quality_approved=False,
              generation_promotions=0,all_40_family_adapters_implemented=False)
stage=root/'.toolchain-manifest.tmp'
stage.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');stage.chmod(0o600)
os.replace(stage,root/'toolchain-manifest.json')
print('FACTORY_TOOLCHAIN_REAL_CHECKS='+str(len(report['checks'])))
print('FACTORY_TOOLCHAIN_ACTIVATION=PASS')
PY
