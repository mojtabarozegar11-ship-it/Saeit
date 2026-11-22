"""Isolated guards for pinned, bounded native Zomorod-store source inspection."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/zomorod_cpanel_store_provenance_readonly_20261114.py"
RELAY = ROOT / "scripts/zomorod_cpanel_store_readonly_relay_20261114.sh"
SPEC = importlib.util.spec_from_file_location("store_attest", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class StoreProvenanceReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.root = Path(self.d.name)
        for rel in MOD.PATHS.values():
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)

    def populate(self, source=None):
        source = MOD.CSS_RULE + MOD.GRID_RULE + "zmStoreDb($private)" if source is None else source
        (self.root / MOD.PATHS["public_index"]).write_text(source, encoding="utf8")
        (self.root / MOD.PATHS["private_store_module"]).write_text("private catalog module", encoding="utf8")
        return source

    def test_reports_exact_hashes_and_both_css_markers(self):
        src = self.populate()
        result = MOD.inspect(self.root, enforce_home=False)
        self.assertEqual(result["public_index_sha256"], hashlib.sha256(src.encode()).hexdigest())
        self.assertTrue(result["active_css_pair_present"])
        self.assertTrue(result["active_file_has_native_db_call"])

    def test_old_css_cannot_claim_current_pair(self):
        self.populate(".grid article small.muted{overflow-wrap:anywhere}")
        r = MOD.inspect(self.root, enforce_home=False)
        self.assertFalse(r["active_css_pair_present"])
        self.assertFalse(r["active_file_grid_rule_present"])

    def test_missing_private_module_fails_closed(self):
        self.populate()
        (self.root / MOD.PATHS["private_store_module"]).unlink()
        with self.assertRaises(FileNotFoundError):
            MOD.inspect(self.root, enforce_home=False)

    def test_file_symlink_is_rejected(self):
        self.populate()
        link = self.root / MOD.PATHS["public_index"]
        link.unlink()
        link.symlink_to(self.root / MOD.PATHS["private_store_module"])
        with self.assertRaises(OSError):
            MOD.inspect(self.root, enforce_home=False)

    def test_symlinked_store_directory_is_rejected(self):
        self.populate()
        path = self.root / "public_html/store"
        real = self.root / "real-store"
        path.rename(real)
        path.symlink_to(real, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            MOD.inspect(self.root, enforce_home=False)

    def test_oversized_file_is_rejected(self):
        self.populate("x" * (MOD.MAX_BYTES + 1))
        with self.assertRaises(RuntimeError):
            MOD.inspect(self.root, enforce_home=False)

    def test_unexpected_home_refused_in_production_default(self):
        self.populate()
        with self.assertRaises(RuntimeError):
            MOD.inspect(self.root)

    def test_never_claims_http_parity_or_writes(self):
        self.populate()
        r = MOD.inspect(self.root, enforce_home=False)
        self.assertFalse(r["verified_public_http_serving_parity"])
        self.assertFalse(r["private_content_disclosed"])
        for name in ("site_writes", "forms_submitted", "payments", "authentication_attempts"):
            self.assertEqual(r[name], 0)

    def test_relay_contains_two_pinned_host_fingerprints(self):
        source = RELAY.read_text(encoding="utf8")
        self.assertIn("SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs", source)
        self.assertIn("SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04", source)
        self.assertIn("StrictHostKeyChecking yes", source)
        self.assertIn("BatchMode yes", source)
        self.assertIn("ProxyJump saeit-vps", source)

    def test_remote_command_is_python_read_only(self):
        content = RELAY.read_text(encoding="utf8")
        self.assertIn("saeit-cpanel python3 - <", content)
        for forbidden in ("scp ", "rsync ", "ssh -tt", "sudo ", "chmod 777"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, content)


if __name__ == "__main__":
    unittest.main()
