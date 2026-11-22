"""Publishable Signal Desk lead-magnet safety and arithmetic checks.

Reads only public docs and a fictional educational CSV. No real market feed,
customer data, external HTTP, Django, payments or trading API is invoked.
"""
import csv
from decimal import Decimal
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "docs/mojprop/education"
ARTICLE = DIR / "signal-desk-free-scenario-sample.md"
RECORDS = DIR / "signal-desk-free-scenario-record.csv"


class SignalDeskEducationalAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.article = ARTICLE.read_text(encoding="utf-8")
        with RECORDS.open(newline="", encoding="utf-8") as file:
            cls.records = list(csv.DictReader(file))

    def test_01_article_is_clear_about_synthetic_unexecuted_status(self):
        text = self.article.lower()
        for label in ("demo-alpha", "invented", "not a real-time signal",
                      "no order was executed", "not an active automatic paid feed",
                      "no live price feed"):
            self.assertIn(label, text, label)

    def test_02_exactly_one_fictional_csv_record_no_realized_profit(self):
        self.assertEqual(len(self.records), 1)
        record = self.records[0]
        self.assertEqual(record["record_id"], "DEMO-ALPHA-20261122-001")
        self.assertEqual(record["example_only"], "true")
        self.assertEqual(record["is_live_market_data"], "false")
        self.assertEqual(record["market_data_source"], "synthetic_illustration_only")
        self.assertEqual(record["execution_status"], "no_order")
        self.assertEqual(record["realized_pnl_usd"], "")

    def test_03_risk_allocation_covers_cost_reserve(self):
        row = self.records[0]
        d = lambda key: Decimal(row[key])
        budget = d("simulated_balance_usd") * d("risk_budget_pct") / 100
        downside = d("planned_units") * d("risk_per_unit_usd") + d("cost_reserve_usd")
        self.assertEqual(budget, Decimal("10"))
        self.assertEqual(downside, Decimal("10"))
        self.assertEqual(downside, d("planned_downside_including_costs_usd"))
        self.assertLessEqual(downside, budget)
        self.assertEqual(d("risk_per_unit_usd"), d("reference_entry")-d("invalid_price"))

    def test_04_net_reward_to_risk_arithmetic_is_exact(self):
        row = self.records[0]
        d = lambda key: Decimal(row[key])
        upside = (d("objective_price") - d("reference_entry")) * d("planned_units")
        net_upside = upside - d("cost_reserve_usd")
        self.assertEqual(net_upside, Decimal("14"))
        self.assertEqual(net_upside, d("illustrative_net_upside_usd"))
        self.assertEqual(net_upside / d("planned_downside_including_costs_usd"),
                         d("net_reward_to_risk"))

    def test_05_real_service_is_unpaid_and_uses_only_central_portal(self):
        self.assertIn("https://mojplaywin.com/moj-prop-intake/?format=html&service=signals", self.article)
        self.assertIn("https://mojplaywin.com/moj-prop/signals/", self.article)
        self.assertIn("https://mojplaywin.com/mojtaba.bot.ai/", self.article)
        for text in ("does **not** create a paid subscription",
                     "Do not send TRX without an individual",
                     "do not send broker passwords", "no-trade", "not customer data"):
            self.assertIn(text.lower(), self.article.lower())

    def test_06_references_and_download_are_stable_public_paths(self):
        self.assertIn("./signal-desk-free-scenario-record.csv", self.article)
        self.assertIn("https://www.law.cornell.edu/cfr/text/17/4.41", self.article)
        self.assertIn("https://www.investor.gov/", self.article)
        self.assertIn("Simulated or hypothetical illustrations", self.article)

    def test_07_index_and_official_readme_refer_to_the_free_sample(self):
        index = (DIR / "README.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("./signal-desk-free-scenario-sample.md", index)
        self.assertIn("docs/mojprop/education/signal-desk-free-scenario-sample.md", readme)
        self.assertIn("Moj Prop Signal Desk — free educational terms", readme)


if __name__ == "__main__":
    unittest.main()
