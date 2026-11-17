"""C159 prospective owner-approved XAUUSD risk tests; NO broker or customer APIs."""
from dataclasses import FrozenInstanceError
from decimal import Decimal
import unittest

from prop_firm.owner_gold_risk_v13 import (
    OWNER_GOLD_CONTRACT_VERSION, OWNER_GOLD_V13, risk_terms_summary,
)
from prop_firm.plan1_gold_disclosure_v13 import (
    proposed_disclosure_v13, SKU, SCHEMA,
)
from prop_firm.rules import POLICY, authorize_order, LEVELS
from prop_firm.plans import plan_for_code
from prop_firm.policy_integrity import policy_drift_defects


class C159OwnerGoldRisk(unittest.TestCase):
    def evaluate(self, **change):
        data=dict(
            account_capital="100", equity="100", day_open_equity="100",
            risk_at_stop="1", open_risk_before="0",
            broker_minimum_risk="0.1", verified_stop=True,
            authoritative_snapshot=True, mode="challenge",
            contract_version=OWNER_GOLD_CONTRACT_VERSION,
            broker_symbol="XAUUSD", broker_symbol_verified=True,
        )
        data.update(change)
        return authorize_order(**data)

    def test_01_new_terms_are_exact_and_not_payable(self):
        self.assertEqual(OWNER_GOLD_V13.max_per_order_risk_pct,Decimal("3"))
        self.assertEqual(OWNER_GOLD_V13.max_aggregate_open_risk_pct,Decimal("8"))
        self.assertEqual(OWNER_GOLD_V13.exact_broker_symbol,"XAUUSD")
        self.assertFalse(OWNER_GOLD_V13.checkout_enabled)
        self.assertFalse(OWNER_GOLD_V13.real_execution_enabled)
        self.assertTrue(OWNER_GOLD_V13.requires_new_buyer_consent)

    def test_02_old_v12_08_and_16_limits_are_unchanged(self):
        self.assertEqual(POLICY.version,"2026-11-15/v1.2")
        self.assertEqual(POLICY.order_risk_pct,Decimal("0.8"))
        self.assertEqual(POLICY.aggregate_risk_pct,Decimal("1.6"))
        self.assertTrue(self.evaluate(contract_version=None,
                                      risk_at_stop="0.8",
                                      broker_symbol=None,
                                      broker_symbol_verified=False).allowed)
        old=self.evaluate(contract_version=POLICY.version,risk_at_stop="0.81")
        self.assertIn("per_order_risk_limit",old.reasons)

    def test_03_new_3pct_exact_trade_at_high_enough_equity_is_allowed_in_challenge(self):
        r=self.evaluate(risk_at_stop="3")
        self.assertTrue(r.allowed,r.reasons)
        self.assertEqual(r.daily_equity_floor,Decimal("96"))
        self.assertEqual(r.total_equity_floor,Decimal("92"))

    def test_04_new_3pct_plus_one_cent_still_denied(self):
        r=self.evaluate(risk_at_stop="3.01")
        self.assertFalse(r.allowed)
        self.assertIn("per_order_risk_limit",r.reasons)

    def test_05_8pct_open_limit_at_exact_boundary_only_if_headroom(self):
        r=self.evaluate(equity="115",day_open_equity="110",
                        open_risk_before="5",risk_at_stop="3")
        self.assertTrue(r.allowed,r.reasons)
        self.assertEqual(r.daily_equity_floor,Decimal("106"))

    def test_06_8pct_exceeded_is_denied_even_if_headroom(self):
        r=self.evaluate(equity="115",day_open_equity="110",
                        open_risk_before="5.01",risk_at_stop="3")
        self.assertFalse(r.allowed)
        self.assertIn("aggregate_risk_limit",r.reasons)
        self.assertNotIn("stop_risk_exceeds_drawdown_headroom",r.reasons)

    def test_07_4pct_daily_drawdown_stricter_than_8pct_static(self):
        r=self.evaluate(open_risk_before="1.2",risk_at_stop="3")
        self.assertFalse(r.allowed)
        self.assertIn("stop_risk_exceeds_drawdown_headroom",r.reasons)
        self.assertNotIn("per_order_risk_limit",r.reasons)
        self.assertNotIn("aggregate_risk_limit",r.reasons)

    def test_08_daily_exact_stop_at_floor_is_denied(self):
        r=self.evaluate(equity="99",open_risk_before="0",risk_at_stop="3")
        self.assertFalse(r.allowed)
        self.assertIn("stop_risk_exceeds_drawdown_headroom",r.reasons)
        self.assertEqual(r.daily_equity_floor,Decimal("96"))

    def test_09_total_loss_8pct_floor_remains_independent(self):
        r=self.evaluate(day_open_equity="94",equity="94",
                        risk_at_stop="2",open_risk_before="0")
        self.assertFalse(r.allowed)
        self.assertEqual(r.total_equity_floor,Decimal("92"))
        self.assertIn("stop_risk_exceeds_drawdown_headroom",r.reasons)

    def test_10_breached_equity_blocks_without_order(self):
        r=self.evaluate(equity="96",risk_at_stop="0.1")
        self.assertFalse(r.allowed)
        self.assertIn("daily_loss_floor_reached",r.reasons)

    def test_11_only_exact_XAUUSD_symbol_approved(self):
        for name in ("XAUUSDm","xauusd","XAU/USD","XAUUSD.a",
                     "EURUSD","GOLD",""," XAUUSD","XAUUSD ",
                     "XAUUSD\x00",None,True):
            with self.subTest(symbol=name):
                r=self.evaluate(broker_symbol=name)
                self.assertFalse(r.allowed)
                self.assertIn("xauusd_exact_broker_symbol_required",r.reasons)

    def test_12_broker_verification_must_be_actual_boolean_true(self):
        for flag in (False,None,1,"yes",0):
            with self.subTest(flag=flag):
                r=self.evaluate(broker_symbol_verified=flag)
                self.assertFalse(r.allowed)
                self.assertIn("broker_symbol_independent_verification_required",r.reasons)

    def test_13_missing_authoritative_snapshot_never_trades(self):
        r=self.evaluate(authoritative_snapshot=False)
        self.assertFalse(r.allowed)
        self.assertIn("authoritative_broker_snapshot_required",r.reasons)

    def test_14_missing_real_stop_loss_never_trades(self):
        r=self.evaluate(verified_stop=False)
        self.assertFalse(r.allowed)
        self.assertIn("stop_loss_required",r.reasons)

    def test_15_broker_minimum_lot_must_fit_single_order(self):
        r=self.evaluate(broker_minimum_risk="2",risk_at_stop="1")
        self.assertFalse(r.allowed)
        self.assertIn("broker_minimum_lot_not_feasible",r.reasons)

    def test_16_real_orders_remain_disabled_despite_any_owner_flags(self):
        r=self.evaluate(mode="real",execution_authorized=True)
        self.assertFalse(r.allowed)
        self.assertIn("real_execution_disabled",r.reasons)
        self.assertFalse(POLICY.real_orders_enabled)

    def test_17_unknown_contract_does_not_fall_back_to_new_cap(self):
        for v in ("2026-11-14/v1.1","2026-11-17/v1.3-preview",
                  "","invalid",0,True):
            with self.subTest(version=v),self.assertRaises(ValueError):
                self.evaluate(contract_version=v)

    def test_18_float_nan_negative_or_overflow_input_never_accepted(self):
        for value in (-1.2,True,"NaN","Infinity","-3"):
            with self.subTest(value=value),self.assertRaises(ValueError):
                self.evaluate(risk_at_stop=value)

    def test_19_historical_plan1_disclosure_and_integrity_not_rewritten(self):
        plan=plan_for_code("MOJ-PROP-01")
        self.assertEqual(plan.max_risk_per_trade_pct,Decimal("0.8"))
        self.assertEqual(plan.max_open_risk_pct,Decimal("1.6"))
        self.assertEqual(policy_drift_defects(),())
        self.assertEqual(LEVELS[0],Decimal("100"))
        self.assertEqual(LEVELS[-1],Decimal("100000"))

    def test_20_new_source_summary_has_no_commercial_release(self):
        s=risk_terms_summary()
        self.assertEqual(s["symbol"],"XAUUSD")
        self.assertEqual(s["risk_per_trade_percent"],"3")
        self.assertEqual(s["aggregate_open_risk_percent"],"8")
        self.assertTrue(s["historical_v12_unchanged"])
        self.assertFalse(s["checkout_enabled"])
        self.assertFalse(s["real_execution_enabled"])
        self.assertFalse(s["independent_capital_broker_legal_approval_verified"])

    def test_21_immutable_risk_profile_cannot_be_modified_after_review(self):
        with self.assertRaises(FrozenInstanceError):
            OWNER_GOLD_V13.max_per_order_risk_pct=Decimal("50")

    def test_22_prospective_bilingual_buyer_terms_are_deterministic(self):
        d=proposed_disclosure_v13()
        self.assertEqual(d,proposed_disclosure_v13())
        self.assertEqual(d.schema,SCHEMA)
        self.assertEqual(d.sku,SKU)
        self.assertEqual(d.contract_version,OWNER_GOLD_CONTRACT_VERSION)
        self.assertEqual(len(d.sha256_digest),64)
        self.assertEqual(d.native_fee_sun,30_000_000)
        self.assertEqual(d.trader_profit_share_pct,"70")
        self.assertEqual(d.company_profit_share_pct,"30")

    def test_23_disclosure_truthfully_explains_gold_and_dynamic_limits(self):
        d=proposed_disclosure_v13()
        for part in ("XAUUSD","3%","8%","4%","30 native TRX","USD 100"):
            self.assertIn(part,d.en)
        for part in ("XAUUSD","۳٪","۸٪","۴٪","۳۰","۱۰۰"):
            self.assertIn(part,d.fa)
        self.assertIn("v1.2",d.en)
        self.assertIn("v1.3",d.en)
        self.assertIn("CONDITIONAL",d.en)

    def test_24_disclosure_never_invoices_or_creates_a_funded_buyer(self):
        d=proposed_disclosure_v13()
        for field in ("buyer_accepted","legal_approved",
                      "broker_symbol_verified","account_funding_verified",
                      "payment_enabled","invoice_issued","actual_order_enabled"):
            self.assertIs(getattr(d,field),False)
        self.assertEqual(d.status,"PROPOSED_REQUIRES_SIGNED_NEW_CONTRACT")
        self.assertFalse(POLICY.trx_checkout_enabled)

    def test_25_real_closed_equity_risk_historical_default_still_enforced(self):
        d=self.evaluate(contract_version=None, risk_at_stop="0.7",
                        open_risk_before="1")
        self.assertFalse(d.allowed)
        self.assertIn("aggregate_risk_limit",d.reasons)

    def test_26_v13_requires_exact_typing_and_zero_risk_denied(self):
        d=self.evaluate(risk_at_stop="0")
        self.assertFalse(d.allowed)
        self.assertIn("per_order_risk_limit",d.reasons)

if __name__=="__main__":
    unittest.main()
