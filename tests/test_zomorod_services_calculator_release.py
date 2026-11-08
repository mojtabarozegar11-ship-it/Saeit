"""Regression checks for the strictly scoped services calculator release."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/deploy_zomorod_services_calculator.py"
ROOT = SCRIPT.parents[1]
SPEC = importlib.util.spec_from_file_location("zomorod_services_release", SCRIPT)
release_script = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_script)


OLD_BLOCK = (
    release_script.MARKER + b"\n<section><button id=\"zm-margin-run\"></button></section>"
    + b"<script>function oldCalculator(){return 1;}</script>"
)
NEW_BLOCK = (
    release_script.MARKER + b"\n<section><button id=\"zm-margin-run\"></button>"
    + b"<button id=\"zm-margin-download\"></button></section><script>"
    + b"function resetPriorResult(){}; breakEvenPrice:yieldKg>0;"
    + b"Number.MAX_SAFE_INTEGER; input.addEventListener('input',resetPriorResult);"
    + b"</script>"
)
PREFIX = b"<html><header>LIVE ONLY</header><main>\n"
SUFFIX = b"<footer>keep user's independent page edits</footer></main></html>"


class ScopedReleaseTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.target = self.root / "index.html"
        self.legacy = PREFIX + OLD_BLOCK + SUFFIX
        self.approved = PREFIX + NEW_BLOCK + SUFFIX
        self.live = PREFIX.replace(b"LIVE ONLY", b"LIVE LOCAL CUSTOMIZATION") + OLD_BLOCK + SUFFIX
        self.target.write_bytes(self.live)
        self.backup_parent = self.root / "backups"
        self.backup_parent.mkdir()
        self.verified = []

    def deploy(self, **kwargs):
        args = dict(legacy=self.legacy, approved=self.approved,
                    target=self.target, backup_dir=self.backup_parent / "1-1",
                    verify=self.verified.append)
        args.update(kwargs)
        return release_script.release(**args)

    def test_release_changes_only_named_block(self):
        result = self.deploy()
        self.assertEqual(result["state"], "deployed")
        self.assertEqual(self.target.read_bytes(), self.live.replace(OLD_BLOCK, NEW_BLOCK, 1))
        self.assertIn(b"LIVE LOCAL CUSTOMIZATION", self.target.read_bytes())
        self.assertIn(b"keep user's independent page edits", self.target.read_bytes())
        self.assertEqual(self.verified, [NEW_BLOCK])

    def test_backup_is_exact_original_and_manifest_is_auditable(self):
        result = self.deploy()
        folder = self.backup_parent / "1-1"
        self.assertEqual((folder / "services-original.html").read_bytes(), self.live)
        manifest = json.loads((folder / "manifest.json").read_text())
        self.assertEqual(manifest["original_sha256"], release_script.digest(self.live))
        self.assertEqual(manifest["updated_sha256"], result["updated_sha256"])

    def test_verification_failure_restores_every_original_byte(self):
        def bad_verify(_):
            raise RuntimeError("public page returned stale content")
        with self.assertRaisesRegex(RuntimeError, "stale content"):
            self.deploy(verify=bad_verify)
        self.assertEqual(self.target.read_bytes(), self.live)

    def test_live_calculator_mismatch_is_never_overwritten(self):
        original = self.live.replace(b"oldCalculator", b"anotherLiveCalculator")
        self.target.write_bytes(original)
        with self.assertRaisesRegex(RuntimeError, "differs from exact reviewed baseline"):
            self.deploy()
        self.assertEqual(self.target.read_bytes(), original)
        self.assertFalse((self.backup_parent / "1-1").exists())

    def test_duplicate_marker_is_refused(self):
        with self.assertRaisesRegex(ValueError, "Missing, duplicate"):
            release_script.section(self.legacy + OLD_BLOCK)

    def test_missing_marker_is_refused(self):
        with self.assertRaisesRegex(ValueError, "Missing, duplicate"):
            release_script.section(b"<html>empty</html>")

    def test_missing_download_guard_is_refused(self):
        with self.assertRaisesRegex(ValueError, "required safeguard"):
            release_script.expected_release(self.legacy, self.approved.replace(b"Number.MAX_SAFE_INTEGER", b"unsafe"))

    def test_existing_download_in_legacy_is_refused(self):
        bad_legacy = self.legacy.replace(OLD_BLOCK, NEW_BLOCK)
        with self.assertRaisesRegex(ValueError, "Legacy baseline"):
            release_script.expected_release(bad_legacy, self.approved)

    def test_already_deployed_is_idempotent(self):
        prepared = self.live.replace(OLD_BLOCK, NEW_BLOCK)
        self.target.write_bytes(prepared)
        result = self.deploy()
        self.assertEqual(result["state"], "already_deployed")
        self.assertEqual(self.target.read_bytes(), prepared)
        self.assertFalse((self.backup_parent / "1-1").exists())
        self.assertEqual(self.verified, [NEW_BLOCK])

    def test_symlink_target_is_refused(self):
        other = self.root / "other.html"
        other.write_bytes(self.live)
        self.target.unlink()
        self.target.symlink_to(other)
        with self.assertRaisesRegex(RuntimeError, "symlinked"):
            self.deploy()
        self.assertEqual(other.read_bytes(), self.live)

    def test_existing_backup_prevents_repeat_write(self):
        (self.backup_parent / "1-1").mkdir()
        with self.assertRaisesRegex(RuntimeError, "backup already exists"):
            self.deploy()
        self.assertEqual(self.target.read_bytes(), self.live)

    def test_oversized_html_is_refused(self):
        with self.assertRaisesRegex(ValueError, "oversized"):
            release_script.section(self.legacy + b"x" * release_script.MAX_HTML_BYTES)

    def test_breakage_during_public_verification_preserves_concurrent_edit(self):
        concurrent = b"<html>newer operator edit</html>"
        def verify_then_edit(_):
            self.target.write_bytes(concurrent)
            raise RuntimeError("verification failed after a concurrent edit")
        with self.assertRaisesRegex(RuntimeError, "concurrent edit"):
            self.deploy(verify=verify_then_edit)
        self.assertEqual(self.target.read_bytes(), concurrent)

    def test_release_is_rejected_if_live_file_disappears(self):
        self.target.unlink()
        with self.assertRaisesRegex(RuntimeError, "Missing"):
            self.deploy()

    def test_actual_approved_calculator_source_has_all_release_guards(self):
        source = ROOT / "content/zomorod-nova-pages/services.html"
        if not source.is_file():
            source = ROOT / "services_working.html"  # Local editor copy; checkout uses canonical path.
        if not source.is_file():
            self.skipTest("Approved calculator source not present in this workspace")
        block = release_script.section(source.read_bytes())[2]
        for needle in (b'id="zm-margin-download"', b"function resetPriorResult()",
                       b"breakEvenPrice:yieldKg>0", b"Number.MAX_SAFE_INTEGER"):
            self.assertIn(needle, block)

    def test_dispatch_is_manual_and_limited_to_services(self):
        workflow = ROOT / ".github/workflows/zomorod-services-calculator-release.yml"
        source = workflow.read_text(encoding="utf-8")
        self.assertIn("  workflow_dispatch:", source)
        self.assertNotIn("  push:", source)
        self.assertIn("github.ref == 'refs/heads/main'", source)
        self.assertIn("zomorod-services-calculator-production", source)
        self.assertIn("deploy_zomorod_services_calculator.py", source)
        self.assertIn("legacy_commit=e6838aff97d2e1450ec540f0605402afb94fd89f", source)


if __name__ == "__main__":
    unittest.main()
