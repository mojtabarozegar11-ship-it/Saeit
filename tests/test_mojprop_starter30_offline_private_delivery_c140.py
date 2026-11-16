"""C140: execute private Starter30 CSV -> scorecard without merchant side effects."""
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from scripts.mojprop_starter30_offline_private_delivery_c140 import (
    PrivateReportRejected, create_private_report,
)
from scripts.mojprop_starter30 import InvalidJournal


class ActualPrivateEducationalReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inbox = self.root / "customer-private"
        self.outbox = self.root / "report-private"
        self.inbox.mkdir(mode=0o700)
        self.outbox.mkdir(mode=0o700)
        self.inbox.chmod(0o700)
        self.outbox.chmod(0o700)
        self.case = "MPS30-ABCDEF1234"
        self.input = self.inbox / "journal.csv"
        self.input.write_text(
            "session,closing_equity_usd,risk_plan_recorded,reflection_recorded\n"
            + "".join(f"{i},100.00,yes,yes\n" for i in range(1, 11)),
            encoding="utf-8",
        )
        self.input.chmod(0o600)

    def create(self, **kwargs):
        defaults = dict(source_csv=self.input, private_output_dir=self.outbox,
                        case_reference=self.case)
        defaults.update(kwargs)
        return create_private_report(**defaults)

    def test_01_real_10_session_html_created_privately(self):
        target = self.create()
        self.assertEqual(target, self.outbox / (self.case + ".html"))
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        body = target.read_text("utf-8")
        self.assertIn("Moj Prop Starter 30 — Educational scorecard", body)
        self.assertIn("Sessions documented: 10 of 10 received", body)
        self.assertIn(self.case, body)
        self.assertIn("100.00", body)
        self.assertIn("not owned, funded or withdrawable", body)
        self.assertNotIn("<script", body)
        self.assertNotIn("buyer@", body)

    def test_02_never_overwrite_existing_deliverable(self):
        target = self.create()
        original = target.read_bytes()
        with self.assertRaisesRegex(PrivateReportRejected, "overwrite forbidden"):
            self.create()
        self.assertEqual(target.read_bytes(), original)

    def test_03_incomplete_csv_never_created_as_final_delivery(self):
        self.input.write_text(
            "session,closing_equity_usd,risk_plan_recorded,reflection_recorded\n"
            + "".join(f"{i},100.00,yes,yes\n" for i in range(1, 10)),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(PrivateReportRejected, "exactly 10"):
            self.create()
        self.assertEqual(list(self.outbox.iterdir()), [])

    def test_04_no_invalid_case_reference_can_create_file(self):
        for fake in ("buyer@example.org", "", "MPS30-abc", "MPS30-ABCD1234/../../evil"):
            with self.subTest(fake=fake):
                with self.assertRaises(PrivateReportRejected):
                    self.create(case_reference=fake)
        self.assertEqual(list(self.outbox.iterdir()), [])

    def test_05_symlinked_csv_denied(self):
        real = self.inbox / "real.csv"
        self.input.rename(real)
        self.input.symlink_to(real)
        with self.assertRaises(PrivateReportRejected):
            self.create()
        self.assertEqual(list(self.outbox.iterdir()), [])

    def test_06_symlinked_output_parent_denied(self):
        symlink = self.root / "redirect"
        symlink.symlink_to(self.outbox, target_is_directory=True)
        with self.assertRaisesRegex(PrivateReportRejected, "symlink"):
            self.create(private_output_dir=symlink)
        self.assertEqual(list(self.outbox.iterdir()), [])

    def test_07_group_readable_input_denied(self):
        self.input.chmod(0o640)
        with self.assertRaises(PrivateReportRejected):
            self.create()
        self.assertEqual(list(self.outbox.iterdir()), [])

    def test_08_world_readable_output_directory_denied(self):
        self.outbox.chmod(0o755)
        with self.assertRaises(PrivateReportRejected):
            self.create()
        self.assertEqual(list(self.outbox.iterdir()), [])

    def test_09_malformed_csv_does_not_create_report(self):
        self.input.write_text("email,balance\nbuyer@example.org,100\n", encoding="utf-8")
        with self.assertRaises(InvalidJournal):
            self.create()
        self.assertEqual(list(self.outbox.iterdir()), [])

    def test_10_no_persistent_target_on_write_failure(self):
        # Source-validated HTML cannot be partially published. Force fsync
        # failure after opening the private report, before completion.
        with patch("scripts.mojprop_starter30_offline_private_delivery_c140.os.fsync",
                   side_effect=OSError("synthetic storage failure")):
            with self.assertRaises(OSError):
                self.create()
        self.assertEqual(list(self.outbox.iterdir()), [])

    def test_11_reject_hardlinked_source(self):
        alias = self.inbox / "other.csv"
        os.link(self.input, alias)
        with self.assertRaises(PrivateReportRejected):
            self.create()
        self.assertEqual(list(self.outbox.iterdir()), [])

    def test_12_no_transaction_or_email_trigger_code(self):
        source = (Path(__file__).resolve().parents[1]
                  / "scripts/mojprop_starter30_offline_private_delivery_c140.py").read_text()
        for forbidden in ("send_mail(", "requests.post(", "transfer_trx(",
                          "create_payment(", "mark_paid(", "email.send("):
            self.assertNotIn(forbidden, source)
        self.assertNotIn("payment_recorded = True", source)

    def test_13_raw_email_csv_is_rejected(self):
        self.input.write_text(
            "session,closing_equity_usd,risk_plan_recorded,reflection_recorded\n"
            + "1,buyer@example.org,yes,yes\n" * 10,
            encoding="utf-8",
        )
        with self.assertRaises(InvalidJournal):
            self.create()
        self.assertEqual(list(self.outbox.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
