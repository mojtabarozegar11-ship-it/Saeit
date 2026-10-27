import unittest

from core.self_funding_policy import authorize_operating_expense


BASE = dict(
    settled_cash="100", protected_reserves="30", monthly_budget="40",
    month_to_date_spend="5", amount="10", vendor="host",
    approved_vendors={"host"}, expense_type="infrastructure",
)


class SelfFundingTests(unittest.TestCase):
  def test_budgeted_expense_can_be_paid_from_settled_revenue(self):
    self.assertTrue(authorize_operating_expense(**BASE).allowed)


  def test_expense_cannot_touch_protected_reserve(self):
    result = authorize_operating_expense(**(BASE | {"amount": "71"}))
    self.assertFalse(result.allowed)
    self.assertEqual(result.reason, "would_spend_protected_reserve_or_unsettled_cash")


  def test_expense_cannot_exceed_monthly_budget(self):
    result = authorize_operating_expense(**(BASE | {"month_to_date_spend": "35"}))
    self.assertFalse(result.allowed)
    self.assertEqual(result.reason, "monthly_budget_exceeded")


  def test_subscription_needs_usage_and_roi_evidence(self):
    data = BASE | {"expense_type": "subscription", "usage_evidence": True}
    result = authorize_operating_expense(**data)
    self.assertFalse(result.allowed)
    self.assertEqual(result.reason, "subscription_requires_active_use_and_roi_evidence")
    self.assertTrue(authorize_operating_expense(**(data | {"roi_evidence": True})).allowed)


  def test_unapproved_vendor_and_invalid_money_fail_closed(self):
    self.assertFalse(authorize_operating_expense(**(BASE | {"vendor": "unknown"})).allowed)
    self.assertFalse(authorize_operating_expense(**(BASE | {"settled_cash": "NaN"})).allowed)


if __name__ == "__main__":
  unittest.main()
