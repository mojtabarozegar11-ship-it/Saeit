"""Read-only origin inventory contract; CI uses temporary fake roots only."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

from scripts.mpw_origin_release_readonly import inspect, status, PROBES, MAX_READ_BYTES


class OriginReadOnlyInventoryTests(TestCase):
    def test_probe_scope_is_explicit_and_bounded(self):
        self.assertEqual(len(PROBES), 15)
        self.assertEqual(len({probe[0] for probe in PROBES}), len(PROBES))
        self.assertTrue(all(isinstance(x[2], str) and ".." not in Path(x[2]).parts for x in PROBES))
        self.assertGreater(MAX_READ_BYTES, 5000)
        self.assertLess(MAX_READ_BYTES, 250000)

    def test_real_file_matching_without_following_other_paths(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "config"
            p.mkdir()
            (p / "urls.py").write_text('path("store/", store_home)\n', encoding="utf-8")
            self.assertEqual(status(Path(d), "config/urls.py", ('path("store/",',)), "matched")
            self.assertEqual(status(Path(d), "config/urls.py", ("unseen",)), "marker_missing")
            self.assertEqual(status(Path(d), "config/none.py", ()), "missing")

    def test_reject_file_symlinks(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "target").write_text("secret", encoding="utf-8")
            (root / "alias").symlink_to(root / "target")
            self.assertEqual(status(root, "alias", ()), "unsafe_symlink")

    def test_reject_parent_directory_symlinks(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "target").mkdir()
            (root / "target" / "a").write_text("x", encoding="utf-8")
            (root / "alias").symlink_to(root / "target", target_is_directory=True)
            self.assertEqual(status(root, "alias/a", ()), "unsafe_symlink")

    def test_reject_oversized_inputs(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "large").write_text("a" * (MAX_READ_BYTES + 1), encoding="utf-8")
            self.assertEqual(status(root, "large", ()), "oversized")

    def test_missing_root_is_not_reported_ready(self):
        with TemporaryDirectory() as d:
            self.assertEqual(status(Path(d) / "absent", "file.py", ()), "root_unavailable")

    def test_summary_never_grants_deployment_or_payment(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "file.py").write_text("ready", encoding="utf-8")
            result = inspect((("a", root, "file.py", ("ready",)),))
            self.assertEqual(result["matched_file_probes"], 1)
            for key in ("release_authorized", "payment_authorized",
                        "production_isolation_verified", "server_files_modified",
                        "invoice_or_order_accessed"):
                self.assertIs(result[key], False)

    def test_missing_probes_visible_without_secret_paths(self):
        with TemporaryDirectory() as d:
            result = inspect((("a", Path(d), "missing", ()),))
            self.assertEqual(result["observations"], {"a": "missing"})
            self.assertNotIn(str(d), str(result))

    def test_no_django_or_network_module_import_side_effects(self):
        source = (Path(__file__).resolve().parents[1] / "scripts/mpw_origin_release_readonly.py").read_text()
        for forbidden in ("django.setup", "import requests", "urlopen(",
                          "import subprocess", "from subprocess", ".write_text(", ".unlink(", "os.system(",
                          "PaymentIntent.objects", "Order.objects"):
            self.assertNotIn(forbidden, source)

    def test_workflow_is_manual_only_and_uses_pinned_direct_runner(self):
        file = Path(__file__).resolve().parents[1] / ".github/workflows/vps-to-cpanel-ssh-readonly-20261112.yml"
        source = file.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", source)
        self.assertNotIn("\n  push:", source)
        self.assertNotIn("\n  pull_request:", source)
        self.assertIn("self-hosted, factory-vps", source)
        self.assertIn("StrictHostKeyChecking=yes", source)
        self.assertIn("PYTHONDONTWRITEBYTECODE=1 python3 -B -", source)
        self.assertIn("mpw_origin_release_readonly.py", source)
