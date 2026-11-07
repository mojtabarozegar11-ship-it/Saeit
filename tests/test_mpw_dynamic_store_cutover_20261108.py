"""Offline synthetic checks; never contacts cPanel or the public store."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from scripts.mpw_dynamic_store_cutover_20261108 import (
    FALLBACK_BLOCK, MARKER, inspect_owned_fallback, perform_cutover,
)


class DynamicStoreCutoverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.public = Path(self.temp.name) / "public"
        self.public.mkdir()
        (self.public / "tmp").mkdir()
        (self.public / "tmp/restart.txt").touch()
        (self.public / "store").mkdir()
        (self.public / "store/index.html").write_bytes(
            b"<html><body>" + MARKER + b"</body></html>"
        )
        # Real live rule starts at line seven, so do not assume a file prefix.
        self.original = b"# retained owner config\n" * 6 + FALLBACK_BLOCK + b"PassengerAppRoot retained\n"
        (self.public / ".htaccess").write_bytes(self.original)
        self.backups = Path(self.temp.name) / "private-backups"

    def test_line_seven_exact_rule_removed_without_impact_on_other_config(self):
        original, changed, _ = inspect_owned_fallback(self.public)
        self.assertEqual(original, self.original)
        self.assertEqual(changed, self.original.replace(FALLBACK_BLOCK, b"", 1))
        checks = []

        def successful_probe():
            checks.append(1)
            self.assertFalse((self.public / "store").exists())
            self.assertEqual((self.public / ".htaccess").read_bytes(), changed)
            return True

        with contextlib.redirect_stdout(io.StringIO()):
            perform_cutover(self.public, self.backups, "42425162108", successful_probe)
        self.assertEqual(checks, [1])
        self.assertTrue((self.backups / "42425162108/store/index.html").is_file())
        self.assertEqual((self.backups / "42425162108/htaccess.original").read_bytes(), original)
        self.assertEqual((self.public / ".htaccess").read_bytes(), changed)

    def test_failed_public_probe_restores_exact_original_files(self):
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, "LIVE_DYNAMIC_PUBLIC_SMOKE_FAILED"):
                perform_cutover(self.public, self.backups, "42425162109", lambda: False)
        self.assertEqual((self.public / ".htaccess").read_bytes(), self.original)
        self.assertIn(MARKER, (self.public / "store/index.html").read_bytes())
        self.assertTrue((self.public / "tmp/restart.txt").is_file())

    def test_duplicate_rule_and_unrelated_store_file_are_rejected(self):
        (self.public / ".htaccess").write_bytes(self.original + FALLBACK_BLOCK)
        with self.assertRaisesRegex(RuntimeError, "FALLBACK_ANCHOR_DRIFT"):
            inspect_owned_fallback(self.public)
        (self.public / ".htaccess").write_bytes(self.original)
        (self.public / "store/unrelated.txt").write_text("preserve")
        with self.assertRaisesRegex(RuntimeError, "UNOWNED_STORE_DIRECTORY_CONTENTS"):
            inspect_owned_fallback(self.public)
        self.assertEqual((self.public / "store/unrelated.txt").read_text(), "preserve")

    def test_invalid_run_id_cannot_create_backup(self):
        with self.assertRaisesRegex(RuntimeError, "INVALID_RUN_ID"):
            perform_cutover(self.public, self.backups, "../../escape", lambda: True)
        self.assertFalse(self.backups.exists())

    def test_owner_only_workflow_is_fail_closed(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/mpw-dynamic-store-cutover-20261108.yml").read_text()
        self.assertIn("github.event.comment.user.login == 'mojtabarozegar11-ship-it'", workflow)
        self.assertIn("github.event.comment.author_association == 'OWNER'", workflow)
        self.assertIn("github.event.issue.number == 1600", workflow)
        self.assertIn("github.event.comment.body == 'MPW-STORE-DYNAMIC-CUTOVER-20261108'", workflow)
        self.assertIn("timeout 150s ssh -T", workflow)
        self.assertNotIn("StrictHostKeyChecking no", workflow)


if __name__ == "__main__":
    unittest.main()
