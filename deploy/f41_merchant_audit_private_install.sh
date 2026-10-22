#!/usr/bin/env bash
# Private buyer-evaluation package only. No sites, wallets, payments or cron changes.
set -euo pipefail
umask 077
test "$#" -eq 3
stage="$1"
revision="$2"
run_id="$3"
test "$(id -un)" = githubops && test "$(id -u)" -ne 0
[[ "$revision" =~ ^[0-9a-f]{40}$ ]]
[[ "$run_id" =~ ^[0-9]{5,15}$ ]]
test -d "$stage" && test ! -L "$stage"
base="$HOME/factory-runtime"
python="$base/.venv/bin/python"
ops="$base/operations"
private="$base/private/autonomous-product-cycle"
test -x "$python" && test -d "$ops" && test -d "$private"
for name in f41_merchant_audit_cli.py verifier.py tests.py tests_verifier.py README.md LICENSE.txt invoices.csv payments.csv; do
  test -f "$stage/$name" && test ! -L "$stage/$name"
done
dest="$ops/f41-merchant-audit/releases/$revision"
pilot="$private/f41-merchant-audit"
test ! -L "$ops/f41-merchant-audit" && test ! -L "$private/f41-merchant-audit"
install -d -m 700 "$ops/f41-merchant-audit" "$ops/f41-merchant-audit/releases" "$pilot"
exec 9>"$ops/f41-merchant-audit/.install.lock"
flock -w 30 9
if test -e "$dest"; then
  test -d "$dest" && test ! -L "$dest"
  for name in f41_merchant_audit_cli.py verifier.py tests.py tests_verifier.py README.md LICENSE.txt invoices.csv payments.csv; do
    cmp -s "$stage/$name" "$dest/$name" || { echo F41_MERCHANT_RELEASE_DRIFT; exit 1; }
  done
else
  install -d -m 700 "$dest"
  for name in f41_merchant_audit_cli.py verifier.py tests.py tests_verifier.py README.md LICENSE.txt invoices.csv payments.csv; do
    install -m 600 "$stage/$name" "$dest/$name"
  done
fi
# Verify actual executable on this VPS, using a new private demo folder.
demo="$pilot/demo-$run_id"
test ! -e "$demo" && test ! -L "$demo"
"$python" -B "$dest/f41_merchant_audit_cli.py" --invoices "$dest/invoices.csv" --payments "$dest/payments.csv" --out "$demo"
"$python" -B "$dest/f41_merchant_audit_cli.py" --invoices "$dest/invoices.csv" --payments "$dest/payments.csv" --out "$demo" --verify
"$python" -B "$dest/verifier.py" --help >/dev/null
"$python" -B - "$dest" "$pilot/evaluation-$revision.zip" <<'PY'
from pathlib import Path
import sys,zipfile
root=Path(sys.argv[1])
out=Path(sys.argv[2])
names=("f41_merchant_audit_cli.py","verifier.py","README.md","LICENSE.txt","invoices.csv","payments.csv")
if out.exists() or out.is_symlink():
    with zipfile.ZipFile(out,"r") as z:
        assert sorted(z.namelist()) == sorted(names)
        assert all(z.read(n) == (root/n).read_bytes() for n in names)
else:
    with zipfile.ZipFile(out,"x",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name in names:
            z.write(root/name,name)
    out.chmod(0o600)
    with zipfile.ZipFile(out,"r") as z:
        assert sorted(z.namelist()) == sorted(names)
        assert all(z.read(n) == (root/n).read_bytes() for n in names)
PY
echo F41_MERCHANT_PRIVATE_RELEASE_SHA="$revision"
echo F41_MERCHANT_VPS_PILOT_SHA256="$(sha256sum "$demo/integrity.json" | awk '{print $1}')"
echo F41_MERCHANT_EVALUATION_ZIP_SHA256="$(sha256sum "$pilot/evaluation-$revision.zip" | awk '{print $1}')"
echo F41_MERCHANT_PUBLIC_LISTING=false
echo F41_MERCHANT_ONCHAIN_FINALITY=false
echo F41_MERCHANT_REAL_REVENUE_PROVEN=false
