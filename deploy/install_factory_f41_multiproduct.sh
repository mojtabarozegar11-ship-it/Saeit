#!/usr/bin/env bash
# One-pass isolated extension of installed F41; four REAL offline product makers.
# Does not write sites, wallets, crontabs, Django, payments or existing F01-F40.
set -euo pipefail
umask 077
test "$#" -eq 1
stage="$1"
test "$(id -un)" = githubops && test "$(id -u)" -ne 0
test -d "$stage" && test ! -L "$stage"
base="$HOME/factory-runtime"
ops="$base/operations"
private="$base/private/autonomous-product-cycle"
py="$base/.venv/bin/python"
test -x "$py" && test -d "$ops" && test -d "$private"
dest="$ops/f41-multiproduct"
pilot="$private/f41-multiproduct"
test ! -L "$dest" && test ! -L "$pilot"
install -d -m 700 "$dest" "$pilot" "$dest/samples" "$dest/assets" "$dest/backups"
exec 9>"$ops/.f41-multiproduct-install.lock"
flock -w 30 9
for file in factory_f41_multi_product_builder.py factory_f41_token_builder.py catalog.json vesting.json reconciliation.json provenance.json nft_metadata.json demo_art.svg license_terms.txt; do
  test -f "$stage/$file" && test ! -L "$stage/$file"
done
"$py" -B - "$stage" <<'PY'
import ast,json,sys
from pathlib import Path
root=Path(sys.argv[1])
for name in ("factory_f41_multi_product_builder.py","factory_f41_token_builder.py"):
    ast.parse((root/name).read_text("utf8"))
catalog=json.loads((root/"catalog.json").read_text("utf8"))
assert catalog["line_id"]=="F41" and len(catalog["active_builders"])==5
assert catalog["cash_conversion_gate"]["commercial_sale_allowed"] is False
assert catalog["safety"]["mainnet_launch_authorized"] is False
print("F41_MULTIPRODUCT_INSTALL_POLICY=PASS")
PY
# Idempotent immutable revision: unknown existing differences need manual review.
for mapping in "factory_f41_multi_product_builder.py:factory_f41_multi_product_builder.py" "catalog.json:catalog.json" "vesting.json:samples/vesting.json" "reconciliation.json:samples/reconciliation.json" "provenance.json:samples/provenance.json" "nft_metadata.json:samples/nft_metadata.json" "demo_art.svg:assets/demo_art.svg" "license_terms.txt:assets/license_terms.txt"; do
  src="${mapping%%:*}"; name="${mapping#*:}"
  out="$dest/$name"
  test ! -L "$out"
  if test -e "$out"; then
    cmp -s "$stage/$src" "$out" || { echo "F41_UNKNOWN_INSTALLED_REVISION:$name"; exit 1; }
  else
    install -m 600 "$stage/$src" "$out"
  fi
done
# Repair the original F41 source/receipt validator after proving compatibility
# against the original immutable private pilot. Preserve exact original backup.
legacy="$ops/f41-blockchain-token"
token="$legacy/factory_f41_token_builder.py"
oldpilot="$private/f41-blockchain-token/private-pilot-v1"
test -f "$token" && test ! -L "$token" && test -f "$legacy/pilot.json"
"$py" -B "$stage/factory_f41_token_builder.py" --spec "$legacy/pilot.json" --out "$oldpilot" --verify
if ! cmp -s "$stage/factory_f41_token_builder.py" "$token"; then
  test "$(git hash-object "$token")" = "f89e1ce47e430833da2a64b0bda81b4556e9eb8b" || { echo F41_UNKNOWN_LEGACY_TOKEN_REVISION; exit 1; }
  oldhash="$(sha256sum "$token" | awk '{print $1}')"
  backup="$dest/backups/token-builder-$oldhash.py"
  test ! -L "$backup"
  if test ! -e "$backup"; then
    install -m 600 "$token" "$backup"
  else
    cmp -s "$token" "$backup"
  fi
  tmp="$legacy/.f41-token-repaired-$$"
  install -m 600 "$stage/factory_f41_token_builder.py" "$tmp"
  mv -f -- "$tmp" "$token"
  "$py" -B "$token" --spec "$legacy/pilot.json" --out "$oldpilot" --verify
fi
count=0
for kind in vesting reconciliation provenance nft_metadata; do
  work="$pilot/$kind-v1"
  spec="$dest/samples/$kind.json"
  if test -e "$work"; then
    "$py" -B "$dest/factory_f41_multi_product_builder.py" --spec "$spec" --out "$work" --assets "$dest/assets" --verify
  else
    "$py" -B "$dest/factory_f41_multi_product_builder.py" --spec "$spec" --out "$work" --assets "$dest/assets"
  fi
  count=$((count+1))
done
test "$count" -eq 4
echo F41_MULTIPRODUCT_INSTALL_ON_VPS=PASS
echo F41_INDEPENDENT_REAL_PRIVATE_PRODUCT_KINDS=4
echo F41_TOTAL_FUNCTIONAL_BUILDER_KINDS=5
echo F41_TOKEN_MANIFEST_V1_HARDENED=PASS
echo F41_MAINNET_TRANSACTIONS=0
echo F41_COMMERCIAL_SALES_VERIFIED=0
echo F41_GENERATION100_AND_QA1000_CERTIFIED=false
echo F41_PRIOR_FORTY_LINES_UNTOUCHED=true
