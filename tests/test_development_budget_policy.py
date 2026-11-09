import unittest

from core.development_budget_policy import (
    MAX_DEVELOPMENT_REVENUE_SHARE,
    assess_development_budget,
)
from core.economic_master_agent import EconomicMasterAgent


def evidence(**changes):
    data = {
        "accounting_period": "2026-11",
        "currency": "USD",
        "provider_reconciliation_verified": True,
        "cost_records_verified": True,
        "settled_revenue": "1000",
        "operating_expenses": "400",
        "existing_commitments": "50",
        "protected_reserves": "100",
        "development_spend_to_date": "0",
        "proposed_development_cost": "300",
    }
    data.update(changes)
    return data


class DevelopmentBudgetTests(unittest.TestCase):
    def test_owner_ceiling_is_exactly_forty_percent(self):
        self.assertEqual(str(MAX_DEVELOPMENT_REVENUE_SHARE), "0.40")
        result = assess_development_budget(**evidence())
        self.assertTrue(result.eligible_for_owner_approval)
        self.assertEqual(result.maximum_from_revenue, "400.00")
        self.assertEqual(result.remaining_development_budget, "400.00")
        self.assertFalse(result.payment_authorized)

    def test_cannot_spend_forty_percent_when_expenses_leave_less_cash(self):
        result = assess_development_budget(**evidence(
            operating_expenses="650", existing_commitments="50",
            protected_reserves="200", proposed_development_cost="150",
        ))
        self.assertFalse(result.eligible_for_owner_approval)
        self.assertEqual(result.available_surplus_before_development, "100")
        self.assertEqual(result.remaining_development_budget, "100")

    def test_prior_development_spend_reduces_room(self):
        result = assess_development_budget(**evidence(
            development_spend_to_date="150", proposed_development_cost="300",
        ))
        self.assertFalse(result.eligible_for_owner_approval)
        self.assertEqual(result.remaining_development_budget, "250.00")

    def test_no_self_financing_on_operating_loss(self):
        result = assess_development_budget(**evidence(operating_expenses="1200"))
        self.assertFalse(result.eligible_for_owner_approval)
        self.assertEqual(result.remaining_development_budget, "0")

    def test_unsettled_revenue_is_not_a_budget(self):
        result = assess_development_budget(**evidence(
            provider_reconciliation_verified=False, settled_revenue="999999999",
        ))
        self.assertFalse(result.eligible_for_owner_approval)
        self.assertIsNone(result.maximum_from_revenue)

    def test_unverified_costs_fail_closed(self):
        result = assess_development_budget(**evidence(cost_records_verified=False))
        self.assertFalse(result.eligible_for_owner_approval)

    def test_missing_invalid_values_fail_closed(self):
        for value in (None, "-1", "NaN", "Infinity", 12.3, True):
            with self.subTest(value=value):
                result = assess_development_budget(**evidence(protected_reserves=value))
                self.assertFalse(result.eligible_for_owner_approval)

    def test_missing_period_or_currency_fail_closed(self):
        for change in ({"accounting_period": ""}, {"currency": ""}):
            with self.subTest(change=change):
                self.assertFalse(assess_development_budget(**evidence(**change)).eligible_for_owner_approval)

    def test_prior_spending_over_cap_blocks_any_new_spend(self):
        result = assess_development_budget(**evidence(development_spend_to_date="450", proposed_development_cost="1"))
        self.assertEqual(result.reason, "prior_development_spend_exceeds_allowed_budget")
        self.assertFalse(result.eligible_for_owner_approval)

    def test_economic_master_agent_exposes_budget_review_without_payment(self):
        result = EconomicMasterAgent().assess_development_request(**evidence())
        self.assertTrue(result.eligible_for_owner_approval)
        self.assertFalse(result.payment_authorized)


if __name__ == "__main__":
    unittest.main()
