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
import subprocess
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
    field_names = {field.name for field in fields}
    safe = {field.name: field for field in fields
            if field.name in ("sent_at", "delivered_at", "email_sent_at",
                              "fulfilled_at", "created_at", "last_attempt_at")}
    try:
        aggregate = {"total_rows": model.objects.count()}
        for name in sorted(safe):
            aggregate[name + "_nonnull"] = model.objects.filter(
                **{name + "__isnull": False}).count()
        from django.db.models import Count, Sum
        for name in ("invoice_state", "receipt_state"):
            if name in field_names:
                states = list(model.objects.values(name).annotate(n=Count("pk")).order_by(name))
                aggregate[name + "_counts"] = [
                    {"state": (str(item[name]) if str(item[name]) in (
                        "pending", "failed", "sent", "delivered", "skipped",
                        "complete", "completed", "sending", "queued") else "other"),
                     "count": int(item["n"])}
                    for item in states[:15]
                ]
        for name in ("invoice_attempts", "receipt_attempts"):
            if name in field_names:
                aggregate[name + "_total"] = model.objects.aggregate(
                    total=Sum(name))["total"] or 0
        return {"model_available": True, "aggregate": aggregate,
                "time_fields_checked": sorted(safe),
                "delivery_state_fields": sorted(field_names.intersection({
                    "invoice_state", "receipt_state", "invoice_attempts",
                    "receipt_attempts", "last_error", "last_error_at",
                    "invoice_sent_at", "receipt_sent_at"}))}
    except Exception as exc:
        return {"model_available": True,
                "query_status": type(exc).__name__}


def _receipt_settlement_correlation_readonly():
    """Cross-tab mail receipts with locally verified paid intents; no identifiers logged."""
    try:
        from mpw_commerce.models import GuestTrxDelivery
        from core.models import PaymentIntent
        from core.crown_tron_receipts import PROVIDER, verified_walletless_credit
        rows = list(GuestTrxDelivery.objects.select_related("order").order_by("pk")[:11])
        if len(rows) > 10:
            return {"status": "scope_exceeded", "rows_examined": 0}
        counts = {
            "verified_paid_receipt_sent": 0,
            "verified_paid_receipt_pending": 0,
            "verified_paid_receipt_other": 0,
            "not_verified_paid_receipt_sent": 0,
            "not_verified_paid_receipt_pending": 0,
            "not_verified_paid_receipt_other": 0,
        }
        for row in rows:
            order = row.order
            intents = list(PaymentIntent.objects.filter(
                provider=PROVIDER, order=order, status="paid").order_by("pk")[:2])
            verified = (len(intents) == 1 and
                        verified_walletless_credit(order, intents[0]))
            group = "verified_paid" if verified else "not_verified_paid"
            state = str(row.receipt_state)
            label = "sent" if state == "sent" else (
                "pending" if state == "pending" else "other")
            counts[group + "_receipt_" + label] += 1
        return {"status": "ok", "rows_examined": len(rows), "counts": counts,
                "independent_mainnet_recheck_performed": False}
    except Exception as exc:
        return {"status": "unavailable", "error_type": type(exc).__name__}


def _outbox_scheduler_readonly():
    refs = []
    roots = (APP / "services", APP / "core/management/commands", APP / "scripts")
    for root in roots:
        if not root.is_dir() or root.is_symlink():
            continue
        for path in root.glob("*.py"):
            if (path.is_symlink() or not path.is_file() or
                    not path.resolve().is_relative_to(APP.resolve()) or
                    path.stat().st_size > 140000):
                continue
            if path.name == "mpw_trx_guest_delivery.py":
                continue
            for i, line in enumerate(path.read_text("utf-8", "replace").splitlines(), 1):
                if "flush_outbox" in line:
                    refs.append({"path": str(path.relative_to(APP)), "line": i})
    cron = None
    try:
        cron = subprocess.run(["crontab", "-l"], capture_output=True,
                              text=True, timeout=5, check=False)
        schedule = ("configured" if cron.returncode == 0 and
                    "flush_outbox" in cron.stdout else "not_found_or_unavailable")
    except (OSError, subprocess.TimeoutExpired):
        schedule = "not_found_or_unavailable"
    cron_reconcile = (cron is not None and cron.returncode == 0 and
                      "mpw_trx_commercial_reconcile_cron" in cron.stdout)
    return {"python_callsite_references": refs[:30],
            "cpanel_user_crontab_flush_outbox": schedule,
            "cpanel_user_crontab_reconcile_script": bool(cron_reconcile),
            "cpanel_user_crontab_accessible": cron is not None and cron.returncode == 0}



def _paid_download_path_static_readonly():
    """Sanitized control-flow evidence from deployed paid download code."""
    specs = {
        "services/mpw_trx_commercial_web.py": ("_download_paid", "_reconcile_invoice"),
        "services/mpw_walletless_commercial_intent.py": (
            "open_commercial_paid_file", "commercial_buyer_status", "_paid_read_db"),
        "services/mpw_trx_guest_delivery.py": ("magic_link", "redeem_token", "_send_one"),
    }

    class RedactConstants(ast.NodeTransformer):
        def visit_Constant(self, node):
            if node.value is None or type(node.value) is bool:
                return node
            return ast.copy_location(ast.Constant(value="<literal>"), node)

    out = []
    for relative, wanted in specs.items():
        path = APP / relative
        if (path.is_symlink() or not path.is_file() or
                not path.resolve().is_relative_to(APP.resolve()) or
                path.stat().st_size > 140000):
            out.append({"path": relative, "status": "unavailable"})
            continue
        tree = ast.parse(path.read_text("utf-8"), filename=relative)
        functions = []
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name not in wanted:
                continue
            calls = sorted({name for n in ast.walk(node) if isinstance(n, ast.Call)
                            if (name := _call_name(n.func))})[:60]
            conditions = []
            for n in ast.walk(node):
                if isinstance(n, (ast.If, ast.IfExp, ast.While)) and len(conditions) < 20:
                    safe_test = RedactConstants().visit(ast.fix_missing_locations(
                        ast.parse(ast.unparse(n.test), mode="eval"))).body
                    conditions.append(ast.unparse(safe_test)[:240])
            exception_count = sum(isinstance(n, ast.Raise) for n in ast.walk(node))
            functions.append({"name": node.name, "line": node.lineno,
                              "calls": calls, "conditions_redacted": conditions,
                              "explicit_raises": exception_count})
        out.append({"path": relative, "functions": functions})
    return out


def _paid_order_delivery_linkage_readonly():
    """Aggregate existing paid-order receipt linkage, without URLs or buyer identifiers."""
    try:
        from core.models import PaymentIntent
        from core.crown_tron_receipts import PROVIDER, verified_walletless_credit
        from mpw_commerce.models import GuestTrxDelivery
        intents = list(PaymentIntent.objects.filter(provider=PROVIDER, status="paid")
                       .select_related("order").order_by("pk")[:11])
        if len(intents) > 10:
            return {"status": "scope_exceeded"}
        counters = {"paid_intents": len(intents), "locally_verified": 0,
                    "verified_with_delivery_row": 0, "verified_without_delivery_row": 0,
                    "verified_with_receipt_sent": 0, "verified_with_receipt_pending": 0,
                    "verified_with_receipt_other": 0}
        for intent in intents:
            if not verified_walletless_credit(intent.order, intent):
                continue
            counters["locally_verified"] += 1
            delivery = list(GuestTrxDelivery.objects.filter(order=intent.order)[:2])
            if len(delivery) != 1:
                counters["verified_without_delivery_row"] += 1
                continue
            counters["verified_with_delivery_row"] += 1
            label = str(delivery[0].receipt_state)
            bucket = label if label in ("sent", "pending") else "other"
            counters["verified_with_receipt_" + bucket] += 1
        return {"status": "ok", "counts": counters,
                "file_open_attempted": False, "download_link_redeemed": False,
                "remote_chain_recheck": False}
    except Exception as exc:
        return {"status": "unavailable", "error_type": type(exc).__name__}


def _commerce_model_file_schema_readonly():
    """List model/field *types only*; no product names, paths or records."""
    try:
        from django.apps import apps
        models = []
        for model in apps.get_app_config("mpw_commerce").get_models():
            if any(t in model.__name__.lower() for t in
                   ("book", "product", "order", "delivery", "asset", "file")):
                fields = [{"name": f.name, "type": f.get_internal_type()}
                          for f in model._meta.get_fields()
                          if getattr(f, "concrete", False)
                          if f.get_internal_type() in
                          ("FileField", "ImageField", "ForeignKey", "OneToOneField")]
                models.append({"model": model.__name__, "fields": fields[:18]})
        return {"status": "ok", "models": models[:30]}
    except Exception as exc:
        return {"status": "unavailable", "error_type": type(exc).__name__}



def _existing_paid_download_readiness_readonly():
    """Call only the deployed DB/file-existence status gate; do not open paid file."""
    try:
        import inspect
        from core.models import PaymentIntent
        from core.crown_tron_receipts import PROVIDER, verified_walletless_credit
        from services import mpw_walletless_commercial_intent as commercial

        root = APP / "services/mpw_walletless_commercial_intent.py"
        if (root.is_symlink() or not root.is_file() or
                root.stat().st_size > 140000 or
                not root.resolve().is_relative_to(APP.resolve())):
            return {"status": "source_guard_failed"}
        tree = ast.parse(root.read_text("utf-8"), filename=root.name)
        func = next((n for n in tree.body if isinstance(n, ast.FunctionDef)
                     and n.name == "commercial_buyer_status"), None)
        if func is None:
            return {"status": "status_gate_not_found"}
        calls = {_call_name(n.func) for n in ast.walk(func) if isinstance(n, ast.Call)}
        disallowed = {"save", "delete", "update", "create", "bulk_create", "send",
                      "send_mail", "send_messages", "post", "put", "patch",
                      "commit", "open", "write", "touch", "mkdir",
                      "reconcile_commercial_intent_from_candidates"}
        if calls.intersection(disallowed):
            return {"status": "status_gate_not_readonly"}
        sig = inspect.signature(commercial.commercial_buyer_status)
        arguments = list(sig.parameters)
        if not {"intent_id", "buyer_id"}.issubset(set(arguments)):
            return {"status": "unknown_status_gate_signature",
                    "argument_names": arguments[:8]}
        try:
            sig.bind(intent_id=1, buyer_id=1)
        except TypeError:
            return {"status": "status_gate_requires_additional_arguments",
                    "argument_names": arguments[:8]}
        # Derive the exact acceptance key from the deployed file-open guard.
        # This avoids assuming a return schema or exposing its payload values.
        opener = next((n for n in tree.body if isinstance(n, ast.FunctionDef)
                       and n.name == "open_commercial_paid_file"), None)
        if opener is None:
            return {"status": "file_open_guard_missing"}
        acceptance_keys = set()
        for node in ast.walk(opener):
            if not isinstance(node, ast.Compare) or len(node.ops) != 1:
                continue
            if not isinstance(node.ops[0], ast.IsNot) or len(node.comparators) != 1:
                continue
            comparator = node.comparators[0]
            if not (isinstance(comparator, ast.Constant) and comparator.value is True):
                continue
            call = node.left
            if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "get" and
                    isinstance(call.func.value, ast.Name) and
                    call.func.value.id == "state" and len(call.args) == 1 and
                    isinstance(call.args[0], ast.Constant) and
                    isinstance(call.args[0].value, str)):
                key = call.args[0].value
                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,39}", key):
                    acceptance_keys.add(key)
        if len(acceptance_keys) != 1:
            return {"status": "ambiguous_file_open_guard",
                    "safe_key_count": len(acceptance_keys)}
        acceptance_key = next(iter(acceptance_keys))
        intents = list(PaymentIntent.objects.filter(provider=PROVIDER, status="paid")
                       .select_related("order").order_by("pk")[:11])
        if len(intents) > 10:
            return {"status": "scope_exceeded"}
        totals = {"verified_paid_checked": 0, "guard_true": 0, "guard_false": 0,
                  "unavailable_status": 0, "invalid_buyer_relation": 0,
                  "state_exceptions": 0}
        result_kinds = {}
        safe_state_keys = set()
        for intent in intents:
            if not verified_walletless_credit(intent.order, intent):
                continue
            buyer_id = getattr(intent.order, "customer_id", None)
            if type(buyer_id) is not int:
                totals["invalid_buyer_relation"] += 1
                continue
            totals["verified_paid_checked"] += 1
            try:
                state = commercial.commercial_buyer_status(intent_id=intent.pk, buyer_id=buyer_id)
                kind = type(state).__name__
                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,39}", kind):
                    result_kinds[kind] = result_kinds.get(kind, 0) + 1
                if isinstance(state, dict):
                    for field_name in state.keys():
                        if (isinstance(field_name, str) and
                                re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,39}", field_name) and
                                not any(t in field_name.lower() for t in
                                        ("token", "email", "address", "wallet", "private", "secret", "key", "hash", "url"))):
                            safe_state_keys.add(field_name)
                if not isinstance(state, dict) or type(state.get(acceptance_key)) is not bool:
                    totals["unavailable_status"] += 1
                elif state[acceptance_key]:
                    totals["guard_true"] += 1
                else:
                    totals["guard_false"] += 1
            except Exception:
                totals["state_exceptions"] += 1
        return {"status": "ok", "counts": totals,
                "acceptance_key": acceptance_key,
                "status_return_kinds": result_kinds,
                "safe_status_field_names": sorted(safe_state_keys)[:30],
                "paid_file_opened": False,
                "email_sent": False, "blockchain_transaction": False,
                "scope": "existing_local_paid_intents_only"}
    except Exception as exc:
        return {"status": "unavailable", "error_type": type(exc).__name__}




def _guest_email_claim_coverage_readonly():
    """Count only bound email ownership claims, without retrieving addresses or links."""
    try:
        from datetime import datetime, timedelta, timezone as dt_timezone
        from django.conf import settings
        from django.utils import timezone
        from core.models import GuestOrderEmail, Order
        from core.models import PaymentIntent
        from core.crown_tron_receipts import PROVIDER, verified_walletless_credit

        orders = list(Order.objects.filter(
            customer__username__startswith="mpwguest_"
        ).select_related("customer").order_by("pk")[:301])
        if len(orders) > 300:
            return {"status": "scope_exceeded", "guest_order_count": "over_300"}
        order_ids = {order.pk for order in orders}
        claimed_ids = set(GuestOrderEmail.objects.filter(
            order_id__in=order_ids).values_list("order_id", flat=True))
        recent = timezone.now() - timedelta(hours=24)
        recent_orders = {order.pk for order in orders if order.created_at >= recent}
        # Audited release finished 2026-11-05 18:26:32 UTC (run 42084151853).
        # Start 28 seconds later to exclude racing old in-flight checkouts.
        after_live_capture = datetime(2026, 11, 5, 18, 27, tzinfo=dt_timezone.utc)
        post_release_orders = {order.pk for order in orders
                               if order.created_at >= after_live_capture}
        paid = list(PaymentIntent.objects.filter(
            provider=PROVIDER, status="paid", order_id__in=order_ids
        ).select_related("order").order_by("pk")[:301])
        if len(paid) > 300:
            return {"status": "paid_scope_exceeded"}
        verified_ids = {intent.order_id for intent in paid
                        if verified_walletless_credit(intent.order, intent)}
        return {
            "status": "ok",
            "capture_enabled": getattr(
                settings, "MPW_GUEST_EMAIL_CLAIM_CAPTURE_ENABLED", False) is True,
            "public_recovery_enabled": getattr(
                settings, "MPW_GUEST_RECOVERY_ENABLED", False) is True,
            "outbound_recovery_email_approved": getattr(
                settings, "MPW_GUEST_RECOVERY_EMAIL_APPROVED", False) is True,
            "guest_orders": len(order_ids),
            "guest_orders_with_claim": len(order_ids & claimed_ids),
            "guest_orders_without_claim": len(order_ids - claimed_ids),
            "last_24h_guest_orders": len(recent_orders),
            "last_24h_guest_orders_with_claim": len(recent_orders & claimed_ids),
            "last_24h_guest_orders_without_claim": len(recent_orders - claimed_ids),
            "guest_orders_after_release_cutover": len(post_release_orders),
            "after_release_with_claim": len(post_release_orders & claimed_ids),
            "after_release_without_claim": len(post_release_orders - claimed_ids),
            "locally_verified_paid_guest_orders": len(verified_ids),
            "locally_verified_paid_guest_orders_with_claim": len(verified_ids & claimed_ids),
            "locally_verified_paid_guest_orders_without_claim": len(verified_ids - claimed_ids),
            "total_claim_rows": GuestOrderEmail.objects.count(),
            "historical_orders_backfilled": False,
            "checkout_or_email_sent_by_audit": False,
        }
    except Exception as exc:
        return {"status": "unavailable", "error_type": type(exc).__name__}


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
        "commercial_outbox_scheduler": _outbox_scheduler_readonly(),
        "receipt_settlement_cross_tab": _receipt_settlement_correlation_readonly(),
        "paid_download_path_static": _paid_download_path_static_readonly(),
        "paid_order_delivery_linkage": _paid_order_delivery_linkage_readonly(),
        "commerce_file_schema": _commerce_model_file_schema_readonly(),
        "existing_paid_download_readiness": _existing_paid_download_readiness_readonly(),
        "guest_email_claim_coverage": _guest_email_claim_coverage_readonly(),
        "emails_sent_by_audit": 0, "emails_deleted": 0,
        "files_modified": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
