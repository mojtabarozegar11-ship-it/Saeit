"""C127 offline transaction regressions; never connect to cPanel or payment systems."""
import hashlib
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from scripts import mojprop_exact_static_atomic_release_c127 as m

ORIGINAL = (
    b"<!-- MOJ_PROP_CATALOG_RELEASE_V4 -->\n"
    b'<html><main>keep all unrelated markup</main><select id="horizon">'
    b"<option>Today / urgent</option><option>This week</option>"
    b"<option>This month</option><option>Initial review only</option>"
    b"</select><footer>privacy unchanged</footer></html>\n"
)
EXPECTED = (
    ORIGINAL.replace(b"<option>Today / urgent</option>",
                     b'<option value="urgent">Today / urgent</option>')
    .replace(b"<option>This week</option>",
             b'<option value="week">This week</option>')
    .replace(b"<option>This month</option>",
             b'<option value="month">This month</option>')
    .replace(b"<option>Initial review only</option>",
             b'<option value="review">Initial review only</option>')
)


class StaticAtomicC127(unittest.TestCase):
    def setUp(self):
        self.patches = (
            patch.object(m, "ORIGINAL_SHA", hashlib.sha256(ORIGINAL).hexdigest()),
            patch.object(m, "CANDIDATE_SHA", hashlib.sha256(EXPECTED).hexdigest()),
            patch.object(m, "ORIGINAL_SIZE", len(ORIGINAL)),
            patch.object(m, "CANDIDATE_SIZE", len(EXPECTED)),
        )
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.path = root / "site/moj-prop/index.html"
        self.path.parent.mkdir(parents=True)
        self.backup = root / ".backups/original.html"
        self.backup.parent.mkdir()
        self.path.write_bytes(ORIGINAL)
        self.path.chmod(0o644)
        self.uid = os.geteuid()

    def call(self, mode):
        return m.transact(mode, self.path, self.backup, euid=self.uid)

    def test_01_candidate_only_four_insertion_attributes(self):
        self.assertEqual(m.candidate(ORIGINAL), EXPECTED)
        self.assertEqual(len(EXPECTED) - len(ORIGINAL), 57)
        self.assertIn(b"<main>keep all unrelated markup</main>", EXPECTED)

    def test_02_preflight_reads_without_creating_backup_lock_or_changing_html(self):
        info = self.call("preflight")
        self.assertEqual(info["status"], "source_exact")
        self.assertFalse(info["writes"])
        self.assertFalse(self.backup.exists())
        self.assertFalse((self.backup.parent / m.LOCK.name).exists())
        self.assertEqual(self.path.read_bytes(), ORIGINAL)

    def test_03_atomic_apply_creates_private_byte_exact_backup(self):
        result = self.call("apply")
        self.assertTrue(result["writes"])
        self.assertEqual(result["status"], "candidate_installed")
        self.assertEqual(self.path.read_bytes(), EXPECTED)
        self.assertEqual(self.backup.read_bytes(), ORIGINAL)
        self.assertEqual(stat.S_IMODE(self.backup.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o644)

    def test_04_private_backup_enables_full_exact_rollback(self):
        self.call("apply")
        result = self.call("rollback")
        self.assertEqual(result["status"], "original_restored")
        self.assertEqual(self.path.read_bytes(), ORIGINAL)
        self.assertEqual(self.backup.read_bytes(), ORIGINAL)

    def test_05_rollback_is_noop_if_original_is_still_live(self):
        info = self.call("rollback")
        self.assertFalse(info["writes"])
        self.assertEqual(self.path.read_bytes(), ORIGINAL)

    def test_06_wrong_live_sha_refuses_even_readonly_proposal(self):
        self.path.write_bytes(ORIGINAL + b"\n")
        with self.assertRaises(m.SafetyGate):
            self.call("preflight")
        with self.assertRaises(m.SafetyGate):
            self.call("apply")
        self.assertFalse(self.backup.exists())

    def test_07_different_owner_option_is_not_overwritten(self):
        changed = ORIGINAL.replace(b"<option>This week", b'<option value="weekly">This week')
        self.path.write_bytes(changed)
        with self.assertRaises(m.SafetyGate):
            self.call("apply")
        self.assertEqual(self.path.read_bytes(), changed)

    def test_08_symlink_target_never_modified(self):
        actual = self.path.parent / "actual.html"
        actual.write_bytes(ORIGINAL)
        self.path.unlink()
        self.path.symlink_to(actual)
        with self.assertRaises((m.SafetyGate, OSError)):
            self.call("apply")
        self.assertEqual(actual.read_bytes(), ORIGINAL)

    def test_09_symlink_backup_is_not_followed(self):
        destination = self.backup.parent / "unrelated"
        destination.write_bytes(b"do not touch")
        self.backup.symlink_to(destination)
        with self.assertRaises((m.SafetyGate, OSError)):
            self.call("apply")
        self.assertEqual(destination.read_bytes(), b"do not touch")
        self.assertEqual(self.path.read_bytes(), ORIGINAL)

    def test_10_existing_bad_backup_refuses_overwrite(self):
        self.backup.write_bytes(b"owner backup conflict")
        self.backup.chmod(0o600)
        with self.assertRaises((m.SafetyGate, OSError)):
            self.call("apply")
        self.assertEqual(self.backup.read_bytes(), b"owner backup conflict")
        self.assertEqual(self.path.read_bytes(), ORIGINAL)

    def test_11_rollback_refuses_external_mutation_of_candidate(self):
        self.call("apply")
        changed = EXPECTED + b"buyer customization"
        self.path.write_bytes(changed)
        with self.assertRaises((m.SafetyGate, OSError)):
            self.call("rollback")
        self.assertEqual(self.path.read_bytes(), changed)

    def test_12_corrupted_backup_refuses_rollback(self):
        self.call("apply")
        self.backup.write_bytes(b"broken")
        with self.assertRaises(m.SafetyGate):
            self.call("rollback")
        self.assertEqual(self.path.read_bytes(), EXPECTED)

    def test_13_idempotent_duplicate_release_refused(self):
        self.call("apply")
        with self.assertRaises(m.SafetyGate):
            self.call("apply")
        self.assertEqual(self.path.read_bytes(), EXPECTED)

    def test_14_restrict_all_other_actions(self):
        with self.assertRaises(m.SafetyGate):
            self.call("restart-services")

    def test_15_hardcoded_offhost_original_and_candidate_identifiers_are_distinct(self):
        self.assertNotEqual(hashlib.sha256(ORIGINAL).hexdigest(),
                            hashlib.sha256(EXPECTED).hexdigest())
        self.assertEqual(len(m.PAIRS), 4)


if __name__ == "__main__":
    unittest.main()
