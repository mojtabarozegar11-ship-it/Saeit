"""Offline safety contracts for a one-paragraph cPanel storefront copy release."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import mpw_store_payment_copy_safe_release_20261106 as release


SOURCE = Path(__file__).resolve().parents[1] / "core/templates/mojplaywin/store.html"


def baseline():
    return (b"X" * 2100 + release.LANDMARK +
            b'><h3>How checkout and delivery work</h3><p>' + release.OLD +
            b'</p></aside><a href="/commerce/book/72/">Order</a>' + b"Y" * 300)


class StorePaymentCopySafety(unittest.TestCase):
    def test_approved_copy_matches_source_control(self):
        latest = SOURCE.read_bytes()
        self.assertIn(release.NEW, latest)
        self.assertNotIn(release.OLD, latest)

    def test_rewrite_changes_only_one_approved_paragraph(self):
        original = baseline()
        updated, changed = release.rewrite(original)
        self.assertTrue(changed)
        self.assertEqual(updated, original.replace(release.OLD, release.NEW, 1))
        self.assertEqual(release.rewrite(updated), (updated, False))

    def test_unknown_or_duplicated_text_fails_closed(self):
        original = baseline()
        for data in (original + release.OLD,
                     original.replace(release.OLD, b"unknown marketing copy"),
                     original.replace(release.LANDMARK, b'<aside class="other"'),
                     original.replace(release.OLD, release.NEW + release.OLD)):
            with self.subTest(length=len(data)), self.assertRaises(RuntimeError):
                release.rewrite(data)

    def test_publish_verify_and_exact_rollback_without_remote_side_effect(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            store = work / "store.html"
            marker = work / "restart.txt"
            original = baseline()
            updated, _ = release.rewrite(original)
            store.write_bytes(original)
            with patch.object(release, "STORE", store), \
                    patch.object(release, "RESTART", marker), \
                    patch.object(release, "BACKUPS", work / "backups"), \
                    patch.object(release, "preflight", side_effect=lambda: store.read_bytes()), \
                    patch.object(release, "syntax_check"):
                run_id = "202611060001"
                release.command("audit")
                release.command("publish", run_id, release.sha(original))
                self.assertEqual(store.read_bytes(), updated)
                self.assertTrue(marker.is_file())
                self.assertEqual((work / "backups" / run_id / "store.before.html").read_bytes(), original)
                release.command("verify")
                release.command("rollback", run_id, release.sha(updated))
                self.assertEqual(store.read_bytes(), original)

    def test_rollback_refuses_concurrent_edit(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            store = work / "store.html"
            original = baseline()
            updated, _ = release.rewrite(original)
            store.write_bytes(original)
            with patch.object(release, "STORE", store), \
                    patch.object(release, "RESTART", work / "restart.txt"), \
                    patch.object(release, "BACKUPS", work / "backups"), \
                    patch.object(release, "preflight", side_effect=lambda: store.read_bytes()), \
                    patch.object(release, "syntax_check"):
                release.command("publish", "202611060002", release.sha(original))
                store.write_bytes(updated + b"unexpected change")
                with self.assertRaises(RuntimeError):
                    release.command("rollback", "202611060002", release.sha(updated))
                self.assertEqual(store.read_bytes(), updated + b"unexpected change")


if __name__ == "__main__":
    unittest.main()
