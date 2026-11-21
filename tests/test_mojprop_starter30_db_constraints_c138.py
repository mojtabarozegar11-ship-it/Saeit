"""C138 — Starter30 0048 source parity and offline SQL invariant regressions.

No production DB, owner record, TRON transfer, sender wallet, or invoice is
created. The SQLite fixture deliberately mirrors the declared CHECK rules;
it is NOT evidence that MariaDB has migrated or independently restored.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
import sqlite3
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "core/models.py"
MIGRATION = ROOT / "core/migrations/0048_mojprop_starter30_order.py"
PREFLIGHT = ROOT / "scripts/mojprop_schema_preflight_c83.py"
REQUIRED = {"mojprop30_positive_window", "mojprop30_required_fields"}


def _named_checks(path, migration=False):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    if migration:
        scope = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                     and node.name == "Migration")
    else:
        scope = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                     and node.name == "MojPropStarter30Order")
    checks = {}
    for call in (n for n in ast.walk(scope) if isinstance(n, ast.Call)):
        fn = call.func
        if not (isinstance(fn, ast.Attribute) and fn.attr == "CheckConstraint"):
            continue
        fields = {kw.arg: kw.value for kw in call.keywords}
        label = fields.get("name")
        if not isinstance(label, ast.Constant) or not isinstance(label.value, str):
            continue
        if label.value in checks:
            raise AssertionError("Duplicate order CHECK: " + label.value)
        checks[label.value] = ast.dump(fields["condition"], include_attributes=False)
    return checks


def _blob_sha(path):
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\x00" + data).hexdigest()


class SourceParityTests(unittest.TestCase):
    def test_01_model_has_both_constraints(self):
        self.assertTrue(REQUIRED.issubset(_named_checks(MODEL)))

    def test_02_migration_has_both_constraints(self):
        self.assertTrue(REQUIRED.issubset(_named_checks(MIGRATION, migration=True)))

    def test_03_positive_window_ast_matches(self):
        self.assertEqual(_named_checks(MODEL)["mojprop30_positive_window"],
                         _named_checks(MIGRATION, migration=True)["mojprop30_positive_window"])

    def test_04_required_binding_ast_matches(self):
        self.assertEqual(_named_checks(MODEL)["mojprop30_required_fields"],
                         _named_checks(MIGRATION, migration=True)["mojprop30_required_fields"])

    def test_05_source_pin_is_exact_git_blob(self):
        import re
        text = PREFLIGHT.read_text(encoding="utf-8")
        hit = re.search(r'"0048_mojprop_starter30_order": "([0-9a-f]{40})"', text)
        self.assertIsNotNone(hit)
        self.assertEqual(hit.group(1), _blob_sha(MIGRATION))

    def test_06_live_gate_has_no_0048_exception(self):
        text = PREFLIGHT.read_text(encoding="utf-8")
        self.assertIn("if not source_only_selftest:", text)
        self.assertIn("unreviewed staged core migration", text)
        self.assertIn("unreviewed staged Starter30 model schema", text)

    def test_07_migration_is_schema_only(self):
        text = MIGRATION.read_text(encoding="utf-8")
        self.assertNotIn("migrations.RunPython(", text)
        self.assertNotIn("migrations.RunSQL(", text)
        self.assertNotIn("SeparateDatabaseAndState", text)

    def test_08_source_only_cannot_mark_payment(self):
        checks = _named_checks(MODEL)
        self.assertIn("mojprop30_draft_only", checks)
        self.assertIn("mojprop30_tx_never_auto_credit", MIGRATION.read_text())

    def test_09_migration_parent_still_0047(self):
        self.assertIn('"0047_mpw_guest_email_recovery"', MIGRATION.read_text())

    def test_10_fixed_sun_and_mainnet_constraints_preserved(self):
        names = _named_checks(MODEL)
        self.assertIn("mojprop30_fixed_native_sun", names)
        self.assertIn("mojprop30_fixed_mainnet", names)
        self.assertIn("mojprop30_fixed_merchant", names)


class SQLiteContractTests(unittest.TestCase):
    """Actual local SQLite constraints, not MariaDB application of migration 0048."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)
        self.conn.executescript("""
            PRAGMA foreign_keys = ON;
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY,
                order_ref TEXT NOT NULL UNIQUE,
                product TEXT NOT NULL CHECK (product='MOJPROP-STARTER30'),
                merchant_domain TEXT NOT NULL CHECK (merchant_domain='mojplaywin.com'),
                merchant_id TEXT NOT NULL CHECK (merchant_id='mojplaywin-store'),
                network TEXT NOT NULL CHECK (network='tron-mainnet'),
                recipient TEXT NOT NULL,
                payer_hex41 TEXT NOT NULL,
                buyer_terms_acceptance TEXT NOT NULL,
                amount_sun INTEGER NOT NULL CHECK (amount_sun=30000000),
                issued_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                status TEXT NOT NULL CHECK (status='draft'),
                CHECK (expires_at > issued_at),
                CHECK (order_ref <> '' AND recipient <> '' AND
                       payer_hex41 <> '' AND buyer_terms_acceptance <> '')
            );
            CREATE TABLE claims (
                id INTEGER PRIMARY KEY,
                order_id INTEGER NOT NULL UNIQUE REFERENCES orders(id),
                txid TEXT NOT NULL UNIQUE,
                network TEXT NOT NULL CHECK(network='tron-mainnet'),
                state TEXT NOT NULL CHECK(state='unverified')
            );
        """)

    def row(self, **updates):
        values = dict(
            order_ref="MOJPROP30-ABCDEF123456",
            product="MOJPROP-STARTER30",
            merchant_domain="mojplaywin.com", merchant_id="mojplaywin-store",
            network="tron-mainnet", recipient="TRUSTED_REDACTED_PLACEHOLDER",
            payer_hex41="41"+"0"*40, buyer_terms_acceptance="evidence-c138",
            amount_sun=30000000, issued_at=1790000000,
            expires_at=1790003600, status="draft")
        values.update(updates)
        return values

    def insert_order(self, **updates):
        row = self.row(**updates)
        columns = list(row)
        sql = "INSERT INTO orders ("+",".join(columns)+") VALUES ("+(",".join("?" for _ in columns))+")"
        return self.conn.execute(sql, tuple(row.values())).lastrowid

    def denied(self, **overrides):
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_order(**overrides)

    def test_11_valid_draft_is_insertable_in_isolated_db(self):
        self.assertEqual(self.insert_order(), 1)

    def test_12_valid_one_second_window(self):
        self.assertEqual(self.insert_order(issued_at=1790000000, expires_at=1790000001), 1)

    def test_13_equal_timestamps_rejected(self):
        self.denied(issued_at=1790000000, expires_at=1790000000)

    def test_14_reverse_timestamps_rejected(self):
        self.denied(issued_at=1790000010, expires_at=1790000000)

    def test_15_empty_order_reference_rejected(self):
        self.denied(order_ref="")

    def test_16_empty_recipient_rejected(self):
        self.denied(recipient="")

    def test_17_empty_payer_rejected(self):
        self.denied(payer_hex41="")

    def test_18_empty_contract_evidence_rejected(self):
        self.denied(buyer_terms_acceptance="")

    def test_19_wrong_amount_rejected(self):
        self.denied(amount_sun=29999999)

    def test_20_wrong_network_rejected(self):
        self.denied(network="tron-shasta")

    def test_21_wrong_product_rejected(self):
        self.denied(product="MOJPROP-CHALLENGE")

    def test_22_wrong_merchant_domain_rejected(self):
        self.denied(merchant_domain="elsewhere.example")

    def test_23_wrong_merchant_id_rejected(self):
        self.denied(merchant_id="unrelated")

    def test_24_issued_state_rejected(self):
        self.denied(status="issued")

    def test_25_settled_state_rejected(self):
        self.denied(status="settled")

    def test_26_delivered_state_rejected(self):
        self.denied(status="delivered")

    def test_27_cancelled_state_rejected(self):
        self.denied(status="cancelled")

    def test_28_duplicate_order_reference_rejected(self):
        self.insert_order()
        self.denied()

    def test_29_claim_duplicate_txid_rejected(self):
        a = self.insert_order()
        b = self.insert_order(order_ref="MOJPROP30-ABCDEF123457")
        tx = "a"*64
        self.conn.execute("INSERT INTO claims(order_id,txid,network,state) VALUES(?,?,?,?)",
                          (a, tx, "tron-mainnet", "unverified"))
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO claims(order_id,txid,network,state) VALUES(?,?,?,?)",
                              (b, tx, "tron-mainnet", "unverified"))

    def test_30_claim_duplicate_order_rejected(self):
        a = self.insert_order()
        self.conn.execute("INSERT INTO claims(order_id,txid,network,state) VALUES(?,?,?,?)",
                          (a,"b"*64,"tron-mainnet","unverified"))
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO claims(order_id,txid,network,state) VALUES(?,?,?,?)",
                              (a,"c"*64,"tron-mainnet","unverified"))

    def test_31_claim_cannot_be_marked_verified(self):
        a = self.insert_order()
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO claims(order_id,txid,network,state) VALUES(?,?,?,?)",
                              (a,"d"*64,"tron-mainnet","verified"))

    def test_32_claim_cannot_use_testnet(self):
        a = self.insert_order()
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO claims(order_id,txid,network,state) VALUES(?,?,?,?)",
                              (a,"e"*64,"tron-nile","unverified"))

    def test_33_raw_update_cannot_set_paid(self):
        a = self.insert_order()
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE orders SET status='settled' WHERE id=?", (a,))

    def test_34_raw_update_cannot_reverse_expiry(self):
        a = self.insert_order()
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE orders SET expires_at=issued_at WHERE id=?", (a,))

    def test_35_raw_update_cannot_blank_terms(self):
        a = self.insert_order()
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE orders SET buyer_terms_acceptance='' WHERE id=?", (a,))


if __name__ == "__main__":
    unittest.main()
