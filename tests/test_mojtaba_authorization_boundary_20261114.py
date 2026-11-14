"""Offline regression gates for the single mojtaba.bot.ai approval boundaries.

No Django DB, network, credentials, payment, broker or email is required.
These pure checks do not assert an independently verified host approval.
"""
import unittest
from datetime import datetime, timedelta, timezone

from ava_core import action_policy, approvals, operation_guard, operation_policy


NOW = datetime(2026, 11, 14, 5, 0, tzinfo=timezone.utc)
LATER = NOW + timedelta(minutes=5)


class TypedActionTests(unittest.TestCase):
    def request(self, **kwargs):
        fields = {
            "owner_id": "owner", "action": action_policy.Action.READ_OWN_DATA,
            "resource_id": "resource", "authenticated": True,
        }
        fields.update(kwargs)
        return action_policy.ActionRequest(**fields)

    def decide(self, **kwargs):
        return action_policy.authorize(self.request(**kwargs))

    def test_01_authenticated_read_is_allowed(self):
        self.assertEqual(self.decide(), action_policy.Decision.ALLOW)

    def test_02_authenticated_string_is_rejected(self):
        self.assertEqual(self.decide(authenticated="true"), action_policy.Decision.DENY)

    def test_03_authenticated_integer_is_rejected(self):
        self.assertEqual(self.decide(authenticated=1), action_policy.Decision.DENY)

    def test_04_owner_list_is_rejected(self):
        self.assertEqual(self.decide(owner_id=["owner"]), action_policy.Decision.DENY)

    def test_05_resource_dict_is_rejected(self):
        self.assertEqual(self.decide(resource_id={"id": 1}), action_policy.Decision.DENY)

    def test_06_untyped_action_string_is_rejected(self):
        self.assertEqual(self.decide(action="live_trade"), action_policy.Decision.DENY)

    def test_07_sensitive_unverified_requires_approval(self):
        self.assertEqual(self.decide(action=action_policy.Action.LIVE_TRADE),
                         action_policy.Decision.REQUIRE_APPROVAL)

    def test_08_verification_integer_cannot_approve(self):
        self.assertEqual(self.decide(action=action_policy.Action.LIVE_TRADE,
                                     approved_action=action_policy.Action.LIVE_TRADE,
                                     approved_resource_id="resource", approval_verified=1),
                         action_policy.Decision.REQUIRE_APPROVAL)

    def test_09_exact_sensitive_approval_is_a_pure_allow_decision(self):
        self.assertEqual(self.decide(action=action_policy.Action.LIVE_TRADE,
                                     approved_action=action_policy.Action.LIVE_TRADE,
                                     approved_resource_id="resource", approval_verified=True),
                         action_policy.Decision.ALLOW)

    def test_10_other_resource_does_not_inherit_approval(self):
        self.assertEqual(self.decide(action=action_policy.Action.LIVE_TRADE,
                                     approved_action=action_policy.Action.LIVE_TRADE,
                                     approved_resource_id="different", approval_verified=True),
                         action_policy.Decision.REQUIRE_APPROVAL)


class UnifiedApprovalTests(unittest.TestCase):
    def receipt(self, **kwargs):
        data = {"owner_id": "owner", "operation": "live_trade",
                "resource_id": "account", "expires_at": LATER, "approved": True}
        data.update(kwargs)
        return approvals.Approval(**data)

    def check(self, **kwargs):
        data = {"owner_id": "owner", "operation": "live_trade",
                "resource_id": "account", "approval": self.receipt(), "now": NOW}
        data.update(kwargs)
        return approvals.authorized(**data)

    def test_11_exact_approval_accepted(self):
        self.assertTrue(self.check())

    def test_12_owner_list_denied(self):
        self.assertFalse(self.check(owner_id=["owner"]))

    def test_13_operation_list_denied(self):
        self.assertFalse(self.check(operation=["live_trade"]))

    def test_14_resource_number_denied(self):
        self.assertFalse(self.check(resource_id=7))

    def test_15_approved_integer_denied(self):
        self.assertFalse(self.check(approval=self.receipt(approved=1)))

    def test_16_dict_receipt_denied(self):
        self.assertFalse(self.check(approval={"approved": True}))

    def test_17_invalid_expiry_type_denied(self):
        self.assertFalse(self.check(approval=self.receipt(expires_at="tomorrow")))

    def test_18_invalid_now_type_denied(self):
        self.assertFalse(self.check(now="today"))

    def test_19_naive_timestamp_denied(self):
        self.assertFalse(self.check(now=datetime(2026, 11, 14, 5)))

    def test_20_boundary_expiry_denied(self):
        self.assertFalse(self.check(now=LATER))

    def test_21_unknown_operation_denied(self):
        self.assertFalse(self.check(operation="other"))


class OperationGuardTests(unittest.TestCase):
    def receipt(self, **kwargs):
        data = {"action": "deploy", "resource": "release-1",
                "expires_at": LATER, "verified": True, "approval_id": "approval-1"}
        data.update(kwargs)
        return operation_guard.Approval(**data)

    def check(self, **kwargs):
        data = {"action": "deploy", "resource": "release-1",
                "approval": self.receipt(), "now": NOW}
        data.update(kwargs)
        return operation_guard.authorize(**data)

    def test_22_exact_verified_receipt_accepted(self):
        self.assertTrue(self.check())

    def test_23_action_list_denied(self):
        self.assertFalse(self.check(action=["deploy"]))

    def test_24_resource_dict_denied(self):
        self.assertFalse(self.check(resource={"id": 1}))

    def test_25_verified_integer_denied(self):
        self.assertFalse(self.check(approval=self.receipt(verified=1)))

    def test_26_approval_id_integer_denied(self):
        self.assertFalse(self.check(approval=self.receipt(approval_id=1)))

    def test_27_receipt_dict_denied(self):
        self.assertFalse(self.check(approval={"verified": True}))

    def test_28_expiry_string_denied(self):
        self.assertFalse(self.check(approval=self.receipt(expires_at="later")))

    def test_29_now_integer_denied(self):
        self.assertFalse(self.check(now=99))

    def test_30_unknown_sensitive_action_denied(self):
        self.assertFalse(self.check(action="unknown"))

    def test_31_mismatched_resource_denied(self):
        self.assertFalse(self.check(resource="release-2"))

    def test_32_exact_expiry_denied(self):
        self.assertFalse(self.check(now=LATER))


class RequestPolicyTests(unittest.TestCase):
    def receipt(self, **kwargs):
        data = {"owner_id": "مالک", "operation": "trade_live",
                "resource_id": "حساب-۱", "request_id": "req-1",
                "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5)}
        data.update(kwargs)
        return operation_policy.Approval(**data)

    def check(self, **kwargs):
        data = {"owner_id": "مالک", "operation": "trade_live",
                "resource_id": "حساب-۱", "request_id": "req-1",
                "authenticated": True, "approval": self.receipt()}
        data.update(kwargs)
        return operation_policy.authorize(**data)

    def test_33_unicode_bound_identifier_is_supported(self):
        self.assertTrue(self.check())

    def test_34_authenticated_integer_denied(self):
        self.assertFalse(self.check(authenticated=1))

    def test_35_invalid_request_id_type_denied(self):
        self.assertFalse(self.check(request_id=["req-1"]))

    def test_36_invalid_receipt_field_type_denied(self):
        self.assertFalse(self.check(approval=self.receipt(owner_id=["مالک"])))

    def test_37_cross_request_replay_denied(self):
        self.assertFalse(self.check(request_id="req-2"))

    def test_38_unknown_operation_denied(self):
        self.assertFalse(self.check(operation="magic_auto_spend"))

    def test_39_expired_receipt_denied(self):
        self.assertFalse(self.check(approval=self.receipt(
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1))))

    def test_40_naive_expiry_denied(self):
        self.assertFalse(self.check(approval=self.receipt(expires_at=datetime(2026, 11, 14))))

    def test_41_oversized_request_id_denied(self):
        self.assertFalse(self.check(request_id="x" * 513))

    def test_42_unapproved_sensitive_operation_denied(self):
        self.assertFalse(self.check(approval=None))


if __name__ == "__main__":
    unittest.main()
