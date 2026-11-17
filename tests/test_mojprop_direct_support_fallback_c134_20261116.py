"""Fail-closed support continuity without inventing a second buyer inbox.

The verified public Moj Prop contact template names the already published
support@mojplaywin.com address. The v4 sales surfaces should only link to
that first-party page, not substitute another email or auto-send anything.
Source-only offline tests; no network, emails, customers or production writes.
"""
from __future__ import annotations

import ast
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = (
    ROOT / "templates/moj-prop-v4/index.html",
    ROOT / "templates/moj-prop-v4/catalog/index.html",
    ROOT / "templates/moj-prop-v4/starter-30-trx/index.html",
)
CONTACT = ROOT / "templates/moj-prop/contact/index.html"
SHELL = ROOT / "scripts/mpw_dynamic_main_shell_20261019.php"
WORKFLOW = ROOT / ".github/workflows/mojplaywin-moj-prop-deploy.yml"
SUPPORT = "support@mojplaywin.com"
CANONICAL_CONTACT = "/moj-prop/contact/"


class _Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.append(dict(attrs).get("href", ""))


def links(html):
    parser = _Links()
    parser.feed(html)
    parser.close()
    return parser.links


class CanonicalMojPropContactFallback(unittest.TestCase):
    def test_three_commercial_pages_link_directly_to_existing_contact(self):
        for page in PUBLIC:
            with self.subTest(page=page):
                self.assertIn(CANONICAL_CONTACT, links(page.read_text("utf-8")))

    def test_original_verified_root_contact_fallback_stays_intact(self):
        home = PUBLIC[0].read_text("utf-8")
        self.assertIn("/contact/", links(home))
        self.assertIn("If the form is unavailable", home)
        self.assertIn("No response time is guaranteed", home)
        self.assertIn("never send passwords, wallet keys or payment", home)

    def test_contact_page_exposes_single_published_support_identity(self):
        page = CONTACT.read_text("utf-8")
        self.assertIn("mailto:support@mojplaywin.com?subject=Moj%20Prop%20Manual%20Service%20Enquiry", links(page))
        self.assertIn(SUPPORT, page)
        self.assertIn("no payment details or private credentials", page)

    def test_published_shell_and_manual_page_agree_on_support_mailbox(self):
        self.assertIn("$mail='support@mojplaywin.com';", SHELL.read_text("utf-8"))
        self.assertNotIn("mojplaywin@gmail.com", CONTACT.read_text("utf-8"))

    def test_no_new_public_mailto_or_unverified_inbox_in_v4(self):
        for page in PUBLIC:
            with self.subTest(page=page):
                data = page.read_text("utf-8")
                self.assertNotIn("mailto:", data.lower())
                self.assertNotIn("mojplaywin@gmail.com", data.lower())
                self.assertNotIn("mojtaba.rozegar11@gmail.com", data.lower())

    def test_fallback_never_claims_an_issued_paid_order_or_receipt(self):
        home = PUBLIC[0].read_text("utf-8")
        self.assertIn("cannot be treated as a verified request ID, invoice, receipt or payment", home)
        catalog = PUBLIC[1].read_text("utf-8")
        self.assertIn("not a CRM receipt, invoice or funded challenge", catalog)
        detail = PUBLIC[2].read_text("utf-8")
        self.assertIn("not a CRM request ID, order, invoice, receipt", detail)

    def test_no_executable_payment_or_external_sender_introduced(self):
        for page in PUBLIC:
            with self.subTest(page=page):
                data = page.read_text("utf-8")
                self.assertNotIn("tronWeb.trx.sendTransaction", data)
                self.assertNotIn('form action="mailto:', data)
                self.assertNotIn("fetch('mailto:", data)

    def test_plan1_native_consent_and_separate_legacy_intake_remain_available(self):
        home = PUBLIC[0].read_text("utf-8")
        home_links = links(home)
        self.assertIn("/moj-prop-interest/form/", home_links)
        self.assertIn("/moj-prop-interest/form/?lang=fa", home_links)
        # Generic educational/other-service lead paths are not funded Plan 1.
        self.assertNotIn("/moj-prop-intake/?format=html", home_links)
        for page in PUBLIC[1:]:
            with self.subTest(page=page):
                self.assertIn("/moj-prop-intake/?format=html", page.read_text("utf-8"))
        self.assertIn('id="request-form"', home)
        self.assertIn('id="status-form"', home)
        self.assertIn("No payment was taken", home)

    def test_starter30_fallback_never_asks_for_payment_or_credentials(self):
        detail = PUBLIC[2].read_text("utf-8")
        self.assertIn("MOJPROP-STARTER30", detail)
        self.assertIn("never share keys, identity documents or trading credentials", detail)
        self.assertIn("Do not send TRX", detail)

    def test_static_release_inventory_includes_all_changed_pages(self):
        script = (ROOT / "scripts/update_mojplaywin_moj_prop_catalog.py").read_text("utf-8")
        tree = ast.parse(script)
        nodes = next(
            node.value for node in tree.body
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "HTML_FILES"
                for t in node.targets
            )
        )
        paths = {
            ast.literal_eval(item.args[0])
            for item in nodes.elts
            if isinstance(item, ast.Call)
            and isinstance(item.func, ast.Name)
            and item.func.id == "Path"
        }
        self.assertTrue({
            "index.html", "catalog/index.html", "starter-30-trx/index.html"
        } <= paths)
        self.assertIn('PRESERVED_LIVE_FILES = (Path("signals/index.html"),)', script)

    def test_public_observer_includes_both_manual_contact_routes(self):
        workflow = (
            ROOT / ".github/workflows/mojprop-public-readonly-24h-evidence-20261115.yml"
        ).read_text("utf-8")
        self.assertEqual(workflow.count(
            "mojprop_contact|https://mojplaywin.com/moj-prop/contact/"), 1)
        self.assertEqual(workflow.count(
            "mpw_contact|https://mojplaywin.com/contact/"), 1)
        self.assertIn("GET_ONLY_", workflow)
        self.assertIn("NO_POST_NO_PAYMENT_NO_RELEASE=true", workflow)

    def test_owner_backup_and_manual_deploy_gates_not_bypassed(self):
        workflow = WORKFLOW.read_text("utf-8")
        for guard in (
            "github.event_name == 'workflow_dispatch'",
            "inputs.owner_approved_static_release == true",
            "MOJPROP_FULL_DB_APP_MEDIA_RESTORE_VERIFIED",
            "MOJPROP_PASSENGER_TENANT_ISOLATION_VERIFIED",
            "MOJPROP_STATIC_ROLLBACK_VERIFIED",
            "MOJPROP_STATIC_APPROVED_MAIN_SHA == github.sha",
        ):
            self.assertIn(guard, workflow)


if __name__ == "__main__":
    unittest.main()
