import unittest

from core.economic_master_agent import EconomicMasterAgent


def evidence(**overrides):
    params = {
        "settled_cash": "1000",
        "protected_reserves": "100",
        "monthly_budget": "450",
        "month_to_date_spend": "0",
        "amount": "200",
        "vendor": "approved-host",
        "approved_vendors": {"approved-host"},
        "expense_type": "infrastructure",
        "account_currency": "USD",
        "development_financial_evidence": {
            "accounting_period": "2026-11",
            "currency": "USD",
            "provider_reconciliation_verified": True,
            "cost_records_verified": True,
            "settled_revenue": "1000",
            "operating_expenses": "300",
            "existing_commitments": "100",
            "protected_reserves": "100",
            "development_spend_to_date": "0",
        },
        "owner_approval_reference": "owner-case-17",
        "owner_approval_checker": lambda **case: case == {
            "approval_reference": "owner-case-17",
            "expense_type": "infrastructure",
            "vendor": "approved-host",
            "amount": "200",
            "currency": "USD",
            "accounting_period": "2026-11",
        },
    }
    params.update(overrides)
    return params


class MasterDevelopmentSpendingTests(unittest.TestCase):
    def setUp(self):
        self.agent = EconomicMasterAgent()

    def test_no_development_budget_is_fail_closed(self):
        params = evidence()
        del params["development_financial_evidence"]
        self.assertEqual(
            self.agent.authorize_self_funded_expense(**params).reason,
            "development_budget_evidence_required",
        )

    def test_valid_development_request_requires_verified_owner_case(self):
        decision = self.agent.authorize_self_funded_expense(**evidence())
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "development_eligible_with_verified_owner_case_approval")

    def test_missing_or_false_case_approval_is_blocked(self):
        for checker in (lambda **case: False, lambda **case: "true"):
            with self.subTest(checker=checker):
                decision = self.agent.authorize_self_funded_expense(**evidence(
                    owner_approval_checker=checker,
                ))
                self.assertFalse(decision.allowed)

    def test_default_checker_without_real_django_grant_is_fail_closed(self):
        self.assertFalse(self.agent.authorize_self_funded_expense(**evidence(
            owner_approval_checker=None,
        )).allowed)

    def test_checker_exception_is_fail_closed(self):
        def fail(**case):
            raise OSError("approval service down")
        self.assertFalse(self.agent.authorize_self_funded_expense(**evidence(
            owner_approval_checker=fail,
        )).allowed)

    def test_cash_and_vendor_gate_still_apply(self):
        for change in ({"monthly_budget": "100"}, {"vendor": "unknown"},
                       {"settled_cash": "100"}):
            with self.subTest(change=change):
                self.assertFalse(self.agent.authorize_self_funded_expense(**evidence(**change)).allowed)

    def test_development_cap_uses_actual_expense_amount(self):
        params = evidence(amount="401")
        params["development_financial_evidence"]["proposed_development_cost"] = "1"
        self.assertEqual(
            self.agent.authorize_self_funded_expense(**params).reason,
            "proposed_cost_exceeds_40_percent_or_free_surplus",
        )

    def test_low_operating_surplus_blocks_infrastructure(self):
        params = evidence()
        params["development_financial_evidence"]["operating_expenses"] = "750"
        self.assertFalse(self.agent.authorize_self_funded_expense(**params).allowed)

    def test_unverified_revenue_blocks_without_owner_checker_call(self):
        called = []
        params = evidence(owner_approval_checker=lambda **case: called.append(case))
        params["development_financial_evidence"]["provider_reconciliation_verified"] = False
        self.assertFalse(self.agent.authorize_self_funded_expense(**params).allowed)
        self.assertEqual(called, [])

    def test_mismatched_account_currency_blocks_before_approval(self):
        self.assertEqual(self.agent.authorize_self_funded_expense(**evidence(
            account_currency="TRX",
        )).reason, "accounting_currency_mismatch_or_missing")

    def test_business_software_is_development_too(self):
        self.assertEqual(
            self.agent.authorize_self_funded_expense(**evidence(
                expense_type="business_software",
            )).reason,
            "specific_owner_approval_not_verified",
        )

    def test_existing_subscription_retains_roi_budget_gate(self):
        decision = self.agent.authorize_self_funded_expense(**{
            "settled_cash": "100",
            "protected_reserves": "40",
            "monthly_budget": "50",
            "month_to_date_spend": "0",
            "amount": "10",
            "vendor": "approved-host",
            "approved_vendors": {"approved-host"},
            "expense_type": "subscription",
            "subscription_active": True,
            "usage_evidence": True,
            "roi_evidence": True,
        })
        self.assertTrue(decision.allowed)


if __name__ == "__main__":
    unittest.main()
