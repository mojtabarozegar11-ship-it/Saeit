"""Authorization regression tests; no production operations."""
import unittest
from datetime import datetime, timedelta, timezone
from ava_core.approvals import Approval, SENSITIVE_OPERATIONS, authorized

class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 11, tzinfo=timezone.utc)
        self.approval = Approval("owner", "live_trade", "account-1",
                                 self.now + timedelta(minutes=5), True)

    def check(self, **overrides):
        values = dict(owner_id="owner", operation="live_trade",
                      resource_id="account-1", approval=self.approval, now=self.now)
        values.update(overrides)
        return authorized(**values)

    def test_exact_approval(self):
        self.assertTrue(self.check())

    def test_missing_or_negative_approval(self):
        self.assertFalse(self.check(approval=None))
        self.assertFalse(self.check(approval=Approval("owner", "live_trade", "account-1",
                                                      self.now + timedelta(minutes=5), False)))

    def test_owner_operation_and_resource_must_match(self):
        self.assertFalse(self.check(owner_id="another"))
        self.assertFalse(self.check(operation="payment"))
        self.assertFalse(self.check(resource_id="account-2"))

    def test_expired_and_boundary(self):
        self.assertFalse(self.check(now=self.approval.expires_at))
        self.assertFalse(self.check(now=self.approval.expires_at + timedelta(seconds=1)))

    def test_unknown_and_blank_operations_deny(self):
        self.assertFalse(self.check(operation="unknown"))
        self.assertFalse(self.check(operation=""))
        self.assertFalse(self.check(owner_id=" "))
        self.assertFalse(self.check(resource_id=" "))

    def test_all_sensitive_operations_default_deny(self):
        for operation in SENSITIVE_OPERATIONS:
            with self.subTest(operation=operation):
                self.assertFalse(self.check(operation=operation, approval=None))

    def test_naive_expiry_and_now_deny(self):
        naive = Approval("owner", "live_trade", "account-1",
                         datetime(2026, 11, 12), True)
        self.assertFalse(self.check(approval=naive))
        self.assertFalse(self.check(now=datetime(2026, 11, 11)))

if __name__ == "__main__":
    unittest.main()
