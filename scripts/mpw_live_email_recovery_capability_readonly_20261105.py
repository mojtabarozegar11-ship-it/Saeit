#!/usr/bin/env python3
"""One-shot, read-only MojPlayWin live email-recovery capability inventory.

Inspects only Django model/URL metadata and Python AST. Never reads stored
customer values, emails, private downloads, payment details, or credentials.
No GET/POST requests, network IO, email actions or DB writes.
"""
from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path

ROOT = Path("/home/zomorod2/Saeit-staging")
if not ROOT.is_dir() or ROOT.is_symlink():
    raise RuntimeError("UNEXPECTED_LIVE_RUNTIME_ROOT")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import get_resolver
from django.urls.resolvers import URLPattern, URLResolver

TARGET_MODELS = (
    ("core", "Order"),
    ("core", "OrderItem"),
    ("core", "PaymentIntent"),
    ("mpw_commerce", "CommerceOrder"),
    ("mpw_commerce", "CommerceInvoice"),
    ("mpw_commerce", "CommerceFulfillment"),
    ("mpw_commerce", "CommerceReceipt"),
)
RECOVERY_WORDS = ("recover", "recovery", "restore", "reset", "resend", "email-link")
SOURCE_NAMES = (
    "buyer_orders.py", "customer_auth.py", "downloads.py", "views.py",
    "urls.py", "models.py", "guest_checkout.py", "trx_commercial.py",
    "payment_links.py", "emails.py", "mail.py",
)
MAIL_SEND_NODES = {
    "send_mail", "send_mass_mail", "EmailMessage", "EmailMultiAlternatives",
    "send", "send_messages",
}


def model_shape(model):
    fields = []
    for field in model._meta.fields:
        internal = field.get_internal_type()
        related = getattr(field, "related_model", None)
        fields.append({
            "name": str(field.name)[:60],
            "kind": str(internal)[:45],
            "related_model": str(related._meta.label_lower)[:80] if related else None,
        })
    return {
        "present": True, "field_count": len(fields),
        "fields": fields[:40],
        "email_like_field_count": sum("email" in f["name"].lower() for f in fields),
    }


def source_inventory():
    root = ROOT / "mpw_commerce"
    result = {"directory_exists": root.is_dir() and not root.is_symlink(),
              "inspected_files": 0, "parse_failures": 0,
              "files_with_recovery_named_functions": 0,
              "recovery_named_functions": 0,
              "files_with_mail_send_code_reference": 0}
    if not result["directory_exists"]:
        return result
    for name in SOURCE_NAMES:
        p = root / name
        if not p.is_file() or p.is_symlink():
            continue
        try:
            if p.stat().st_size > 128000:
                result["parse_failures"] += 1
                continue
            tree = ast.parse(p.read_text("utf8"))
            funcs = [n.name.lower() for n in ast.walk(tree)
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            names = [n.id for n in ast.walk(tree) if isinstance(n, ast.Name)]
            attributes = [n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)]
            recovered = sum(any(word in name for word in RECOVERY_WORDS) for name in funcs)
            result["inspected_files"] += 1
            result["recovery_named_functions"] += recovered
            result["files_with_recovery_named_functions"] += int(recovered > 0)
            result["files_with_mail_send_code_reference"] += int(bool(
                MAIL_SEND_NODES.intersection(names + attributes)))
        except (OSError, SyntaxError, UnicodeError, ValueError):
            result["parse_failures"] += 1
    return result


def route_inventory():
    report = {"commerce_routes_examined": 0, "commerce_purchase_routes": [],
              "commerce_recovery_routes": [], "truncated": False}
    visited = 0

    def visit(patterns, prefix="", depth=0):
        nonlocal visited
        if depth > 8:
            report["truncated"] = True
            return
        for item in patterns:
            visited += 1
            if visited > 2000:
                report["truncated"] = True
                return
            path = prefix + str(item.pattern)
            if isinstance(item, URLResolver):
                visit(item.url_patterns, path, depth+1)
            elif isinstance(item, URLPattern):
                low = path.lower()
                if "commerce" not in low and "purchase" not in low:
                    continue
                report["commerce_routes_examined"] += 1
                if any(s in low for s in RECOVERY_WORDS):
                    report["commerce_recovery_routes"].append(path[:120])
                elif any(s in low for s in ("purchases", "download")):
                    report["commerce_purchase_routes"].append(path[:120])
    visit(get_resolver().url_patterns)
    for field in ("commerce_recovery_routes", "commerce_purchase_routes"):
        report[field] = sorted(set(report[field]))[:30]
    return report


def run():
    result = {
        "scope": "production_staging_live_metadata_no_customer_values",
        "customer_email_values_read": False, "mailbox_read": False,
        "emails_sent": 0, "emails_deleted": 0, "database_writes": 0,
        "financial_transactions": 0,
        "models": {},
        "route_inventory": route_inventory(),
        "source_inventory": source_inventory(),
        "smtp_transport": {"non_dummy_backend_configured": False},
    }
    backend = str(getattr(settings, "EMAIL_BACKEND", "")).lower()
    result["smtp_transport"]["non_dummy_backend_configured"] = bool(
        backend and not any(x in backend for x in
            ("console", "dummy", "locmem", "filebased")))
    result["models"]["auth_user"] = model_shape(get_user_model())
    for app, name in TARGET_MODELS:
        try:
            result["models"][app + "." + name] = model_shape(apps.get_model(app, name))
        except LookupError:
            result["models"][app + "." + name] = {"present": False}
    print("MPW_LIVE_EMAIL_RECOVERY_CAPABILITY_READONLY=" +
          json.dumps(result, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    run()
