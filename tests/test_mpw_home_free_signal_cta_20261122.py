"""Offline tests for one pinned, reversible homepage free signal CTA.

No production path, network, Django/Passenger, invoice, payment or trading.
"""
import hashlib
import importlib.util
import json
import stat
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/mpw_home_free_signal_cta_20261122.py"
spec = importlib.util.spec_from_file_location("mpw_signal_cta_candidate", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture():
    return (
        b'<html><head><title>Original production homepage</title></head><body>\n'
        b'<section id="mpw-mojprop-spotlight-20261121">\n'
        b'<a href="/moj-prop/starter-30-trx/">Read Starter30 terms</a>\n'
        + module.ANCHOR +
        b'<div class="protected-chat-code">Do not edit unrelated markup</div>\n'
        b'</section></body></html>\n'
    )


class HomepageSignalCandidateTests(TestCase):
    def test_01_only_one_allowed_link_is_added_and_exactly_reversible(self):
        before = fixture()
        after = module.candidate_bytes(before)
        self.assertEqual(after.count(module.CTA), 1)
        self.assertEqual(after.replace(module.ANCHOR + module.CTA, module.ANCHOR, 1), before)
        self.assertIn(b"protected-chat-code", after)
        self.assertIn(b"service=signals", module.CTA)
        self.assertNotIn(b"checkout", module.CTA)
        self.assertNotIn(b"invoice", module.CTA)
        self.assertNotIn(b"send TRX", module.CTA)

    def test_02_refuses_duplicate_or_old_anchor_drift(self):
        original = fixture()
        for bad in (original + module.ANCHOR,
                    original.replace(module.ANCHOR, b"unrecognized markup"),
                    original + module.CTA,
                    original.replace(b"id=\"mpw-mojprop-spotlight-20261121\"", b"id=\"unknown\""),
                    original + b'/moj-prop/starter-30-trx/'):
            with self.subTest(bad=hashlib.sha256(bad).hexdigest()[:8]):
                with self.assertRaises(ValueError):
                    module.candidate_bytes(bad)

    def test_03_actual_verified_host_hashes_are_pinned(self):
        self.assertEqual(module.BASE_SHA256, "2f9c70c182833bb9a81f6eda3fba399463c36e70a13a51e2ee599fa3f04b5884")
        self.assertEqual(module.CANDIDATE_SHA256, "e637c5d6a73fc5a55f1c04d13adc2fb1ab5d15c79e4b9bce1714f656d6e812fe")
        self.assertEqual(module.BASE_SIZE, 265821)
        self.assertEqual(module.CANDIDATE_SIZE, 266074)
        self.assertEqual(len(module.CTA), 253)
        self.assertIn(b"utm_campaign=signals_education_lead_20261121", module.CTA)
        self.assertIn(b"utm_content=signal_nav", module.CTA)

    def test_04_full_offline_check_apply_rollback_preserves_target_bytes(self):
        before = fixture()
        after = module.candidate_bytes(before)
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            target = root / "production-home.html"
            target.write_bytes(before)
            target.chmod(0o644)
            private = root / ".private"
            private.mkdir(mode=0o700)
            backup_dir = private / "backups"
            kwargs = {
                "TARGET": target,
                "PRIVATE_DIR": private,
                "BACKUP_DIR": backup_dir,
                "BACKUP": backup_dir / "production-home.before",
                "MANIFEST": backup_dir / "manifest.json",
                "BASE_SHA256": module.digest(before),
                "CANDIDATE_SHA256": module.digest(after),
                "BASE_SIZE": len(before),
                "CANDIDATE_SIZE": len(after),
            }
            with patch.object(module.getpass, "getuser", return_value="zomorod2"):
                with patch.multiple(module, **kwargs):
                    module.execute("--check")
                    self.assertFalse(backup_dir.exists())
                    self.assertEqual(target.read_bytes(), before)
                    module.execute("--apply")
                    self.assertEqual(target.read_bytes(), after)
                    self.assertEqual(stat.S_IMODE((backup_dir / "production-home.before").stat().st_mode), 0o600)
                    self.assertEqual(stat.S_IMODE((backup_dir / "manifest.json").stat().st_mode), 0o600)
                    self.assertEqual(json.loads((backup_dir / "manifest.json").read_text())["creates_invoice_or_payment"], False)
                    with self.assertRaises(RuntimeError):
                        module.execute("--apply")
                    module.execute("--rollback")
                    self.assertEqual(target.read_bytes(), before)

    def test_05_never_overwrites_concurrent_source_or_missing_proof(self):
        before = fixture()
        after = module.candidate_bytes(before)
        with patch.object(module, "BASE_SHA256", module.digest(before)):
            with patch.object(module, "CANDIDATE_SHA256", module.digest(after)):
                with patch.object(module, "BASE_SIZE", len(before)):
                    with patch.object(module, "CANDIDATE_SIZE", len(after)):
                        with self.assertRaisesRegex(RuntimeError, "LIVE_SOURCE_SHA_MISMATCH"):
                            module.strict_source(before + b"other concurrent change")
                        self.assertEqual(module.strict_source(before), after)

    def test_06_non_owner_is_refused_even_in_check_mode(self):
        with patch.object(module.getpass, "getuser", return_value="wrong-user"):
            with self.assertRaisesRegex(RuntimeError, "Owner cPanel user only"):
                module.execute("--check")
