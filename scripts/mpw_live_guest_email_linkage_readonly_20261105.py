#!/usr/bin/env python3
"""Read-only MojPlayWin checkout email capture and paid-order linkage evidence.

Only aggregate SQL COUNT queries and read-only Django template inspection.
No customer email values leave the database; no orders are created or changed.
No SMTP, payments, private downloads, messages, or file writes.
"""
from __future__ import annotations
from html.parser import HTMLParser
from pathlib import Path
import json
import os
import sys

ROOT = Path("/home/zomorod2/Saeit-staging")
if not ROOT.is_dir() or ROOT.is_symlink():
    raise RuntimeError("UNEXPECTED_LIVE_RUNTIME_ROOT")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.contrib.auth import get_user_model
from django.template.loader import get_template
from core.models import PaymentIntent

class FormInspector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.email_inputs = 0
        self.nonhidden_email_inputs = 0
        self.forms = 0
        self.post_forms = 0

    def handle_starttag(self, tag, attrs):
        props = dict(attrs)
        if tag == "form":
            self.forms += 1
            self.post_forms += int(str(props.get("method", "")).lower() == "post")
        if tag != "input":
            return
        if str(props.get("name", "")).lower() not in (
            "email", "buyer_email", "customer_email", "purchase_email"
        ):
            return
        self.email_inputs += 1
        self.nonhidden_email_inputs += int(
            str(props.get("type", "text")).lower() != "hidden"
        )


def template_evidence():
    report = {"found": False, "source_local": False, "forms": None,
              "post_forms": None, "named_email_inputs": None,
              "visible_named_email_inputs": None}
    try:
        template = get_template("mpw_commerce/product_checkout.html")
        origin = getattr(template, "origin", None)
        raw_path = Path(str(getattr(origin, "name", "")))
        if (not raw_path.is_file() or raw_path.is_symlink()
                or not raw_path.resolve().is_relative_to(ROOT.resolve())
                or raw_path.stat().st_size > 120000):
            return report
        report["found"] = True
        report["source_local"] = True
        inspector = FormInspector()
        inspector.feed(raw_path.read_text(encoding="utf8"))
        report["forms"] = inspector.forms
        report["post_forms"] = inspector.post_forms
        report["named_email_inputs"] = inspector.email_inputs
        report["visible_named_email_inputs"] = inspector.nonhidden_email_inputs
    except (OSError, UnicodeError, ValueError, SyntaxError):
        pass
    return report


def aggregate_linkage():
    paid = PaymentIntent.objects.filter(
        status__iexact="paid", provider="mpw_walletless_trx_v1"
    )
    email_lookup = "order__customer__email"
    nonempty = paid.exclude(**{email_lookup: ""}).filter(
        **{email_lookup + "__isnull": False}
    )
    customers = get_user_model()
    username_name = str(customers.USERNAME_FIELD)
    guest_lookup = {username_name + "__startswith": "mpwguest_"}
    guests = customers.objects.filter(**guest_lookup)
    guest_with_email = guests.exclude(email="").filter(email__isnull=False)
    return {
        "paid_walletless_intents": paid.count(),
        "paid_walletless_with_customer_email": nonempty.count(),
        "paid_walletless_with_nonplaceholder_email": nonempty.exclude(
            **{email_lookup + "__endswith": "@guest.mojplaywin.com"}
        ).count(),
        "guest_accounts": guests.count(),
        "guest_accounts_with_nonempty_email": guest_with_email.count(),
        "guest_accounts_with_nonplaceholder_email": guest_with_email.exclude(
            email__endswith="@guest.mojplaywin.com"
        ).count(),
    }


def main():
    report = {
        "scope": "live_aggregate_counts_and_checkout_form_structure",
        "customer_values_returned_to_python": False,
        "email_addresses_logged": False,
        "emails_sent": 0, "emails_deleted": 0,
        "database_writes": 0, "payment_transactions": 0,
        "template": template_evidence(),
        "counts": aggregate_linkage(),
    }
    print("MPW_GUEST_EMAIL_LINKAGE_READONLY=" + json.dumps(
        report, sort_keys=True, ensure_ascii=False
    ))


if __name__ == "__main__":
    main()
