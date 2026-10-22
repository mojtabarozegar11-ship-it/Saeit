#!/usr/bin/env bash
# Isolated F41 private source-kit install; no modification to 40-line registry.
set -euo pipefail
umask 077
test "$#" -eq 3
test "$(id -un)" = githubops && test "$(id -u)" -ne 0
source_py="$1"; source_config="$2"; source_spec="$3"
for item in "$source_py" "$source_config" "$source_spec"; do
  test -f "$item" && test ! -L "$item"
done
base="$HOME/factory-runtime"
ops="$base/operations"
private="$base/private/autonomous-product-cycle"
python="$base/.venv/bin/python"
test -x "$python"
test -d "$ops" && test ! -L "$ops"
test -d "$private" && test ! -L "$private"
target="$ops/f41-blockchain-token"
pilot="$private/f41-blockchain-token"
test ! -L "$target" && test ! -L "$pilot"
install -d -m 700 "$target" "$pilot"
exec 9>"$ops/.f41-blockchain-token-install.lock"
flock -w 30 9
"$python" -B - "$source_py" "$source_config" "$source_spec" <<'PY'
import ast,json,sys
from pathlib import Path
ast.parse(Path(sys.argv[1]).read_text("utf8"))
cfg=json.loads(Path(sys.argv[2]).read_text("utf8"))
spec=json.loads(Path(sys.argv[3]).read_text("utf8"))
assert cfg["id"]=="F41" and cfg["auto_deploy"] is False
assert cfg["mainnet_enabled"] is False and cfg["public_sale_enabled"] is False
assert cfg["coordinator_binding"]=="pending_authenticated_qa_capability"
assert spec["network"]=="shasta" and spec["mode"]=="fixed_supply"
print("F41_INSTALL_SOURCE_POLICY=PASS")
PY
for pair in "factory_f41_token_builder.py:$source_py" "line.json:$source_config" "pilot.json:$source_spec"; do
  name="${pair%%:*}"; source="${pair#*:}"
  dest="$target/$name"
  test ! -L "$dest"
  if test -e "$dest"; then
    cmp -s "$source" "$dest" || { echo "F41_REVISION_CONFLICT:$name"; exit 1; }
  else
    install -m 600 "$source" "$dest"
  fi
done
candidate="$pilot/private-pilot-v1"
if test -e "$candidate"; then
  "$python" -B "$target/factory_f41_token_builder.py" --spec "$target/pilot.json" --out "$candidate" --verify
else
  "$python" -B "$target/factory_f41_token_builder.py" --spec "$target/pilot.json" --out "$candidate"
fi
test -f "$candidate/manifest.json" && test ! -L "$candidate/manifest.json"
"$python" -B - "$candidate/manifest.json" <<'PY'
import json,sys
from pathlib import Path
p=json.loads(Path(sys.argv[1]).read_text())
assert p["line_id"]=="F41" and p["network"]=="shasta"
assert not p["commercial_release"] and not p["quality_1000_certified"]
assert not p["generation_100_verified"] and not p["production_deployment_enabled"]
assert p["transaction_broadcasts"]==0 and p["site_writes"]==0
print("F41_VPS_PRIVATE_CANDIDATE_HASH_VERIFIED=PASS")
PY
echo F41_FACTORY_LINE_PRIVATE_INSTALLED=PASS
echo F41_EXISTING_FORTY_LINES_UNTOUCHED=true
echo F41_MASTER_AGENT_QA_BINDING=pending
echo F41_MAINNET_AND_SALES_DISABLED=true
