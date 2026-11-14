"""Pure one-bot grant policy tests. No Django database or external actions."""
import unittest
from types import SimpleNamespace

from core.grant_scope_policy import (
    require_exact_consumption_scope, require_exact_grant_scope,
)


def approval(action="publish", target_type="KnowledgeArticle", target_id="7", risk="high"):
    return SimpleNamespace(
        action_type=action, target_type=target_type,
        target_id=target_id, risk=risk,
    )


class PolicyContractTests(unittest.TestCase):
    def assert_denied(self, approval_obj, scope):
        with self.assertRaises(ValueError):
            require_exact_grant_scope(approval_obj, scope)

    def test_01_publish_exact(self):
        self.assertEqual(require_exact_grant_scope(
            approval(), {"action": "publish", "target": "knowledge:7"}),
            {"action": "publish", "target": "knowledge:7"},
        )

    def test_02_payment_exact(self):
        self.assertEqual(require_exact_grant_scope(
            approval("payment", "Order", "9", "critical"),
            {"action": "payment", "target": "order:9"},
        )["target"], "order:9")

    def test_03_mailbox_exact(self):
        self.assertEqual(require_exact_grant_scope(
            approval("external_write", "TradeMailbox", "company-trade"),
            {"action": "external_write", "target": "company-trade"},
        )["target"], "company-trade")

    def test_04_paid_knowledge_exact(self):
        self.assertEqual(require_exact_grant_scope(
            approval("knowledge_content_generation", "AgentTask", "11"),
            {"action": "knowledge_content_generation", "run_id": 3, "paid_model": True},
        )["run_id"], 3)

    def test_05_no_scope(self):
        self.assert_denied(approval(), None)

    def test_06_no_action(self):
        self.assert_denied(approval(), {"target": "knowledge:7"})

    def test_07_unknown_action(self):
        self.assert_denied(approval("deploy", "Host", "1"), {"action": "deploy", "target": "host:1"})

    def test_08_action_list(self):
        self.assert_denied(approval(), {"action": ["publish"], "target": "knowledge:7"})

    def test_09_cross_action(self):
        self.assert_denied(approval(), {"action": "payment", "target": "order:7"})

    def test_10_cross_type(self):
        self.assert_denied(approval(target_type="Order"), {"action": "publish", "target": "knowledge:7"})

    def test_11_cross_object(self):
        self.assert_denied(approval(), {"action": "publish", "target": "knowledge:8"})

    def test_12_extra_field(self):
        self.assert_denied(approval(), {"action": "publish", "target": "knowledge:7", "wildcard": True})

    def test_13_low_risk(self):
        self.assert_denied(approval(risk="low"), {"action": "publish", "target": "knowledge:7"})

    def test_14_payment_high_risk_only(self):
        self.assert_denied(approval("payment", "Order", "9", "high"), {"action": "payment", "target": "order:9"})

    def test_15_id_leading_zero(self):
        self.assert_denied(approval(target_id="07"), {"action": "publish", "target": "knowledge:07"})

    def test_16_non_numeric_object(self):
        self.assert_denied(approval(target_id="abc"), {"action": "publish", "target": "knowledge:abc"})

    def test_17_empty_object_id(self):
        self.assert_denied(approval(target_id=""), {"action": "publish", "target": "knowledge:"})

    def test_18_wrong_mailbox(self):
        self.assert_denied(
            approval("external_write", "TradeMailbox", "not-company-trade"),
            {"action": "external_write", "target": "not-company-trade"},
        )

    def test_19_paid_run_bool(self):
        self.assert_denied(
            approval("knowledge_content_generation", "AgentTask", "11"),
            {"action": "knowledge_content_generation", "run_id": True, "paid_model": True},
        )

    def test_20_paid_model_string(self):
        self.assert_denied(
            approval("knowledge_content_generation", "AgentTask", "11"),
            {"action": "knowledge_content_generation", "run_id": 3, "paid_model": "true"},
        )

    def test_21_paid_run_zero(self):
        self.assert_denied(
            approval("knowledge_content_generation", "AgentTask", "11"),
            {"action": "knowledge_content_generation", "run_id": 0, "paid_model": True},
        )

    def test_22_required_scope_exact(self):
        self.assertEqual(
            require_exact_consumption_scope(
                {"action": "publish", "target": "knowledge:7"},
                {"action": "publish", "target": "knowledge:7"},
            )["action"], "publish"
        )

    def test_23_subset_denied(self):
        with self.assertRaises(ValueError):
            require_exact_consumption_scope(
                {"action": "publish", "target": "knowledge:7"}, {"action": "publish"})

    def test_24_extra_consumption_denied(self):
        with self.assertRaises(ValueError):
            require_exact_consumption_scope(
                {"action": "publish", "target": "knowledge:7"},
                {"action": "publish", "target": "knowledge:7", "override": True})

    def test_25_scope_value_mismatch(self):
        with self.assertRaises(ValueError):
            require_exact_consumption_scope(
                {"action": "publish", "target": "knowledge:7"},
                {"action": "publish", "target": "knowledge:8"})

    def test_26_missing_required_scope(self):
        with self.assertRaises(ValueError):
            require_exact_consumption_scope({"action": "publish", "target": "knowledge:7"}, None)

    def test_27_list_required_scope(self):
        with self.assertRaises(ValueError):
            require_exact_consumption_scope({"action": "publish", "target": "knowledge:7"}, ["publish"])

    def test_28_bool_vs_int_mismatch(self):
        with self.assertRaises(ValueError):
            require_exact_consumption_scope({"paid_model": True}, {"paid_model": 1})

    def test_29_empty_scope(self):
        with self.assertRaises(ValueError):
            require_exact_consumption_scope({}, {})

    def test_30_approval_without_type(self):
        self.assert_denied(SimpleNamespace(target_type="Order", target_id="7", risk="critical"),
                           {"action": "payment", "target": "order:7"})


if __name__ == "__main__":
    unittest.main()
