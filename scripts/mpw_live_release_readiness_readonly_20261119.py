"""Boolean-only store release diagnostic; no customer rows or payment mutations."""
import json
import os
from pathlib import Path
import sys

ROOT = Path("/home/zomorod2/Saeit-staging")
FLAGS = (
    "MPW_COMMERCE_RELEASE_READY", "MPW_COMMERCE_DOWNLOADS_ENABLED",
    "MPW_WALLETLESS_TRX_PUBLIC_ENABLED", "MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED",
    "MPW_TRX_SOLIDITY_RELEASE_VERIFIED", "MPW_TRX_BACKGROUND_RECONCILE_ENABLED",
    "MPW_GUEST_RECOVERY_ENABLED", "MPW_GUEST_RECOVERY_EMAIL_APPROVED",
    "MPW_GUEST_EMAIL_SEND_APPROVED",
)
MODELS = (
    ("core", "PaymentIntent"), ("core", "LedgerEntry"),
    ("core", "GuestOrderEmail"), ("core", "GuestRecoveryToken"),
    ("core", "GuestRecoveryRate"), ("mpw_commerce", "CommerceFulfillment"),
    ("mpw_commerce", "CommerceInvoice"),
)
ROUTES = {
    "shop": "/commerce/trx-easy/",
    "checkout": "/commerce/book/1/",
    "start": "/commerce/trx-easy/start/1/",
    "status": "/commerce/trx-easy/status/1/",
    "reconcile": "/commerce/trx-easy/reconcile/1/",
    "download": "/commerce/trx-easy/download/1/",
    "recovery": "/commerce/trx-easy/recover/",
    "verify": "/commerce/trx-easy/recover/verify/",
}


def inspect():
    report = {"read_only": True, "runtime_ready": False, "flags": {},
              "routes": {}, "schema": {}, "mysql_backend": False,
              "smtp_configured": False, "private_asset_root_configured": False,
              "product_allowlist_configured": False, "public_worker_proven": False,
              "payment_finality_proven": False, "release_authorized": False}
    if not ROOT.is_dir() or ROOT.is_symlink():
        return report
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        import django
        django.setup()
        from django.apps import apps
        from django.conf import settings
        from django.db import connection
        from django.urls import resolve, Resolver404
        report["runtime_ready"] = True
        report["flags"] = {key: getattr(settings, key, False) is True for key in FLAGS}
        report["mysql_backend"] = connection.vendor == "mysql"
        report["smtp_configured"] = (
            str(getattr(settings, "EMAIL_BACKEND", "")).endswith(".smtp.EmailBackend")
            and bool(getattr(settings, "EMAIL_HOST", ""))
            and bool(getattr(settings, "DEFAULT_FROM_EMAIL", ""))
        )
        asset_root = getattr(settings, "MPW_COMMERCE_PRIVATE_ASSET_ROOT", "")
        report["private_asset_root_configured"] = (
            isinstance(asset_root, str) and asset_root.startswith("/")
            and Path(asset_root).is_dir() and not Path(asset_root).is_symlink()
        )
        report["product_allowlist_configured"] = bool(
            getattr(settings, "MPW_TRX_PUBLIC_PRODUCT_IDS", ())
        )
        for key, path in ROUTES.items():
            try:
                match = resolve(path)
                module = getattr(match.func, "__module__", "")
                report["routes"][key] = {
                    "resolved": True, "mpw_handler": module.startswith("services.mpw_")
                }
            except Resolver404:
                report["routes"][key] = {"resolved": False, "mpw_handler": False}
        tables = set(connection.introspection.table_names())
        for app, name in MODELS:
            key = app + "." + name
            try:
                model = apps.get_model(app, name)
                table = model._meta.db_table
                if table not in tables:
                    report["schema"][key] = "table_missing"
                    continue
                with connection.cursor() as cursor:
                    existing = {col.name for col in connection.introspection.get_table_description(cursor, table)}
                required = {f.column for f in model._meta.local_concrete_fields}
                report["schema"][key] = "columns_present" if required <= existing else "columns_missing"
            except LookupError:
                report["schema"][key] = "model_missing"
    except Exception as exc:
        report["error_type"] = type(exc).__name__
    return report


if __name__ == "__main__":
    print("MPW_RELEASE_READONLY=" + json.dumps(inspect(), sort_keys=True))
