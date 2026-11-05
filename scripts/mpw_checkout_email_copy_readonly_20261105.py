#!/usr/bin/env python3
"""Read-only, privacy-safe inventory of MojPlayWin's email delivery promises."""
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import sys


APP = Path("/home/zomorod2/Saeit-staging")
WATCH = ("email", "invoice", "receipt", "download")


def _call_name(expr):
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        return expr.attr
    return ""


def _commercial_flow_inventory():
    """Report only static function/call names; never source literals or credentials."""
    files = (
        "services/mpw_trx_guest_delivery.py",
        "services/mpw_trx_commercial_web.py",
        "services/mpw_walletless_commercial_intent.py",
    )
    selected_calls = {
        "EmailMessage", "get_connection", "send", "send_messages", "send_mail",
        "record_invoice", "require_active_merchant_wallet", "on_commit",
        "deliver", "deliver_paid", "_download_paid", "mark_paid",
        "create", "get_or_create", "update_or_create", "save", "filter",
    }
    result = []
    for relative in files:
        path = APP / relative
        if (path.is_symlink() or not path.is_file() or
                not path.resolve().is_relative_to(APP.resolve()) or
                path.stat().st_size > 140000):
            result.append({"path": relative, "status": "unavailable"})
            continue
        raw = path.read_bytes()
        tree = ast.parse(raw.decode("utf-8"), filename=relative)
        functions = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                calls = sorted({name for call in ast.walk(node)
                                if isinstance(call, ast.Call)
                                if (name := _call_name(call.func)) in selected_calls})
                functions.append({"name": node.name, "line": node.lineno,
                                  "calls": calls})
        result.append({"path": relative, "sha256": hashlib.sha256(raw).hexdigest(),
                       "functions": functions[:65]})
    return result


def _commercial_delivery_aggregate():
    """Read aggregate counts only; no addresses, order IDs, or message bodies."""
    from django.apps import apps
    try:
        model = apps.get_model("mpw_commerce", "GuestTrxDelivery")
    except LookupError:
        return {"model_available": False}
    fields = model._meta.concrete_fields
    safe = {field.name: field for field in fields
            if field.name in ("sent_at", "delivered_at", "email_sent_at",
                              "fulfilled_at", "created_at", "last_attempt_at")}
    try:
        aggregate = {"total_rows": model.objects.count()}
        for name in sorted(safe):
            aggregate[name + "_nonnull"] = model.objects.filter(
                **{name + "__isnull": False}).count()
        return {"model_available": True, "aggregate": aggregate,
                "time_fields_checked": sorted(safe)}
    except Exception as exc:
        return {"model_available": True,
                "query_status": type(exc).__name__}


def main():
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2" or APP.is_symlink() or not APP.is_dir():
        raise RuntimeError("MPW_COPY_AUDIT_WRONG_HOST")
    sys.path.insert(0, str(APP))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.template.loader import get_template
    from django.conf import settings
    rendered = get_template("mpw_commerce/product_checkout.html")
    checkout = Path(rendered.origin.name)
    if not checkout.resolve().is_relative_to(APP.resolve()):
        raise RuntimeError("MPW_COPY_AUDIT_EXTERNAL_TEMPLATE")

    candidates = {
        checkout,
        *(APP / "services").glob("mpw_trx_*.py"),
        *(APP / "services").glob("mpw_*commerce*.py"),
    }
    findings = []
    for path in sorted(candidates):
        if (path.is_symlink() or not path.is_file() or
                not path.resolve().is_relative_to(APP.resolve()) or
                path.stat().st_size > 130000):
            continue
        source = path.read_text("utf-8", "replace")
        matches = []
        for number, line in enumerate(source.splitlines(), 1):
            lowered = line.lower()
            if ("email" in lowered and any(term in lowered for term in WATCH[1:])
                    or "email my invoice" in lowered):
                # Source-only public display strings; no DB rows or mailboxes.
                matches.append({"line": number,
                                "literal": re.sub(r"\s+", " ", line).strip()[:170]})
        if matches:
            findings.append({"path": str(path.relative_to(APP)),
                             "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                             "matches": matches[:20]})
    delivery_source = APP / "services/mpw_trx_guest_delivery.py"
    delivery_checks = []
    if delivery_source.is_file() and not delivery_source.is_symlink():
        for number, line in enumerate(delivery_source.read_text("utf-8", "replace").splitlines(), 1):
            lowered = line.lower()
            if ("mpw_" in lowered or "send_mail" in lowered or "emailmessage" in lowered
                    or "send_messages" in lowered or "deliver" in lowered and
                    ("def " in lowered or "enabled" in lowered)):
                if not any(term in lowered for term in ("password", "secret", "private_key", "token=")):
                    delivery_checks.append({"line": number, "source": line.strip()[:210]})
    triggers = []
    for path in (APP / "services").glob("*.py"):
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 140000:
            continue
        if path.name == "mpw_trx_guest_delivery.py":
            continue
        for number, line in enumerate(path.read_text("utf-8", "replace").splitlines(), 1):
            if "mpw_trx_guest_delivery" in line:
                triggers.append({"path": str(path.relative_to(APP)), "line": number,
                                 "source": line.strip()[:170]})
    flags = {}
    for name in dir(settings):
        if name.startswith("MPW_") and any(t in name for t in ("EMAIL", "MAIL", "DELIVERY")):
            value = getattr(settings, name)
            if type(value) is bool:
                flags[name] = value
    backend = getattr(settings, "EMAIL_BACKEND", None)
    backend_type = backend if isinstance(backend, str) and (
        backend.startswith("django.core.mail.backends.") or
        backend.startswith("anymail.backends.")) else "custom_or_unavailable"
    print("MPW_CHECKOUT_EMAIL_COPY_READONLY=" + json.dumps({
        "checkout_template": str(checkout.relative_to(APP)),
        "found": findings[:12],
        "delivery_source_controls": delivery_checks[:55],
        "delivery_module_references": triggers[:20],
        "boolean_mail_delivery_flags": flags,
        "commercial_email_backend_type": backend_type,
        "commercial_flow_static": _commercial_flow_inventory(),
        "commercial_delivery_aggregate": _commercial_delivery_aggregate(),
        "emails_sent_by_audit": 0, "emails_deleted": 0,
        "files_modified": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
