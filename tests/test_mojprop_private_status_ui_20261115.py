"""Offline UI contract: issued buyer tokens are actually usable without URL leaks."""
from html.parser import HTMLParser
from pathlib import Path
import unittest

HOME = Path(__file__).resolve().parents[1] / "templates/moj-prop-v4/index.html"


class FormInspector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.form_stack = []
        self.forms = {}
        self.invalid = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            if self.form_stack:
                self.invalid = True
            name = a.get("id")
            self.form_stack.append(name)
            self.forms[name] = {"inputs": [], "buttons": []}
        if self.form_stack and tag == "input":
            self.forms[self.form_stack[-1]]["inputs"].append(a)
        if self.form_stack and tag == "button":
            self.forms[self.form_stack[-1]]["buttons"].append(a)

    def handle_endtag(self, tag):
        if tag == "form":
            if not self.form_stack:
                self.invalid = True
            else:
                self.form_stack.pop()


class PrivateStatusCustomerJourneyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HOME.read_text(encoding="utf-8")
        cls.inspector = FormInspector()
        cls.inspector.feed(cls.html)
        cls.inspector.close()

    def test_intake_and_tracking_forms_are_distinct_and_well_formed(self):
        self.assertFalse(self.inspector.invalid)
        self.assertFalse(self.inspector.form_stack)
        self.assertIn("request-form", self.inspector.forms)
        self.assertIn("status-form", self.inspector.forms)

    def test_private_tracking_uses_bounded_user_editable_token(self):
        fields = [
            v for v in self.inspector.forms["status-form"]["inputs"]
            if v.get("id") == "status-token"
        ]
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0].get("type"), "text")
        self.assertEqual(fields[0].get("maxlength"), "256")
        self.assertIn("required", fields[0])
        self.assertEqual(fields[0].get("autocomplete"), "off")

    def test_client_submits_signed_receipt_in_csrf_protected_json_body(self):
        for marker in (
            "const statusEndpoint='/moj-prop-status/'",
            "statusForm.addEventListener('submit'",
            "method:'POST',credentials:'same-origin',cache:'no-store'",
            "'X-CSRFToken':csrfValue",
            "body:JSON.stringify({receipt_token:receiptToken})",
            "statusInput.value=data.receipt_token",
            "data.receipt_token.length>256",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.html)
        # Do not log, bookmark, link to or persist the bearer credential.
        self.assertNotIn("statusEndpoint+'?receipt_token=", self.html)
        self.assertNotIn("localStorage.setItem('receipt_token'", self.html)

    def test_customer_copy_receipt_includes_private_tracking_credential(self):
        self.assertIn("Private status token (keep secret)", self.html)
        self.assertIn("No payment was taken.", self.html)
        self.assertIn("does not confirm payment, settlement or delivery.", self.html)


if __name__ == "__main__":
    unittest.main()
