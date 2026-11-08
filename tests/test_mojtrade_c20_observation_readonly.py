"""C20 source regression: disabled demo trading cannot mutate open positions."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1] / "trading"
SCALP = (ROOT / "MojTradeDemoBot.cs").read_text(encoding="utf-8")
OMEGA = (ROOT / "MojTradeOmegaXDemoBot.cs").read_text(encoding="utf-8")


def on_tick_body(source: str) -> str:
    """Slice the handler before the next override without C# parsing deps."""
    match = re.search(r"protected override void OnTick\(\)\s*\{(?P<body>.*?)"
                      r"(?=protected override void OnTimer\(\))", source, re.S)
    if not match:
        raise AssertionError("OnTick handler not found")
    return match.group("body")


class ReadonlyObservationContract(unittest.TestCase):
    def test_both_bots_have_readonly_default_flags(self):
        for source in (SCALP, OMEGA):
            self.assertRegex(source, r'\[Parameter\("Enable Coordinated Demo Trading", DefaultValue = false\)\]')
        self.assertRegex(OMEGA, r'\[Parameter\("Enable Demo Trading", DefaultValue = false\)\]')

    def test_scalp_tick_gates_trailing_before_mutation(self):
        body = on_tick_body(SCALP)
        self.assertRegex(body, r'if\s*\(_halted\s*\|\|\s*!EnableCoordinatedDemoTrading\s*\|\|\s*'
                               r'!CoordinatorConfigured\(\)\)\s*return;')
        self.assertLess(body.index("CoordinatorConfigured()"),
                        body.index("ManageOpenPositions()"))

    def test_omega_tick_gates_trailing_before_mutation(self):
        body = on_tick_body(OMEGA)
        self.assertRegex(body, r'if\s*\(_halted\s*\|\|\s*!EnableDemoTrading\s*\|\|\s*'
                               r'!EnableCoordinatedDemoTrading\s*\|\|\s*'
                               r'!CoordinatorConfigured\(\)\)\s*return;')
        self.assertLess(body.index("CoordinatorConfigured()"), body.index("foreach"))

    def test_live_account_is_guarded_before_trailing(self):
        for source in (SCALP, OMEGA):
            body = on_tick_body(source)
            self.assertLess(body.index("Account.IsLive"),
                            body.index("CoordinatorConfigured()"))

    def test_mutation_sites_stay_limited_to_demo_risk_controlled_paths(self):
        self.assertEqual(SCALP.count("ManageOpenPositions();"), 1)
        self.assertEqual(OMEGA.count("foreach (var position in Positions.FindAll(Label, SymbolName))"), 1)


if __name__ == "__main__":
    unittest.main()
