"""Offline regression contract for the first 30 TRX Moj Prop educational product.

Pure tests: no database, network, customer, external settlement or trading.
"""
import unittest

from scripts.mojprop_starter30 import (
    InvalidJournal, PRODUCT_ID, PRICE_TRX, PRICE_SUN,
    assess_journal, public_product
)


def journal(amount="100.00", n=10):
    return [{"session": i, "closing_equity_usd": amount,
             "risk_plan_recorded": True, "reflection_recorded": True}
            for i in range(1, n + 1)]


class Starter30ContractTests(unittest.TestCase):
    def test_id_is_stable(self):
        self.assertEqual(PRODUCT_ID, "MOJPROP-STARTER30")

    def test_price_trx_is_exact(self):
        self.assertEqual(PRICE_TRX, 30)

    def test_price_uses_integer_sun(self):
        self.assertEqual(PRICE_SUN, 30_000_000)

    def test_no_checkout_or_charge_claim(self):
        self.assertFalse(public_product()["automatic_checkout"])
        self.assertFalse(public_product()["charge_approved"])

    def test_no_real_funding_or_brokerage(self):
        for k in ("funded_account", "withdrawals", "profit_sharing", "broker_account", "investment_service"):
            self.assertIs(public_product()[k], False, k)

    def test_manual_request_only(self):
        self.assertEqual(public_product()["availability"],
                         "request_only_until_legal_payment_and_delivery_proof")

    def test_has_concrete_deliverables(self):
        self.assertEqual(len(public_product()["deliverables"]), 3)

    def test_stable_single_agent(self):
        self.assertEqual(public_product()["operator"], "mojtaba.bot.ai")

    def test_completed_risk_compliant_educational_log(self):
        result = assess_journal(journal())
        self.assertEqual(result["status"], "completed_educational_review")
        self.assertEqual(result["rule_breaches"], [])
        self.assertEqual(result["documented_sessions"], 10)

    def test_short_log_is_not_completed(self):
        self.assertEqual(assess_journal(journal(n=9))["status"], "incomplete_training")

    def test_no_sessions_denied(self):
        with self.assertRaises(InvalidJournal):
            assess_journal([])

    def test_eleven_sessions_denied(self):
        with self.assertRaises(InvalidJournal):
            assess_journal(journal(n=11))

    def test_tuple_denied(self):
        with self.assertRaises(InvalidJournal):
            assess_journal(tuple(journal()))

    def test_missing_field_denied(self):
        rows = journal()
        del rows[0]["reflection_recorded"]
        with self.assertRaises(InvalidJournal):
            assess_journal(rows)

    def test_unexpected_field_denied(self):
        rows = journal()
        rows[0]["paid"] = True
        with self.assertRaises(InvalidJournal):
            assess_journal(rows)

    def test_reordered_session_denied(self):
        rows = journal()
        rows[1]["session"] = 3
        with self.assertRaises(InvalidJournal):
            assess_journal(rows)

    def test_bool_session_denied(self):
        rows = journal()
        rows[0]["session"] = True
        with self.assertRaises(InvalidJournal):
            assess_journal(rows)

    def test_non_boolean_flag_denied(self):
        rows = journal()
        rows[0]["risk_plan_recorded"] = "yes"
        with self.assertRaises(InvalidJournal):
            assess_journal(rows)

    def test_float_money_denied(self):
        rows = journal()
        rows[0]["closing_equity_usd"] = 100.00
        with self.assertRaises(InvalidJournal):
            assess_journal(rows)

    def test_negative_money_denied(self):
        rows = journal("-1")
        with self.assertRaises(InvalidJournal):
            assess_journal(rows)

    def test_exponent_money_denied(self):
        rows = journal("1e2")
        with self.assertRaises(InvalidJournal):
            assess_journal(rows)

    def test_nan_money_denied(self):
        rows = journal("NaN")
        with self.assertRaises(InvalidJournal):
            assess_journal(rows)

    def test_infinity_money_denied(self):
        rows = journal("Infinity")
        with self.assertRaises(InvalidJournal):
            assess_journal(rows)

    def test_high_precision_denied(self):
        rows = journal("100.001")
        with self.assertRaises(InvalidJournal):
            assess_journal(rows)

    def test_amount_with_space_denied(self):
        rows = journal(" 100.00")
        with self.assertRaises(InvalidJournal):
            assess_journal(rows)

    def test_exact_daily_loss_limit_is_allowed(self):
        rows = journal()
        rows[0]["closing_equity_usd"] = "97.00"
        for row in rows[1:]:
            row["closing_equity_usd"] = "97.00"
        self.assertEqual(assess_journal(rows)["rule_breaches"], [])

    def test_above_daily_loss_limit_is_flagged(self):
        rows = journal()
        rows[0]["closing_equity_usd"] = "96.99"
        for row in rows[1:]:
            row["closing_equity_usd"] = "96.99"
        result = assess_journal(rows)
        self.assertIn({"session": 1, "rule": "daily_loss"}, result["rule_breaches"])
        self.assertEqual(result["status"], "completed_needs_coaching")

    def test_peak_drawdown_is_flagged(self):
        rows = journal()
        for i, amount in enumerate(["99", "98", "97", "96", "95", "94", "93", "93", "93", "93"]):
            rows[i]["closing_equity_usd"] = amount
        result = assess_journal(rows)
        self.assertIn({"session": 7, "rule": "overall_peak_drawdown"}, result["rule_breaches"])

    def test_journal_missing_reflection_is_flagged(self):
        rows = journal()
        rows[3]["reflection_recorded"] = False
        result = assess_journal(rows)
        self.assertIn({"session": 4, "rule": "reflection_missing"}, result["rule_breaches"])
        self.assertEqual(result["documented_sessions"], 9)

    def test_journal_missing_plan_is_flagged(self):
        rows = journal()
        rows[0]["risk_plan_recorded"] = False
        result = assess_journal(rows)
        self.assertIn({"session": 1, "rule": "risk_plan_missing"}, result["rule_breaches"])

    def test_no_real_trade_or_payment_or_funding_from_completion(self):
        result = assess_journal(journal())
        self.assertIs(result["funded_account_earned"], False)
        self.assertIs(result["payment_recorded"], False)
        self.assertIs(result["trades_executed"], False)

    def test_zero_balance_is_risk_breach_not_exception(self):
        result = assess_journal(journal("0.00"))
        self.assertIn({"session": 1, "rule": "daily_loss"}, result["rule_breaches"])

    def test_zero_then_zero_does_not_claim_second_daily_loss(self):
        rows = journal("0.00", n=3)
        result = assess_journal(rows)
        self.assertIn({"session": 1, "rule": "daily_loss"}, result["rule_breaches"])
        self.assertNotIn({"session": 2, "rule": "daily_loss"}, result["rule_breaches"])
        self.assertNotIn({"session": 3, "rule": "daily_loss"}, result["rule_breaches"])
        for session in (1, 2, 3):
            self.assertIn({"session": session, "rule": "overall_peak_drawdown"}, result["rule_breaches"])

    def test_recovery_after_zero_is_not_a_new_daily_loss(self):
        rows = journal("100.00", n=4)
        rows[0]["closing_equity_usd"] = "0.00"
        rows[1]["closing_equity_usd"] = "25.00"
        rows[2]["closing_equity_usd"] = "50.00"
        rows[3]["closing_equity_usd"] = "48.00"
        result = assess_journal(rows)
        self.assertIn({"session": 1, "rule": "daily_loss"}, result["rule_breaches"])
        self.assertNotIn({"session": 2, "rule": "daily_loss"}, result["rule_breaches"])
        self.assertNotIn({"session": 3, "rule": "daily_loss"}, result["rule_breaches"])
        self.assertIn({"session": 4, "rule": "daily_loss"}, result["rule_breaches"])
        self.assertEqual(result["status"], "incomplete_training")
        self.assertFalse(result["payment_recorded"])
        self.assertFalse(result["funded_account_earned"])

    def test_public_contract_is_serializable(self):
        import json
        self.assertEqual(json.loads(json.dumps(public_product()))["price_sun"], 30_000_000)


if __name__ == "__main__":
    unittest.main()
