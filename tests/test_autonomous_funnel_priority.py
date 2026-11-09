"""Test actual AutonomousBrain candidate priority without requiring Django DB."""

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


def load_brain():
    django = types.ModuleType("django")
    django_db = types.ModuleType("django.db")
    django_db.DatabaseError = type("DatabaseError", (Exception,), {})
    models = types.ModuleType("core.models")
    for name in ("AgentTask", "Product", "Order", "LedgerEntry", "CommerceFunnelEvent"):
        setattr(models, name, object())
    module_name = "autonomous_brain_isolated_test"
    module = types.ModuleType(module_name)
    path = Path(__file__).resolve().parents[1] / "core" / "autonomous_brain.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module.__spec__ = spec
    with patch.dict(sys.modules, {
        "django": django, "django.db": django_db, "core.models": models,
        module_name: module,
    }):
        spec.loader.exec_module(module)
    return module.AutonomousBrain


def state(**changes):
    result = {
        "unfinished_tasks": 0,
        "financial_event_needs_reconcile": False,
        "funnel_event_needs_review": False,
        "self_improvement_complete": True,
        "self_improvement_failed": False,
        "self_improvement_unverified": False,
        "market_inventory_measured": True,
        "market_research_complete": False,
        "opportunity_scored": False,
        "mvp_built": 0,
        "offer_designed": 0,
        "growth_ready": 0,
        "active_products": 1,
    }
    result.update(changes)
    return result


class AutonomousFunnelPriorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.brain = load_brain()()

    def test_new_commerce_event_prompts_real_readonly_audit(self):
        chosen = self.brain.candidates(state(funnel_event_needs_review=True))[0]
        self.assertEqual(chosen.action, "income_funnel_audit")

    def test_new_payment_evidence_has_higher_priority_than_funnel(self):
        chosen = self.brain.candidates(state(
            financial_event_needs_reconcile=True, funnel_event_needs_review=True,
        ))[0]
        self.assertEqual(chosen.action, "income_revenue_verify")

    def test_existing_unfinished_work_blocks_duplicate_new_task(self):
        chosen = self.brain.candidates(state(
            unfinished_tasks=1, funnel_event_needs_review=True,
        ))[0]
        self.assertEqual(chosen.action, "continue_existing_work")

    def test_no_new_evidence_does_not_repeat_funnel_audit(self):
        chosen = self.brain.candidates(state())[0]
        self.assertNotEqual(chosen.action, "income_funnel_audit")


if __name__ == "__main__":
    unittest.main()
