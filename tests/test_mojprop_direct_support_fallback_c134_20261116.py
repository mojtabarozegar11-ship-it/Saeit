"""Moj Prop no-cost, no-auto-send fallback when live intake HTML is degraded.

Offline stdlib-only source tests; no network, provider access, customer data,
messages, payments, backup operations or production changes.
"""
from __future__ import annotations

import ast
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit
import unittest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = (
    ROOT / "templates/moj-prop-v4/index.html",
    ROOT / "templates/moj-prop-v4/starter-30-trx/index.html",
    ROOT / "templates/moj-prop-v4/catalog/index.html",
)
OWNER_MAILBOX = "mojplaywin@gmail.com"
STARTER_SUBJECT = "MOJPROP-STARTER30 / Educational assessment / Written terms"
HOMEPAGE_SUBJECT = "Moj Prop service inquiry"


class EmailLinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            link = dict(attrs).get("href", "")
            if link.lower().startswith("mailto:"):
                self.links.append(link)


def email_link(path: Path):
    page = path.read_text(encoding="utf-8")
    doc = EmailLinkParser()
    doc.feed(page)
    doc.close()
    if len(doc.links) != 1:
        raise AssertionError("exactly one manual support email link required: " + str(path))
    uri = urlsplit(doc.links[0])
    if uri.scheme.lower() != "mailto":
        raise AssertionError("mail channel was unexpectedly replaced")
    return page, uri


class ManualEmailFallbackContract(unittest.TestCase):
    def test_each_public_commercial_page_has_manual_fallback(self):
        for template in TEMPLATES:
            with self.subTest(template=template.name):
                page, _ = email_link(template)
                self.assertIn(OWNER_MAILBOX, page)
                self.assertIn("mailto:", page)

    def test_mailto_recipient_is_the_connected_mojplaywin_owner_inbox(self):
        for template in TEMPLATES:
            with self.subTest(template=template.name):
                _, uri = email_link(template)
                self.assertEqual(uri.path.lower(), OWNER_MAILBOX)
                self.assertEqual(uri.fragment, "")

    def test_mailto_has_only_approved_nonpersonal_subject(self):
        for template in TEMPLATES:
            with self.subTest(template=template.name):
                _, uri = email_link(template)
                params = parse_qs(uri.query, keep_blank_values=True)
                self.assertEqual(set(params), {"subject"})
                expected = (HOMEPAGE_SUBJECT if template.name == "index.html" and
                            template.parent.name == "moj-prop-v4"
                            else STARTER_SUBJECT)
                self.assertEqual(params["subject"], [expected])

    def test_mailto_has_no_buyer_data_or_secrets(self):
        for template in TEMPLATES:
            with self.subTest(template=template.name):
                _, uri = email_link(template)
                query = unquote(uri.query).lower()
                self.assertNotIn("body=", query)
                self.assertNotIn("bcc=", query)
                self.assertNotIn("cc=", query)
                self.assertNotIn("receipt_token", query)
                self.assertNotIn("csrf", query)
                self.assertNotIn("private key", query)
                self.assertNotIn("%0a", uri.query.lower())
                self.assertNotIn("%0d", uri.query.lower())

    def test_link_is_a_user_initiated_anchor_not_an_automatic_send(self):
        for template in TEMPLATES:
            with self.subTest(template=template.name):
                page, _ = email_link(template)
                self.assertNotIn('location.href="mailto:', page)
                self.assertNotIn("fetch('mailto:", page)
                self.assertNotIn('form action="mailto:', page)

    def test_fallback_never_claims_to_create_a_paid_order_or_crm_receipt(self):
        home, _ = email_link(TEMPLATES[0])
        self.assertIn("not a CRM request, order, receipt, payment", home)
        starter, _ = email_link(TEMPLATES[1])
        self.assertIn("does not send automatically, allocate a CRM request ID", starter)
        catalog, _ = email_link(TEMPLATES[2])
        self.assertIn("Email enquiries do not issue CRM receipts", catalog)

    def test_no_wallet_or_paid_checkout_added(self):
        for template in TEMPLATES:
            with self.subTest(template=template.name):
                page, _ = email_link(template)
                self.assertNotIn("tronWeb.trx.sendTransaction", page)
                self.assertNotIn("payment?recipient=", page)
                self.assertNotIn("window.tronLink.request", page)

    def test_existing_native_request_routes_are_preserved(self):
        for template in TEMPLATES:
            with self.subTest(template=template.name):
                page, _ = email_link(template)
                self.assertIn("moj-prop-intake/?format=html", page)
        home, _ = email_link(TEMPLATES[0])
        self.assertIn('id="request-form"', home)
        self.assertIn('id="status-form"', home)

    def test_owner_email_is_not_substituted_into_client_side_pii_draft(self):
        home, _ = email_link(TEMPLATES[0])
        self.assertNotIn("body:encodeURIComponent(", home)
        self.assertNotIn("mailto:"+OWNER_MAILBOX+"?body=", home)

    def test_no_unsupported_zero_javascript_claim_for_email_fallback(self):
        home, _ = email_link(TEMPLATES[0])
        self.assertIn("a separate <strong>manual email enquiry</strong>", home)
        self.assertIn("<noscript>", home)

    def test_exact_static_release_inventory_covers_all_changed_pages(self):
        script = (ROOT / "scripts/update_mojplaywin_moj_prop_catalog.py").read_text("utf-8")
        tree = ast.parse(script)
        target = next(
            node.value for node in tree.body
            if isinstance(node, ast.Assign) and any(
                isinstance(item, ast.Name) and item.id == "HTML_FILES"
                for item in node.targets
            )
        )
        names = {
            ast.literal_eval(element.args[0])
            for element in target.elts
            if isinstance(element, ast.Call) and
            isinstance(element.func, ast.Name) and element.func.id == "Path"
        }
        self.assertTrue({
            "index.html", "catalog/index.html", "starter-30-trx/index.html"
        }.issubset(names))
        self.assertIn("PRESERVED_LIVE_FILES = (Path(\"signals/index.html\"),)", script)


if __name__ == "__main__":
    unittest.main()
