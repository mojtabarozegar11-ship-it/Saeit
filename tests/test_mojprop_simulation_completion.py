from decimal import Decimal as D
from types import SimpleNamespace
from unittest import TestCase
from prop_firm.simulation_completion import completion_evidence, review_completion

class SimulationCompletionTests(TestCase):
    def state(self, **overrides):
        return SimpleNamespace(**(dict(blocked=False,positions={},pending={},closed_trade_count=50,
            realized_pnl=D("100"),realized_by_day={"day1":D("32"),"day2":D("23"),"day3":D("23"),"day4":D("22")}) | overrides))
    def test_exact_necessary_boundaries_do_not_certify_pass(self):
        self.assertEqual(completion_evidence(self.state(),expired=True),())
    def test_49_trades_definite_failure(self):
        self.assertIn("minimum_closed_positions_not_met",completion_evidence(self.state(closed_trade_count=49),expired=True))
    def test_best_day_above_32_percent_fails(self):
        self.assertIn("best_day_share_exceeds_limit",completion_evidence(self.state(realized_by_day={"day1":D("32.01")}),expired=True))
    def test_nonpositive_net_fails(self):
        self.assertIn("positive_net_profit_not_met",completion_evidence(self.state(realized_pnl=D("0")),expired=True))
    def test_open_positions_require_review(self):
        self.assertEqual(completion_evidence(self.state(positions={"open":1},closed_trade_count=1),expired=True),())
    def test_pending_orders_require_review(self):
        self.assertEqual(completion_evidence(self.state(pending={"pending":1},closed_trade_count=1),expired=True),())
    def test_no_early_failure_from_incomplete_targets(self):
        self.assertEqual(completion_evidence(self.state(closed_trade_count=0),expired=False),())
    def test_drawdown_is_definite_failure_before_expiry(self):
        self.assertEqual(completion_evidence(self.state(blocked=True),expired=False),("drawdown_limit_reached",))

    def test_review_missing_target(self):
        result=review_completion(self.state(),expired=True)
        self.assertEqual(result["state"],"review_required")
        self.assertFalse(result["pass_attested"])
    def test_review_target_below_required_profit(self):
        result=review_completion(self.state(),expired=True,reviewed_profit_target_pct=D("11"))
        self.assertEqual(result["state"],"failed")
        self.assertFalse(result["pass_attested"])
    def test_review_candidate_never_attests_pass(self):
        result=review_completion(self.state(),expired=True,reviewed_profit_target_pct=D("10"))
        self.assertEqual(result["state"],"pass_candidate")
        self.assertFalse(result["pass_attested"])
    def test_invalid_review_targets(self):
        for target in (None,True,10,D("NaN"),D("Infinity"),D("0"),D("-1")):
            self.assertEqual(review_completion(self.state(),expired=True,reviewed_profit_target_pct=target)["state"],"review_required")
    def test_review_pending_positions_no_pass(self):
        result=review_completion(self.state(positions={"open":1}),expired=True,reviewed_profit_target_pct=D("10"))
        self.assertEqual(result["state"],"review_required")
    def test_review_early_no_pass(self):
        result=review_completion(self.state(),expired=False,reviewed_profit_target_pct=D("10"))
        self.assertEqual(result["state"],"in_progress")
