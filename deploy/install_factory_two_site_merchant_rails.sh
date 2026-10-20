#!/usr/bin/env bash
# Strict private 40x2 merchant rails; never touch either public store/payment.
set -euo pipefail
umask 077
test "$(id -un)" = githubops && test "$#" -eq 1
stage="$1";test -d "$stage" && test ! -L "$stage"
base="$HOME/factory-runtime";ops="$base/operations"
root="$base/private/autonomous-product-cycle";target="$ops/forty-execution"
registry="$ops/forty-family-master/forty_families.json"
scheduler="$target/periodic-dispatch.sh"
py="$base/.venv/bin/python"
file="factory_two_site_merchant_rails.py"
test -x "$py" && test -s "$registry" && test -s "$stage/$file"
test -s "$target/factory_commerce40_admission.py"
test -f "$scheduler" && test ! -L "$scheduler"
test "$(crontab -l|grep -c SAEIT_FACTORY_FORTY_FAMILY_OPERATIONAL_DISPATCH_V1)" -eq 1
exec 9>"$ops/.two-site-merchant-rails.lock";flock -w 35 9
install -d -m 700 "$ops/backups"
backup="$ops/backups/two-merchant-rails-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup"
if test -f "$target/$file";then
 test ! -L "$target/$file";cp -p "$target/$file" "$backup/$file"
fi
cp -p "$scheduler" "$backup/periodic-dispatch.sh"
crontab -l > "$backup/crontab"
rollback(){
 local code=$?
 if test "$code" -ne 0;then
  if test -f "$backup/$file";then cp -p "$backup/$file" "$target/$file";else rm -f "$target/$file";fi
  cp -p "$backup/periodic-dispatch.sh" "$scheduler"
  rm -f "$target/$file.new" "$scheduler.new"
  echo FACTORY_PAYMENT_RAILS_SOURCE_ROLLBACK=PASS
 fi
 return "$code"
}
trap rollback EXIT
test ! -L "$stage/$file"
"$py" -B -m py_compile "$stage/$file"
install -m 600 "$stage/$file" "$target/$file.new"
test "$(sha256sum "$stage/$file"|cut -d' ' -f1)" = "$(sha256sum "$target/$file.new"|cut -d' ' -f1)"
mv -f "$target/$file.new" "$target/$file"
# Use existing independent manufacturer receipts. Do not touch store or merchants.
"$py" -B "$target/factory_commerce40_admission.py" --factory-private "$root" --registry "$registry" --module-dir "$target"
"$py" -B "$target/$file" --factory-private "$root"
"$py" -B - "$target/$file" "$root" <<'PY'
import importlib.util,json,sys
from pathlib import Path
source=Path(sys.argv[1]);root=Path(sys.argv[2])
spec=importlib.util.spec_from_file_location("real_merchant_rails_check",str(source))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
dashboard=m.load(root/"merchant-rails/dashboard.json",500000)
assert dashboard["private_site_family_offer_routes"]==80
assert dashboard["unique_payment_rail_types"]==2
assert dashboard["sites_changed"]==0 and dashboard["live_charges"]==0
for fid in ("F01","F12","F24","F29","F35","F40"):
 for site in ("mojplaywin","zomorodmelal"):
  route=m.load(root/"merchant-rails/routes"/site/(fid+".json"))
  assert route["family_id"]==fid
  assert route["site_id"]==site
  assert route["collect_customer_payment"] is False
  assert route["automatic_paid_entitlement"] is False
  currency="TRX" if site=="mojplaywin" else "IRR"
  other="IRR" if site=="mojplaywin" else "TRX"
  assert m.require_currency(site,currency)==currency
  try:m.require_currency(site,other);raise AssertionError("rail mismatch accepted")
  except ValueError:pass
  try:m.reject_unverified_payment(route,{"status":"paid"});raise AssertionError("bogus receipt accepted")
  except ValueError:pass
print("VPS_TWO_SITE_BANK_SHAHR_VS_CRYPTO_ROUTES=80")
print("VPS_TWO_SITE_NO_CROSS_SITE_PAYMENT=PASS")
print("VPS_TWO_SITE_UNVERIFIED_PAID_RECEIPT_ALWAYS_BLOCKED=PASS")
PY
"$py" -B - "$scheduler" "$scheduler.new" <<'PY'
from pathlib import Path
import sys
path=Path(sys.argv[1]);target=Path(sys.argv[2]);script=path.read_text()
hook='/usr/bin/timeout 75s "$HOME/factory-runtime/.venv/bin/python" -B "$HOME/factory-runtime/operations/forty-execution/factory_two_site_merchant_rails.py" --factory-private "$HOME/factory-runtime/private/autonomous-product-cycle" || echo FACTORY_TWO_MERCHANT_RAILS_REWORK_REQUIRED\n'
assert script.count('set -euo pipefail')==1
assert 'factory_two_site_merchant_rails.py' not in script or hook in script
if hook not in script:
 script=script.replace('set -euo pipefail\n','set -euo pipefail\n'+hook,1)
assert script.count('factory_two_site_merchant_rails.py')==1
target.write_text(script);target.chmod(path.stat().st_mode&0o777)
PY
bash -n "$scheduler.new";mv -f "$scheduler.new" "$scheduler"
test "$(crontab -l|sha256sum|cut -d' ' -f1)" = "$(sha256sum "$backup/crontab"|cut -d' ' -f1)"
trap - EXIT
echo VPS_TWO_SITE_MERCHANT_RAIL_ROUTING=PASS
echo VPS_EXISTING_CRON_REUSED=PASS
echo VPS_BANK_GATEWAY_LIVE_CODES_AND_SITE_PAYMENTS_UNCHANGED=PASS
