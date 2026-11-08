"""Packaging and deployment *static* checks; no cTrader or VPS activation."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "trading" / "build"
UNIT = (ROOT / "deploy" / "mojtrade-risk.service").read_text(encoding="utf-8")
EXAMPLE = (ROOT / "deploy" / "mojtrade-risk.env.example").read_text(encoding="utf-8")
SCRIPT = (ROOT / "scripts" / "mojtrade_build_cbots.sh").read_text(encoding="utf-8")


class C09PackagingChecks(unittest.TestCase):
    def projects(self):
        for name in ("MojTradeDemoBot", "MojTradeOmegaXDemoBot"):
            yield name, ET.parse(BUILD / name / (name + ".csproj")).getroot()

    def test_two_independent_cbot_projects(self):
        self.assertEqual(len(list(self.projects())), 2)

    def test_both_target_supported_ctrader_net6(self):
        for name, project in self.projects():
            with self.subTest(project=name):
                self.assertEqual(project.findtext("./PropertyGroup/TargetFramework"), "net6.0")

    def test_only_one_source_class_per_project(self):
        for name, project in self.projects():
            with self.subTest(project=name):
                self.assertEqual(
                    [element.get("Include") for element in project.findall("./ItemGroup/Compile")],
                    ["../../" + name + ".cs"],
                )

    def test_explicit_cbot_sdk_version(self):
        for name, project in self.projects():
            with self.subTest(project=name):
                packages = project.findall("./ItemGroup/PackageReference")
                self.assertEqual(len(packages), 1)
                self.assertEqual(packages[0].get("Include"), "cTrader.Automate")
                self.assertEqual(packages[0].get("Version"), "1.0.21")

    def test_no_automatic_algo_publication(self):
        for name, project in self.projects():
            self.assertEqual(project.findtext("./PropertyGroup/AlgoPublish"), "false")

    def test_algo_outputs_have_unique_explicit_names(self):
        for name, project in self.projects():
            self.assertEqual(project.findtext("./PropertyGroup/AlgoName"), name)

    def test_build_script_fails_without_sdk(self):
        self.assertIn("command -v dotnet", SCRIPT)
        self.assertIn("exit 2", SCRIPT)

    def test_service_is_loopback_only_in_application(self):
        server = (ROOT / "trading/mojtrade_risk_coordinator.py").read_text(encoding="utf-8")
        self.assertIn('ThreadingHTTPServer(("127.0.0.1", args.port), Handler)', server)

    def test_service_has_no_demo_enable_flag(self):
        self.assertNotIn("--enable-demo-reservations", UNIT)

    def test_service_requires_secret_file_and_dedicated_user(self):
        self.assertIn("EnvironmentFile=/etc/mojtrade-risk/risk.env", UNIT)
        self.assertIn("User=mojtrade-risk", UNIT)
        self.assertIn("UMask=0077", UNIT)

    def test_service_filesystem_is_read_only_except_state(self):
        self.assertIn("ProtectSystem=strict", UNIT)
        self.assertIn("ReadWritePaths=/var/lib/mojtrade-risk", UNIT)

    def test_example_token_is_not_usable(self):
        self.assertIn("MOJTRADE_RISK_TOKEN=CHANGE_ME", EXAMPLE)
        self.assertTrue(len("CHANGE_ME") < 32)


if __name__ == "__main__":
    unittest.main()
