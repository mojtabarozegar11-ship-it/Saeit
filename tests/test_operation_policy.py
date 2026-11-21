import unittest
from datetime import datetime, timedelta, timezone
from ava_core.operation_policy import Approval, authorize

class OperationPolicyTests(unittest.TestCase):
    def setUp(self):
        self.kw = dict(owner_id="owner-1", operation="trade_live",
                       resource_id="account-1", request_id="req-123",
                       authenticated=True)
        self.approval = Approval(**{k: self.kw[k] for k in
                                  ("owner_id", "operation", "resource_id", "request_id")},
                                 expires_at=datetime.now(timezone.utc) + timedelta(minutes=5))

    def test_exact_approval(self):
        self.assertTrue(authorize(**self.kw, approval=self.approval))

    def test_missing_approval_denied(self):
        self.assertFalse(authorize(**self.kw, approval=None))

    def test_unauthenticated_denied(self):
        self.assertFalse(authorize(**{**self.kw, "authenticated": False},
                                   approval=self.approval))

    def test_cross_owner_and_cross_resource_denied(self):
        for field, value in (("owner_id", "owner-2"), ("resource_id", "account-2"),
                             ("request_id", "req-124"), ("operation", "pay")):
            with self.subTest(field=field):
                self.assertFalse(authorize(**{**self.kw, field: value},
                                           approval=self.approval))

    def test_expired_and_naive_denied(self):
        for expiry in (datetime.now(timezone.utc) - timedelta(seconds=1),
                       datetime.now()):
            with self.subTest(expiry=expiry):
                approval = Approval("owner-1", "trade_live", "account-1", "req-123", expiry)
                self.assertFalse(authorize(**self.kw, approval=approval))

    def test_unknown_operation_denied(self):
        kw = {**self.kw, "operation": "unknown"}
        approval = Approval("owner-1", "unknown", "account-1", "req-123",
                            self.approval.expires_at)
        self.assertFalse(authorize(**kw, approval=approval))

if __name__ == "__main__":
    unittest.main()
