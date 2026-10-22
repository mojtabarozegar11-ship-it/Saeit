"""Offline buyer-style acceptance tests for the F41 Merchant Audit Toolkit."""
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import f41_merchant_audit_cli as audit

ADDRESS = "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb"
INVOICE = ["A100", "tron-mainnet", "TRX", ADDRESS, "1000000", ""]
PAYMENT = ["A100", "a" * 64, "tron-mainnet", "TRX", ADDRESS, "1000000", ""]


def csv_content(fields, rows):
    import io
    value = io.StringIO(newline="")
    writer = csv.writer(value, lineterminator="\n")
    writer.writerow(fields)
    writer.writerows(rows)
    return value.getvalue().encode("utf-8")


def run_rows(invoices=None, payments=None):
    return json.loads(audit.render(
        csv_content(audit.INV_FIELDS, [INVOICE] if invoices is None else invoices),
        csv_content(audit.PAY_FIELDS, [PAYMENT] if payments is None else payments)
    )["report.json"])


class MerchantAuditTests(unittest.TestCase):
    def test_example_match_is_never_settled(self):
        result = run_rows()
        row = result["invoices"][0]
        self.assertEqual(row["status"], "MATCHED_EXPORT_UNVERIFIED")
        self.assertFalse(row["delivery_authorized"])
        self.assertFalse(result["chain_finality_verified"])
        self.assertEqual(result["payments_broadcast"], 0)

    def test_unpaid(self):
        self.assertEqual(run_rows(payments=[])["invoices"][0]["status"], "NO_PAYMENT_IN_EXPORT")

    def test_underpaid(self):
        p = PAYMENT.copy()
        p[5] = "999999"
        self.assertEqual(run_rows(payments=[p])["invoices"][0]["status"], "UNDERPAID_IN_EXPORT")

    def test_overpaid(self):
        p = PAYMENT.copy()
        p[5] = "1000001"
        self.assertEqual(run_rows(payments=[p])["invoices"][0]["status"], "OVERPAID_IN_EXPORT")

    def test_wrong_recipient(self):
        p = PAYMENT.copy()
        p[4] = "TWTBsKZPVuQgaGNbyJWJm9XR28g4wVBCNQ"
        self.assertEqual(run_rows(payments=[p])["invoices"][0]["status"], "FIELDS_MISMATCH_REVIEW")

    def test_duplicate_payment_across_invoices(self):
        b = INVOICE.copy()
        b[0] = "B200"
        p = PAYMENT.copy()
        p[0] = "B200"
        result = run_rows(invoices=[INVOICE, b], payments=[PAYMENT, p])
        self.assertEqual([x["status"] for x in result["invoices"]],
                         ["DUPLICATE_TXID_REVIEW", "DUPLICATE_TXID_REVIEW"])

    def test_partial_multiple_payment_never_settles(self):
        p1 = PAYMENT.copy()
        p1[5] = "400000"
        p2 = PAYMENT.copy()
        p2[1] = "b" * 64
        p2[5] = "600000"
        self.assertEqual(run_rows(payments=[p1, p2])["invoices"][0]["status"],
                         "MULTIPLE_PAYMENTS_REVIEW")

    def test_orphaned_payment(self):
        p = PAYMENT.copy()
        p[0] = "B200"
        result = run_rows(payments=[p])
        self.assertEqual(result["invoices"][0]["status"], "NO_PAYMENT_IN_EXPORT")
        self.assertEqual(result["orphaned_payments"][0]["invoice_id"], "B200")

    def test_invalid_address_checksum(self):
        inv = INVOICE.copy()
        inv[3] = inv[3][:-1] + "c"
        with self.assertRaisesRegex(ValueError, "CHECKSUM"):
            run_rows(invoices=[inv])

    def test_invalid_amount(self):
        inv = INVOICE.copy()
        inv[4] = "1.0"
        with self.assertRaisesRegex(ValueError, "AMOUNT"):
            run_rows(invoices=[inv])

    def test_invalid_network(self):
        inv = INVOICE.copy()
        inv[1] = "ethereum"
        with self.assertRaisesRegex(ValueError, "NETWORK"):
            run_rows(invoices=[inv])

    def test_token_contract_required(self):
        inv = INVOICE.copy()
        inv[2] = "TRC20"
        with self.assertRaisesRegex(ValueError, "TOKEN"):
            run_rows(invoices=[inv])

    def test_trx_cannot_carry_token_contract(self):
        inv = INVOICE.copy()
        inv[5] = ADDRESS
        with self.assertRaisesRegex(ValueError, "TRX_HAS"):
            run_rows(invoices=[inv])

    def test_duplicate_invoice_id_rejected(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE_INVOICE"):
            run_rows(invoices=[INVOICE, INVOICE])

    def test_duplicate_headers_and_unexpected_columns_rejected(self):
        content = b"invoice_id,invoice_id\nA100,A100\n"
        with self.assertRaisesRegex(ValueError, "SCHEMA"):
            audit.render(content, csv_content(audit.PAY_FIELDS, []))

    def test_injection_in_identifier_rejected(self):
        inv = INVOICE.copy()
        inv[0] = "=cmd"
        with self.assertRaisesRegex(ValueError, "ID_INVALID"):
            run_rows(invoices=[inv])

    def test_build_verify_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            invoices = base / "invoices.csv"
            payments = base / "payments.csv"
            invoices.write_bytes(csv_content(audit.INV_FIELDS, [INVOICE]))
            payments.write_bytes(csv_content(audit.PAY_FIELDS, [PAYMENT]))
            out = base / "result"
            receipt = audit.build(invoices, payments, out)
            self.assertEqual(receipt["schema"], audit.SCHEMA + ".integrity.v1")
            self.assertEqual(audit.build(invoices, payments, out, True), receipt)
            with self.assertRaisesRegex(ValueError, "MUST_BE_NEW"):
                audit.build(invoices, payments, out)
            (out / "invoice_review.csv").write_text("tampered")
            with self.assertRaisesRegex(ValueError, "INTEGRITY_FAILED"):
                audit.build(invoices, payments, out, True)

    def test_changed_input_fails_verification(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            invoices = base / "invoices.csv"
            payments = base / "payments.csv"
            invoices.write_bytes(csv_content(audit.INV_FIELDS, [INVOICE]))
            payments.write_bytes(csv_content(audit.PAY_FIELDS, [PAYMENT]))
            audit.build(invoices, payments, base / "result")
            payments.write_bytes(csv_content(audit.PAY_FIELDS, []))
            with self.assertRaisesRegex(ValueError, "INTEGRITY_FAILED"):
                audit.build(invoices, payments, base / "result", True)

    def test_symlink_input_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            actual = base / "actual.csv"
            actual.write_bytes(csv_content(audit.INV_FIELDS, [INVOICE]))
            (base / "link.csv").symlink_to(actual)
            with self.assertRaisesRegex(ValueError, "UNSAFE_INPUT"):
                audit.build(base / "link.csv", base / "link.csv", base / "out")

    def test_cli_end_to_end(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            inv = base / "invoices.csv"
            pay = base / "payments.csv"
            inv.write_bytes(csv_content(audit.INV_FIELDS, [INVOICE]))
            pay.write_bytes(csv_content(audit.PAY_FIELDS, [PAYMENT]))
            cmd = [sys.executable, str(Path(audit.__file__).resolve()),
                   "--invoices", str(inv), "--payments", str(pay), "--out", str(base / "out")]
            r = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=10)
            self.assertIn("F41_CHAIN_FINALITY_CERTIFIED=false", r.stdout)
            r = subprocess.run(cmd + ["--verify"], check=True, capture_output=True, text=True, timeout=10)
            self.assertIn("F41_MERCHANT_AUDIT_INTEGRITY=PASS", r.stdout)


if __name__ == "__main__":
    unittest.main()
