"""Regressions for the restricted read-only VPS host-policy reporter."""
import ast
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from deploy import mojtaba_vps_host_policy_readonly_20261122 as audit


class VPSReadOnlyHostPolicyTests(TestCase):
    def test_cpu_max_unlimited_with_period(self):
        self.assertEqual(audit.cpu_max("max 100000"),
                         {"mode": "unlimited", "quota": None, "period": 100000})

    def test_cpu_max_bounded(self):
        self.assertEqual(audit.cpu_max("25000 100000"),
                         {"mode": "limited", "quota": 25000, "period": 100000})

    def test_cpu_max_no_period_fail_closed(self):
        self.assertEqual(audit.cpu_max("max")["mode"], "unknown")

    def test_cpu_max_zero_period_fail_closed(self):
        self.assertEqual(audit.cpu_max("25000 0")["mode"], "unknown")

    def test_cpu_max_injection_fail_closed(self):
        self.assertEqual(audit.cpu_max("max 100000\nSECRET")["mode"], "unknown")

    def test_cgroup_v2_normal_path(self):
        self.assertEqual(audit.cgroup_relative("0::/system.slice/factory.service\n"),
                         ("system.slice", "factory.service"))

    def test_cgroup_v2_root(self):
        self.assertEqual(audit.cgroup_relative("0::/\n"), ())

    def test_cgroup_v2_reject_dotdot(self):
        self.assertIsNone(audit.cgroup_relative("0::/service/../../private"))

    def test_cgroup_v2_reject_duplicate(self):
        self.assertIsNone(audit.cgroup_relative("0::/a\n0::/b"))

    def test_cgroup_v2_reject_external_or_control(self):
        for unsafe in ("2:cpu:/x", "0::x", "0:://x", "0::/bad name",
                       "0::/a/$HOME", "0::/a/%2f"):
            with self.subTest(unsafe=unsafe):
                self.assertIsNone(audit.cgroup_relative(unsafe))

    def test_cgroup_unlimited_mode(self):
        self.assertEqual(audit.mode_value("max"),
                         {"mode": "unlimited", "value": None})

    def test_cgroup_unknown_not_unlimited(self):
        self.assertEqual(audit.mode_value(None)["mode"], "unknown")
        self.assertEqual(audit.mode_value("not-a-limit")["mode"], "unknown")

    def test_nonnegative_bounded_and_no_pii(self):
        self.assertEqual(audit.nonnegative("14"), 14)
        self.assertIsNone(audit.nonnegative("14\nsecrets"))
        self.assertIsNone(audit.nonnegative("-1"))
        self.assertIsNone(audit.nonnegative(None))

    def test_os_release_only_two_allowlisted_values(self):
        with patch.object(audit, "bounded_read",
                          return_value='ID=ubuntu\nVERSION_ID="24.04"\n'
                                       'SECRET=private\nPRETTY_NAME="a secret"'):
            self.assertEqual(audit.release_info(),
                             {"id": "ubuntu", "version_id": "24.04"})

    def test_os_release_fixed_vendor_fallback_no_arbitrary_symlink(self):
        def controlled_read(path, *, limit=2048):
            if str(path) == "/etc/os-release":
                return None
            if str(path) == "/usr/lib/os-release":
                return "ID=ubuntu\nVERSION_ID=24.04"
            raise AssertionError("unexpected path read")
        with patch.object(audit, "bounded_read", side_effect=controlled_read):
            self.assertEqual(audit.release_info(),
                             {"id": "ubuntu", "version_id": "24.04"})

    def test_os_release_refuses_unbounded_name(self):
        with patch.object(audit, "bounded_read",
                          return_value='ID="../../bad"\nVERSION_ID="a b"'):
            self.assertEqual(audit.release_info(),
                             {"id": None, "version_id": None})

    def test_snapshot_never_claims_verified_sandbox(self):
        facts = audit.snapshot()
        self.assertTrue(facts["read_only"])
        self.assertFalse(facts["rootless_networkless_sandbox_attested"])
        self.assertFalse(facts["host_secrets_hidden_attested"])
        self.assertFalse(facts["worker_started_or_changed"])
        self.assertFalse(facts["package_installed_or_config_changed"])
        self.assertNotIn("token", repr(facts).casefold())
        self.assertNotIn("secret=", repr(facts).casefold())

    def test_no_subprocess_shell_network_or_write_apis(self):
        source = (Path(__file__).resolve().parents[1] / "deploy" /
                  "mojtaba_vps_host_policy_readonly_20261122.py").read_text()
        tree = ast.parse(source)
        forbidden_imports = {"subprocess", "socket", "requests", "urllib",
                             "shutil", "ctypes"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(all(x.name not in forbidden_imports
                                    for x in node.names))
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn(node.module, forbidden_imports)
        self.assertNotIn("os.system(", source)
        self.assertNotIn("subprocess.", source)
        self.assertNotIn("os.exec", source)
        self.assertNotIn("os.chmod", source)
        self.assertNotIn("mkdir(", source)
        self.assertNotIn("write_text(", source)
        self.assertNotIn("unlink(", source)

    def test_bounded_read_refuses_symlink(self):
        with patch.object(Path, "is_symlink", return_value=True):
            self.assertIsNone(audit.bounded_read(Path("/proc/forbidden")))

    def test_output_schema_is_fixed(self):
        self.assertEqual(audit.PREFIX, "MOJTABA_VPS_HOST_POLICY_READONLY=")
        self.assertEqual(audit.snapshot()["schema"],
                         "mojtaba.bot.ai.vps-host-policy.readonly.v1")
