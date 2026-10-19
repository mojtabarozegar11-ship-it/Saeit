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
  extraction="$(mktemp -d "$root/versions/.extract-$revision-XXXXXX")"
  trap 'rm -rf -- "$extraction"' EXIT
  tar -xf "$bundle/runtime.tar.xz" -C "$extraction" --no-same-owner
  mv -- "$extraction" "$target"
  trap - EXIT
fi
# Restore only package-declared links, relocated within this private prefix.
if [[ -f "$bundle/link-map.json" ]]; then
  "$base/.venv/bin/python" - "$target/prefix" "$bundle/link-map.json" <<'PYLINK'
import json,os,pathlib,sys
root=pathlib.Path(sys.argv[1]).resolve()
for name,destination in json.loads(pathlib.Path(sys.argv[2]).read_text()).items():
    relative=pathlib.PurePosixPath(name)
    if relative.is_absolute() or '..' in relative.parts: raise ValueError('BAD_LINK_PATH')
    link=root/name; dest=root/destination.lstrip('/')
    link.parent.resolve().relative_to(root)
    dest.resolve().relative_to(root)
    if not dest.exists() or (link.exists() and not link.is_symlink()): continue
    if link.is_symlink(): link.unlink()
    link.symlink_to(os.path.relpath(dest,link.parent))
PYLINK
fi
# Distro bootstrap files hard-code system locations; relocate the private copies.
"$base/.venv/bin/python" - "$target/prefix" <<'PYOFFICE'
import pathlib,sys
root=pathlib.Path(sys.argv[1]).resolve()
program=root/'usr/lib/libreoffice/program'
for file in list(program.glob('*rc'))+list(program.rglob('*.rdb')):
    if not file.is_file(): continue
    try: text=file.read_text()
    except UnicodeError: continue
    updated=text
    for path in ('/usr/lib/libreoffice','/etc/libreoffice','/usr/share/java'):
        updated=updated.replace('file://'+path,(root/path.lstrip('/')).as_uri())
    if updated!=text: file.write_text(updated)
PYOFFICE
# Restore relocated office resource links removed from the original portable archive.
for entry in 'share:../../share/libreoffice' 'ure-link:../ure'; do
  name="${entry%%:*}"; destination="${entry#*:}"
  office_link="$target/prefix/usr/lib/libreoffice/$name"
  if [[ ! -e "$office_link" && ! -L "$office_link" ]]; then
    ln -s "$destination" "$office_link"
  fi
done
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
export LD_LIBRARY_PATH="$target/prefix/usr/lib/x86_64-linux-gnu:$target/prefix/lib/x86_64-linux-gnu:$target/prefix/usr/lib:$target/prefix/usr/lib/x86_64-linux-gnu/pulseaudio:$target/prefix/usr/lib/x86_64-linux-gnu/blas:$target/prefix/usr/lib/x86_64-linux-gnu/lapack"
exec "$target/prefix/usr/bin/$tool" "\$@"
EOF
  chmod 700 "$target/bin/$tool"
done
cat > "$target/bin/blender" <<EOF
#!/bin/bash
set -euo pipefail
export LD_LIBRARY_PATH="$target/prefix/usr/lib/x86_64-linux-gnu:$target/prefix/lib/x86_64-linux-gnu:$target/prefix/usr/lib:$target/prefix/usr/lib/x86_64-linux-gnu/pulseaudio:$target/prefix/usr/lib/x86_64-linux-gnu/blas:$target/prefix/usr/lib/x86_64-linux-gnu/lapack"
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
export LD_LIBRARY_PATH="$target/prefix/usr/lib/libreoffice/program:$target/prefix/usr/lib/x86_64-linux-gnu:$target/prefix/lib/x86_64-linux-gnu:$target/prefix/usr/lib:$target/prefix/usr/lib/x86_64-linux-gnu/pulseaudio:$target/prefix/usr/lib/x86_64-linux-gnu/blas:$target/prefix/usr/lib/x86_64-linux-gnu/lapack"
export FONTCONFIG_FILE="$target/fonts.conf" SAL_USE_VCLPLUGIN=svp
export URE_BOOTSTRAP="vnd.sun.star.pathname:$target/prefix/usr/lib/libreoffice/program/fundamentalrc"
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
if ! timeout 480 nice -n 15 "$target/venv/bin/python" "$target/prove.py" "$target"; then
  "$target/venv/bin/python" - "$target/proof.json" <<'PYFAIL'
import json,pathlib,sys
p=pathlib.Path(sys.argv[1])
if p.is_file():
    report=json.loads(p.read_text())
    print(json.dumps({k:v for k,v in report['checks'].items() if not v['passed']},sort_keys=True))
PYFAIL
  exit 5
fi
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
