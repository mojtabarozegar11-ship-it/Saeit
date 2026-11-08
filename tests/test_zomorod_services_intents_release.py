"""Fail-closed safety checks for the four agricultural service inquiry links."""

import importlib.util
from pathlib import Path
import stat
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/deploy_zomorod_services_intents.py"
spec = importlib.util.spec_from_file_location("zomorod_intents_release", SCRIPT)
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class ServiceIntentsReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Actual reviewed HTML must be provided from the same PR branch.
        cls.approved = (ROOT / "content/zomorod-nova-pages/services.html").read_bytes()

    def legacy(self):
        page = self.approved
        approved_links = deploy.find_links(page)
        for label, topic in deploy.LINKS:
            reviewed = approved_links[label][0]
            old = reviewed.replace(deploy.expected_href(topic), deploy.GENERIC_URL, 1)
            self.assertNotEqual(reviewed, old)
            self.assertEqual(page.count(reviewed), 1)
            page = page.replace(reviewed, old, 1)
        return page

    def test_exact_four_link_patch_preserves_every_other_byte(self):
        original = self.legacy()
        state, updated = deploy.prepare(original, self.approved)
        self.assertEqual(state, "ready")
        self.assertEqual(updated, self.approved)
        self.assertIn(b'id="zm-margin-download"', updated)
        self.assertEqual(deploy.find_links(updated)["استعلام مدیریت منابع ←"][1],
                         deploy.expected_href("water"))

    def test_already_deployed_is_read_only(self):
        state, updated = deploy.prepare(self.approved, self.approved)
        self.assertEqual(state, "already_deployed")
        self.assertEqual(updated, self.approved)

    def test_partial_release_is_rejected(self):
        original = self.legacy()
        first_label, first_topic = deploy.LINKS[0]
        raw = deploy.find_links(original)[first_label][0]
        partly_updated = original.replace(
            raw,
            raw.replace(deploy.GENERIC_URL, deploy.expected_href(first_topic), 1),
            1,
        )
        with self.assertRaisesRegex(RuntimeError, "Partial release"):
            deploy.prepare(partly_updated, self.approved)

    def test_wrong_reviewed_target_fails(self):
        broken = self.approved.replace(b"&amp;topic=water", b"&amp;topic=economics", 1)
        with self.assertRaisesRegex(ValueError, "unexpected destination"):
            deploy.prepare(self.legacy(), broken)

    def test_duplicate_target_label_is_rejected(self):
        target = deploy.find_links(self.approved)["استعلام مدیریت منابع ←"][0]
        with self.assertRaisesRegex(ValueError, "Duplicate specialist"):
            deploy.prepare(self.legacy(), self.approved + target)

    def test_successful_release_is_atomic_and_backed_up(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = root / "index.html"
            original = self.legacy()
            target.write_bytes(original)
            target.chmod(0o644)
            backup = root / "backups" / "1-1"
            backup.parent.mkdir(mode=0o700)
            observed = []
            result = deploy.release(
                target=target, approved=self.approved,
                expected_sha=deploy.sha256(original), backup_dir=backup,
                verify=lambda: observed.append(target.read_bytes()),
            )
            self.assertEqual(result["state"], "deployed")
            self.assertEqual(target.read_bytes(), self.approved)
            self.assertEqual((backup / "services-original.html").read_bytes(), original)
            self.assertEqual(observed, [self.approved])
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o644)
            self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o700)

    def test_failed_public_verification_restores_original(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = root / "index.html"
            original = self.legacy()
            target.write_bytes(original)
            backup = root / "backups" / "1-1"
            backup.parent.mkdir(mode=0o700)
            with self.assertRaisesRegex(RuntimeError, "Public verification failed"):
                deploy.release(
                    target=target, approved=self.approved,
                    expected_sha=deploy.sha256(original), backup_dir=backup,
                    verify=lambda: (_ for _ in ()).throw(RuntimeError("Public verification failed")),
                )
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual((backup / "services-original.html").read_bytes(), original)

    def test_mismatched_live_hash_never_creates_backup(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = root / "index.html"
            target.write_bytes(self.legacy())
            backup = root / "backups" / "1-1"
            backup.parent.mkdir(mode=0o700)
            with self.assertRaisesRegex(RuntimeError, "hash changed"):
                deploy.release(target=target, approved=self.approved,
                               expected_sha="0" * 64, backup_dir=backup,
                               verify=lambda: None)
            self.assertFalse(backup.exists())


if __name__ == "__main__":
    unittest.main()
