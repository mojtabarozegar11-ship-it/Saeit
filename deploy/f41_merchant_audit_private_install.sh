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
for name in f41_merchant_audit_cli.py verifier.py tests.py tests_verifier.py worker.py tests_worker.py README.md LICENSE.txt invoices.csv payments.csv; do
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
  for name in f41_merchant_audit_cli.py verifier.py tests.py tests_verifier.py worker.py tests_worker.py README.md LICENSE.txt invoices.csv payments.csv; do
    cmp -s "$stage/$name" "$dest/$name" || { echo F41_MERCHANT_RELEASE_DRIFT; exit 1; }
  done
else
  install -d -m 700 "$dest"
  for name in f41_merchant_audit_cli.py verifier.py tests.py tests_verifier.py worker.py tests_worker.py README.md LICENSE.txt invoices.csv payments.csv; do
    install -m 600 "$stage/$name" "$dest/$name"
  done
fi
# Verify actual executable on this VPS, using a new private demo folder.
demo="$pilot/demo-$run_id"
test ! -e "$demo" && test ! -L "$demo"
"$python" -B "$dest/f41_merchant_audit_cli.py" --invoices "$dest/invoices.csv" --payments "$dest/payments.csv" --out "$demo"
"$python" -B "$dest/f41_merchant_audit_cli.py" --invoices "$dest/invoices.csv" --payments "$dest/payments.csv" --out "$demo" --verify
"$python" -B "$dest/verifier.py" --help >/dev/null
"$python" -B "$dest/worker.py" --help >/dev/null
# Smoke-test the REAL private inbox -> reconciled report path without any network.
smoke="$pilot/intake-smoke-$run_id"
test ! -e "$smoke" && test ! -L "$smoke"
install -d -m 700 "$smoke" "$smoke/inbox" "$smoke/inbox/job-smoke"
install -m 600 "$dest/invoices.csv" "$smoke/inbox/job-smoke/invoices.csv"
install -m 600 "$dest/payments.csv" "$smoke/inbox/job-smoke/payments.csv"
install -m 600 /dev/null "$smoke/inbox/job-smoke/READY"
F41_WORKER_ONCHAIN_ENABLED=0 "$python" -B "$dest/worker.py" --runtime "$smoke"
"$python" -B - "$smoke" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1])
status=json.loads((root/"outbox/job-smoke/status.json").read_text())
assert status["result"]=="COMPLETE_READONLY",status
assert status["delivery_authorized"] is False
assert status["onchain_check_enabled"] is False
assert (root/"outbox/job-smoke/reconciliation/integrity.json").is_file()
print("F41_MERCHANT_REAL_INTAKE_SMOKE=PASS")
PY
# Live intake is PRIVATE and empty until properly sealed invoices arrive.
runtime="$ops/f41-merchant-audit"
"$python" -B "$dest/worker.py" --runtime "$runtime"
runner="$runtime/run-private-worker.sh"
next_runner="$runtime/.run-private-worker-$run_id.tmp"
test ! -e "$next_runner" && test ! -L "$next_runner"
printf '#!/usr/bin/env bash\nset -euo pipefail\numask 077\nexport F41_WORKER_ONCHAIN_ENABLED=1\nexec "%s" -B "%s/worker.py" --runtime "%s"\n' "$python" "$dest" "$runtime" > "$next_runner"
chmod 700 "$next_runner"
mv -- "$next_runner" "$runner"
# Preserve all existing user crontab entries; only add a distinct F41 marker.
if ! command -v crontab >/dev/null; then
  echo F41_MERCHANT_SCHEDULER_MISSING
  exit 1
fi
if original="$(crontab -l 2>&1)"; then
  :
elif [[ "$original" == *"no crontab for"* ]]; then
  original=""
else
  echo F41_MERCHANT_CRONTAB_UNREADABLE
  exit 1
fi
if ! printf '%s\n' "$original" | grep -Fq '# F41_PRIVATE_INTAKE'; then
  {
    if test -n "$original"; then printf '%s\n' "$original"; fi
    printf '%s\n' "* * * * * $runner >/dev/null 2>&1 # F41_PRIVATE_INTAKE"
  } | crontab -
fi
crontab -l | grep -Fq '# F41_PRIVATE_INTAKE'
echo F41_MERCHANT_PRIVATE_SCHEDULER_REGISTERED=true
echo F41_MERCHANT_PRIVATE_INBOX="$runtime/inbox"
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
