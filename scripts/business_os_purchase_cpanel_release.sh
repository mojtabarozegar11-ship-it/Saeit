#!/usr/bin/env bash
# Additive paid-order subscriber release; no migrations, monetary actions, or UI edits.
# Runs ONLY from a verified cPanel private staging release. Keeps per-file rollback.
set -euo pipefail
umask 077
stage="$(pwd -P)"
case "$stage" in
  /home/zomorod2/Saeit-staging/releases/business-os-paid-*) ;;
  *) echo "PURCHASE_RELEASE_BAD_STAGE"; exit 81 ;;
esac
prod="/home/zomorod2/Saeit"
test -f "$prod/manage.py" || { echo "PURCHASE_RELEASE_APP_MISSING"; exit 82; }
backup="$stage/rollback"
mkdir -p "$backup"
exec 9> /home/zomorod2/Saeit-staging/.paid-purchase-deploy.lock
flock -n 9 || { echo "PURCHASE_RELEASE_LOCKED"; exit 83; }

files=(
  core/business_management.py
  core/business_scientist.py
  core/management/commands/business_operating_review.py
  core/purchase_event.py
  core/purchase_signals.py
)
interpreter=""
for candidate in \
  /home/zomorod2/Saeit/.venv/bin/python \
  /home/zomorod2/Saeit/venv/bin/python \
  /home/zomorod2/virtualenv/Saeit/3.11/bin/python \
  /home/zomorod2/virtualenv/Saeit/3.11/bin/python3 \
  /home/zomorod2/virtualenv/Saeit/3.10/bin/python \
  /home/zomorod2/virtualenv/Saeit/3.12/bin/python; do
  if test -x "$candidate" && "$candidate" -B -c "import django" >/dev/null 2>&1; then
    interpreter="$candidate"
    break
  fi
done
test -n "$interpreter" || { echo "PURCHASE_RELEASE_INTERPRETER_MISSING"; exit 84; }

restart() {
  mkdir -p "$prod/tmp"
  touch "$prod/tmp/restart.txt"
}
rollback() {
  if test -f "$backup/armed"; then
    for rel in "${files[@]}"; do
      if test -f "$backup/$rel"; then
        cp -p "$backup/$rel" "$prod/$rel"
      elif test -f "$prod/$rel"; then
        mkdir -p "$backup/removed/$(dirname "$rel")"
        mv "$prod/$rel" "$backup/removed/$rel"
      fi
    done
    if test -f "$backup/core/apps.py"; then
      cp -p "$backup/core/apps.py" "$prod/core/apps.py"
    fi
    restart
    echo "PURCHASE_RELEASE_ROLLED_BACK"
  fi
}
precheck() {
  for rel in "${files[@]}"; do
    test -f "$stage/$rel" && test ! -L "$stage/$rel" || return 1
    # Existing modules belong to the owner unless exact contents match.
    if test -e "$prod/$rel" && ! cmp -s "$stage/$rel" "$prod/$rel"; then
      echo "PURCHASE_RELEASE_CONFLICTING_EXISTING_MODULE"
      return 1
    fi
  done
  test -f "$prod/core/apps.py" && test ! -L "$prod/core/apps.py" || return 1
  "$interpreter" -B "$stage/scripts/business_os_patch_app_config.py" --self-test > /dev/null || return 1
  "$interpreter" -B "$stage/scripts/business_os_patch_app_config.py" --check "$prod/core/apps.py" || return 1
  # Verify full application imports *before* changing any live file.
  (cd "$prod" && "$interpreter" -B manage.py check) > /dev/null 2>&1
}
apply() {
  precheck || { echo "PURCHASE_RELEASE_PREFLIGHT_FAILED"; return 1; }
  mkdir -p "$backup/core"
  cp -p "$prod/core/apps.py" "$backup/core/apps.py" || return 1
  for rel in "${files[@]}"; do
    if test -f "$prod/$rel"; then
      mkdir -p "$backup/$(dirname "$rel")"
      cp -p "$prod/$rel" "$backup/$rel" || return 1
    fi
  done
  touch "$backup/armed"
  for rel in "${files[@]}"; do
    install -m 0644 "$stage/$rel" "$prod/$rel" || { echo "PURCHASE_RELEASE_MODULE_INSTALL_FAILED"; return 1; }
  done
  echo "PURCHASE_RELEASE_MODULES_INSTALLED"
  "$interpreter" -B "$stage/scripts/business_os_patch_app_config.py" --apply "$prod/core/apps.py" || { echo "PURCHASE_RELEASE_APPCONFIG_PATCH_FAILED"; return 1; }
  echo "PURCHASE_RELEASE_APPCONFIG_PATCHED"
  if ! (cd "$prod" && "$interpreter" -B manage.py check) > "$stage/django-check-private.log" 2>&1; then
    "$interpreter" -B - "$stage/django-check-private.log" <<'PY'
import pathlib,re,sys
s=pathlib.Path(sys.argv[1]).read_text(encoding="utf-8",errors="replace")
codes=re.findall(r"(?:(?:fields|models|admin|urls|security|auth)\.)[EW]\d{3}",s)
for code in sorted(set(codes))[:5]:
    print("PURCHASE_RELEASE_CHECK_CODE_" + code.replace(".", "_"))
for kind in ("ModuleNotFoundError","ImportError","AttributeError","TypeError","ValueError","RuntimeError","SystemCheckError","ImproperlyConfigured","SyntaxError"):
    if kind in s:
        print("PURCHASE_RELEASE_CHECK_CLASS_" + kind)
m=re.search(r"(?:cannot import name |has no attribute )['\"]([A-Za-z_][A-Za-z_0-9]*)['\"]",s)
if m:
    print("PURCHASE_RELEASE_CHECK_SYMBOL_" + m.group(1))
m=re.search(r"No module named ['\"]([A-Za-z_][A-Za-z_0-9.]*)['\"]",s)
if m and m.group(1).startswith(("core","command_center","config","django")):
    print("PURCHASE_RELEASE_CHECK_MODULE_" + m.group(1).replace(".", "_"))
PY
    echo "PURCHASE_RELEASE_DJANGO_CHECK_FAILED"
    return 1
  fi
  restart || { echo "PURCHASE_RELEASE_PASSENGER_RESTART_FAILED"; return 1; }
  touch "$backup/applied"
  echo "PURCHASE_RELEASE_APPLIED_DJANGO_CHECK_OK"
}
probe() {
  # Rehearse AppConfig.ready and staged imports in memory, leaving live files untouched.
  "$interpreter" -B - "$stage" "$prod" <<'PY'
import os, sys, pathlib, re, traceback
stage, prod = (pathlib.Path(x) for x in sys.argv[1:])
sys.path.insert(0, str(prod))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
try:
    import django
    import core
    core.__path__.insert(0, str(stage / "core"))
    from core.apps import CoreConfig
    def purchase_ready(self):
        from core import purchase_signals
    CoreConfig.ready = purchase_ready
    django.setup()
    from django.core.management import call_command
    call_command("check", verbosity=0, stdout=open(os.devnull, "w"))
    print("PURCHASE_PROBE_DJANGO_READY_AND_CHECK_OK")
except Exception as exc:
    frames = traceback.extract_tb(exc.__traceback__)
    last = frames[-1] if frames else None
    kind = type(exc).__name__
    component = pathlib.Path(last.filename).name if last else "unknown"
    print("PURCHASE_PROBE_ERROR_CLASS_" + re.sub(r"[^A-Za-z]", "", kind))
    print("PURCHASE_PROBE_ERROR_FILE_" + re.sub(r"[^A-Za-z0-9_.]", "", component))
    # Only a Python identifier from an import/attribute exception is disclosed.
    symbol = re.search(r"(?:cannot import name |has no attribute )['\"]([A-Za-z_][A-Za-z_0-9]*)['\"]", str(exc))
    if symbol:
        print("PURCHASE_PROBE_ERROR_SYMBOL_" + symbol.group(1))
    raise SystemExit(1)
PY
}
verify_active() {
  # Inspect only Django's in-process signal registry; do not touch orders.
  "$interpreter" -B - "$prod" <<'PY'
import os,sys
prod=sys.argv[1]
sys.path.insert(0,prod)
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
try:
    import django
    django.setup()
    if "core.purchase_signals" not in sys.modules:
        print("PURCHASE_ACTIVE_SIGNAL_MODULE_NOT_LOADED")
        raise SystemExit(1)
    from django.db.models.signals import post_save
    from core.models import Order, PaymentWebhookEvent
    def subscribed(sender, name):
        callbacks=post_save._live_receivers(sender)
        if isinstance(callbacks,tuple):
            callbacks=list(callbacks[0])+list(callbacks[1])
        return any(getattr(fn,"__name__",None)==name and getattr(fn,"__module__",None)=="core.purchase_signals" for fn in callbacks)
    if not subscribed(Order,"on_paid_order_saved"):
        print("PURCHASE_ACTIVE_ORDER_SIGNAL_ABSENT")
        raise SystemExit(1)
    if not subscribed(PaymentWebhookEvent,"on_processed_payment_receipt"):
        print("PURCHASE_ACTIVE_RECEIPT_SIGNAL_ABSENT")
        raise SystemExit(1)
    print("PURCHASE_ACTIVE_ORDER_AND_RECEIPT_SIGNALS_CONFIRMED")
except Exception:
    print("PURCHASE_ACTIVE_SIGNAL_CHECK_FAILED")
    raise SystemExit(1)
PY
}
case "${1:-}" in
  --probe)
    probe
    ;;
  --verify-active)
    verify_active
    ;;
  --check-app-config)
    "$interpreter" -B "$stage/scripts/business_os_patch_app_config.py" --check "$prod/core/apps.py"
    ;;
  --apply)
    if ! apply; then rollback; exit 1; fi
    ;;
  --rollback)
    rollback
    ;;
  *)
    echo "PURCHASE_RELEASE_USAGE"; exit 85 ;;
esac
