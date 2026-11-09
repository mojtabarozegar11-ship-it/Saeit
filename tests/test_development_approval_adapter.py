import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from core.development_approval_adapter import verify_grant_snapshot


def grant(**overrides):
    now = datetime(2026, 11, 9, tzinfo=timezone.utc)
    approval = SimpleNamespace(
        action_type="development_purchase", target_type="DevelopmentPurchase",
        target_id="server-quote-17", status="approved", requested_by_id=7,
    )
    obj = SimpleNamespace(
        pk=19, actor_id=7, approval=approval, used_at=None,
        expires_at=now + timedelta(minutes=5),
        scope={
            "proposal_id": "server-quote-17", "expense_type": "infrastructure",
            "vendor": "approved-host", "amount": "200.00",
            "currency": "USD", "accounting_period": "2026-11",
        },
    )
    for key, value in overrides.items():
        setattr(obj, key, value)
    return obj, now


def check(obj, now):
    return verify_grant_snapshot(
        obj, now=now, approval_reference="19",
        expense_type="infrastructure", vendor="approved-host",
        amount="200", currency="USD", accounting_period="2026-11",
    )


class DevelopmentApprovalAdapterTests(unittest.TestCase):
    def test_exact_owner_grant_eligible_for_subsequent_atomic_consumption(self):
        obj, now = grant()
        self.assertTrue(check(obj, now))
        self.assertIsNone(obj.used_at)  # read-only precheck, not a payment

    def test_expired_or_consumed_grant_is_rejected(self):
        obj, now = grant()
        obj.expires_at = now
        self.assertFalse(check(obj, now))
        obj, now = grant(used_at=now)
        self.assertFalse(check(obj, now))

    def test_wrong_owner_or_approval_type_is_rejected(self):
        obj, now = grant(actor_id=22)
        self.assertFalse(check(obj, now))
        obj, now = grant()
        obj.approval.target_type = "AgentTask"
        self.assertFalse(check(obj, now))

    def test_scope_cannot_reuse_approval_for_other_vendor_or_amount(self):
        obj, now = grant()
        obj.scope["vendor"] = "other-host"
        self.assertFalse(check(obj, now))
        obj, now = grant()
        obj.scope["amount"] = "100"
        self.assertFalse(check(obj, now))

    def test_scope_requires_period_currency_and_proposal(self):
        for key in ("proposal_id", "currency", "accounting_period"):
            obj, now = grant()
            obj.scope.pop(key)
            with self.subTest(key=key):
                self.assertFalse(check(obj, now))

    def test_unverified_approval_is_rejected(self):
        obj, now = grant()
        obj.approval.status = "pending"
        self.assertFalse(check(obj, now))


if __name__ == "__main__":
    unittest.main()
