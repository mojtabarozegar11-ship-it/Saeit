"""Source-only assertions for the zero-credential cBot compilation gate."""
from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/mojtrade-cbot-build.yml").read_text(encoding="utf-8")
SCRIPT = (ROOT / "scripts/mojtrade_build_cbots.sh").read_text(encoding="utf-8")


class C11CompileGateChecks(unittest.TestCase):
    def test_ci_uses_standard_linux_runner_and_dotnet_eight(self):
        self.assertIn("runs-on: ubuntu-24.04", WORKFLOW)
        self.assertIn("dotnet-version: '8.0.x'", WORKFLOW)

    def test_sdk_is_pinned_to_eight_only_inside_cbot_build_tree(self):
        config = json.loads((ROOT / "trading/build/global.json").read_text(encoding="utf-8"))
        self.assertEqual(config["sdk"]["version"], "8.0.100")
        self.assertEqual(config["sdk"]["rollForward"], "latestFeature")
        self.assertIn('cd "${root}/trading/build"', SCRIPT)

    def test_ci_is_read_only_and_does_not_keep_checkout_credential(self):
        self.assertIn("permissions:\n  contents: read", WORKFLOW)
        self.assertIn("persist-credentials: false", WORKFLOW)
        self.assertNotIn("secrets.", WORKFLOW)

    def test_ci_never_deploys_or_trades(self):
        self.assertNotIn("ctrader-cli run", WORKFLOW)
        self.assertNotIn("ssh ", WORKFLOW)
        self.assertNotIn("scp ", WORKFLOW)
        self.assertNotIn("systemctl", WORKFLOW)
        self.assertNotIn("ExecuteMarketOrder", WORKFLOW)

    def test_ci_bounds_duration_and_cancels_obsolete_builds(self):
        self.assertIn("timeout-minutes: 12", WORKFLOW)
        self.assertIn("cancel-in-progress: true", WORKFLOW)

    def test_ci_has_manual_entry_and_paths_filter(self):
        self.assertIn("workflow_dispatch:", WORKFLOW)
        self.assertIn("- 'fix/mojtrade-c*'", WORKFLOW)
        self.assertIn("- 'trading/build/**'", WORKFLOW)

    def test_build_requires_two_fresh_algo_artifacts(self):
        self.assertIn("for project in MojTradeDemoBot MojTradeOmegaXDemoBot", SCRIPT)
        self.assertIn("-newer \"${build_marker}\"", SCRIPT)
        self.assertIn("${#artifacts[@]} == 0", SCRIPT)
        self.assertIn('name "${project}.algo"', SCRIPT)
        self.assertIn("exit 3", SCRIPT)

    def test_build_prints_artifact_sha256_and_never_publishes(self):
        self.assertIn("sha256sum \"${artifact}\"", SCRIPT)
        self.assertIn("--no-incremental", SCRIPT)
        self.assertIn("--property:AlgoPublish=False", SCRIPT)


if __name__ == "__main__":
    unittest.main()
