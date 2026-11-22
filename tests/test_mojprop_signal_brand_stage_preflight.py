"""Fail-closed offline contract for the staged 17-brand Signal CTA release."""
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import mojprop_signal_brand_stage_preflight as release


class BrandSourceStagePreflightTests(unittest.TestCase):
    def synthetic_pair(self):
        before = b"\n".join((b"# unrelated module remains byte-exact", *release.OLD.keys(), b"# trailing approved module logic"))
        after = before
        for old, new in release.OLD.items():
            after = after.replace(old, new, 1)
        return before, after

    def test_only_two_constants_can_change(self):
        before, after = self.synthetic_pair()
        self.assertTrue(release.exact_candidate(
            before, after, release.digest(before), release.digest(after)
        ))

    def test_unexpected_before_sha_fails_closed(self):
        before, after = self.synthetic_pair()
        with self.assertRaisesRegex(ValueError, "SOURCE_HASH_DRIFT"):
            release.exact_candidate(before, after)

    def test_unapproved_third_change_fails_closed(self):
        before, after = self.synthetic_pair()
        altered = after + b"\n# silent extra edit"
        with self.assertRaisesRegex(ValueError, "NON_TARGET_CODE_CHANGE"):
            release.exact_candidate(before, altered, release.digest(before), release.digest(altered))

    def test_old_anchor_must_exist_exactly_once(self):
        before, after = self.synthetic_pair()
        before += b"\n" + next(iter(release.OLD))
        with self.assertRaisesRegex(ValueError, "MISSING_OR_DUPLICATE_OLD_CONSTANT"):
            release.exact_candidate(before, after, release.digest(before), release.digest(after))

    def test_no_process_restart_or_production_writes(self):
        script = Path(release.__file__).read_text(encoding="utf8")
        for forbidden in ("os.replace(", "send_mail(", "subprocess.run(", "os.system(", "systemctl ", "pkill ", "touch restart.txt", "manage.py migrate", "http POST"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, script)

    def test_private_files_require_owner_and_private_permissions(self):
        with patch.object(release.os, "lstat") as lstat:
            item=lstat.return_value
            item.st_mode=0o100644
            item.st_uid=release.TENANT_UID
            item.st_nlink=1
            with patch.object(release.Path, "is_symlink", return_value=False):
                with self.assertRaisesRegex(ValueError, "PRIVATE_BACKUP_PERMISSIONS"):
                    release.owner_regular(Path("/not-accessed"), private=True)

    def test_all_modes_other_than_readonly_are_rejected(self):
        text = Path(release.__file__).read_text(encoding="utf8")
        self.assertIn('sys.argv[1] != "--verify-stage"', text)
        self.assertIn('"production_recovery_approval_verified": False', text)
        self.assertIn('"production_source_modified": False', text)

    def test_pinned_hashes_exact_and_real_git_commit(self):
        for val in (release.BEFORE_SHA256, release.CANDIDATE_SHA256, release.WSGI_SHA256, release.HTACCESS_SHA256, release.APPROVED_MAIN_COMMIT):
            self.assertEqual(len(val), 40 if val==release.APPROVED_MAIN_COMMIT else 64)
            int(val,16)
        self.assertEqual(len(release.OLD), 2)


if __name__ == "__main__":
    unittest.main()
