"""Commercial support acknowledgments: strict filters, local MTA, no repeat sending."""
from email.message import EmailMessage
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import tempfile
import unittest

from scripts import mpw_support_qualified_lead_responder_20261026 as lead


def incoming(subject="MojPlayWin website-doctor service enquiry", sender="buyer@example.org",
             auto=None):
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = "support@mojplaywin.com"
    msg["Subject"] = subject
    if auto:
        msg["Auto-Submitted"] = auto
    msg.set_content("Please audit my website. No secrets.")
    return msg.as_bytes()


class CommercialLeadTests(unittest.TestCase):
    def test_exact_subject_and_limited_categories(self):
        self.assertEqual(lead.qualify(incoming()), ("buyer@example.org", "website-doctor"))
        self.assertEqual(lead.qualify(incoming("MojPlayWin business quote")),
                         ("buyer@example.org", "business_quote"))
        self.assertIsNone(lead.qualify(incoming("MojPlayWin bitcoin investment")))
        self.assertIsNone(lead.qualify(incoming("Win a reward")))
        self.assertIsNone(lead.qualify(incoming(auto="auto-generated")))
        self.assertIsNone(lead.qualify(incoming(sender="mailer-daemon@example.org")))
        self.assertIsNone(lead.qualify(incoming(sender="support@mojplaywin.com")))

    def test_acknowledgment_no_contract_or_payment(self):
        mail = lead.reply("buyer@example.org", "business_quote")
        self.assertIn(b"Auto-Submitted: auto-replied", mail)
        self.assertIn(b"not a contract, quotation", mail)
        self.assertIn(b"not send passwords", mail)
        self.assertIn(b"To: buyer@example.org", mail)
        self.assertNotIn(b"payment address", mail.lower())

    def test_single_idempotent_real_mta_submission(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            box = home / "support"
            (box / "new").mkdir(parents=True)
            (box / "new" / "msg1").write_bytes(incoming())
            (box / "new" / "msg2").write_bytes(incoming("Security alert"))
            private = home / "private"
            fake_sendmail = home / "sendmail"
            fake_sendmail.write_text("fake-local-mta")
            with (mock.patch.object(lead, "MAILDIR", box),
                  mock.patch.object(lead, "PRIVATE", private),
                  mock.patch.object(lead, "RECEIPTS", private / "acknowledgements"),
                  mock.patch.object(lead, "LOCK", private / ".process.lock"),
                  mock.patch.object(lead, "SENDMAIL", fake_sendmail),
                  mock.patch.object(lead.subprocess, "run",
                      return_value=SimpleNamespace(returncode=0)) as mta):
                first = lead.run()
                second = lead.run()
            self.assertEqual(first["queued_to_local_mta"], 1)
            self.assertEqual(second["queued_to_local_mta"], 0)
            self.assertEqual(second["previously_processed"], 1)
            mta.assert_called_once()
            receipt_paths = list((private / "acknowledgements").glob("*.json"))
            self.assertEqual(len(receipt_paths), 1)
            payload = receipt_paths[0].read_text()
            self.assertNotIn("buyer@example.org", payload)
            self.assertIn("accepted_by_local_mta", payload)


if __name__ == "__main__":
    unittest.main()
