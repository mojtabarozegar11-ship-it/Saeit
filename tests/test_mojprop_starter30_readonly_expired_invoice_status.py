"""Read-only starter30 invoice status: time-expired display must not require DB edits.

Runs against the actual source function isolated via AST, without importing Django,
connecting to a DB, issuing an invoice or sending a blockchain transaction.
"""
import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock

SOURCE = Path(__file__).resolve().parents[1] / "prop_firm" / "starter30_live.py"


def isolated_invoice_status(now, payment):
    source = ast.parse(SOURCE.read_text(encoding="utf8"))
    targets = [n for n in source.body if isinstance(n, ast.FunctionDef)
               and n.name == "invoice_status"]
    if len(targets) != 1:
        raise AssertionError("expected one isolated invoice_status implementation")
    manager = Mock()
    manager.using.return_value.select_related.return_value.get.return_value = payment
    klass = SimpleNamespace(
        Status=SimpleNamespace(AWAITING="AWAITING", EXPIRED="EXPIRED", PAID="PAID"),
        objects=manager,
    )
    check_release = Mock()
    scope = {
        "require_release": check_release,
        "PropSimulationPayment": klass,
        "MOJPROP_DB_ALIAS": "mojprop",
        "timezone": SimpleNamespace(now=lambda: now),
    }
    exec(compile(ast.Module(body=targets, type_ignores=[]),
                 filename=str(SOURCE), mode="exec"), scope)
    result = scope["invoice_status"]("MOJPROP30-" + "A" * 20)
    check_release.assert_called_once_with()
    manager.using.assert_called_once_with("mojprop")
    manager.using.return_value.select_related.assert_called_once_with("invoice_owner")
    manager.using.return_value.select_related.return_value.get.assert_called_once_with(
        invoice_owner__invoice_ref="MOJPROP30-" + "A" * 20
    )
    return result


def payment(status, expires_at):
    x = SimpleNamespace(
        status=status,
        expires_at=expires_at,
        payment_ref="PAY-REFERENCETOKEN",
        recipient="T" + "A" * 33,
        amount_sun=30_000_000,
        txid=None,
        save=Mock(side_effect=AssertionError("status lookup must be read only")),
    )
    return x


class Starter30ExpiredStatusReadOnlyTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 21, 12, tzinfo=timezone.utc)

    def test_future_awaiting_invoice_stays_awaiting(self):
        p = payment("AWAITING", self.now + timedelta(hours=1))
        status = isolated_invoice_status(self.now, p)
        self.assertEqual(status["status"], "AWAITING")
        p.save.assert_not_called()

    def test_past_awaiting_invoice_is_reported_expired(self):
        p = payment("AWAITING", self.now - timedelta(seconds=1))
        status = isolated_invoice_status(self.now, p)
        self.assertEqual(status["status"], "EXPIRED")
        self.assertEqual(status["amount_sun"], 30_000_000)
        p.save.assert_not_called()

    def test_exact_expiry_instant_is_expired(self):
        p = payment("AWAITING", self.now)
        self.assertEqual(isolated_invoice_status(self.now, p)["status"], "EXPIRED")
        p.save.assert_not_called()

    def test_paid_is_not_reclassified_even_if_past_expiry(self):
        p = payment("PAID", self.now - timedelta(days=1))
        p.txid = "a" * 64
        v = isolated_invoice_status(self.now, p)
        self.assertEqual(v["status"], "PAID")
        self.assertEqual(v["txid"], "a" * 64)
        p.save.assert_not_called()


if __name__ == "__main__":
    import unittest
    unittest.main()
