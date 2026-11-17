"""Isolated synthetic only: exact-hash MOJ-PROP-01 HTML transaction regressions.

Tests create ONLY temporary fake sites; never connect to cPanel or call CLI.
"""
import hashlib
from pathlib import Path
import os
import stat
import tempfile
import unittest
from unittest.mock import patch

from scripts import mojprop_plan1_static_atomic_release_20261118 as m

ORIGINAL=(b"<!-- MOJ_PROP_CATALOG_RELEASE_V4 -->\n"
          b'<html><select id="horizon"><option>week</option></select></html>')
NEW=(b'<html><h1>MOJ-PROP-01</h1>'
     b'<p>not payable today</p>'
     b'<a>Contact MOJ PROP about Plan 1 (free)</a>'
     b'<p>Do not send money today.</p>'
     b'<p>do not send the bearer token by email</p></html>')


class SafeStaticReleaseTests(unittest.TestCase):
    def setUp(self):
        self.patchers=(
            patch.object(m,"ORIGINAL_SHA",hashlib.sha256(ORIGINAL).hexdigest()),
            patch.object(m,"ORIGINAL_SIZE",len(ORIGINAL)),
            patch.object(m,"CANDIDATE_SHA",hashlib.sha256(NEW).hexdigest()),
            patch.object(m,"CANDIDATE_SIZE",len(NEW)),
        )
        for p in self.patchers:
            p.start()
            self.addCleanup(p.stop)
        self.tmp=tempfile.TemporaryDirectory(prefix="MOJPROP_TEST_ONLY_")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.live=self.root/"web"/"moj-prop"/"index.html"
        self.live.parent.mkdir(parents=True)
        self.live.write_bytes(ORIGINAL)
        self.live.chmod(0o644)
        self.candidate=self.root/"reviewed"/"index.html"
        self.candidate.parent.mkdir()
        self.candidate.write_bytes(NEW)
        self.candidate.chmod(0o644)
        self.backup=self.root/".backups"/"previous.html"
        self.backup.parent.mkdir(mode=0o700)
        self.backup.parent.chmod(0o700)
        self.uid=os.geteuid()

    def call(self, mode, **kw):
        return m.transact(mode,live=self.live,backup=self.backup,
                          candidate=self.candidate,uid=self.uid,**kw)

    @staticmethod
    def approve():
        return m.ReleaseReviews(True,True,True,True,True)

    def test_01_preflight_only_reads_no_backup_lock(self):
        report=self.call("preflight")
        self.assertFalse(report["writes"])
        self.assertFalse(self.backup.exists())
        self.assertFalse((self.backup.parent/m.LOCK.name).exists())
        self.assertEqual(self.live.read_bytes(),ORIGINAL)

    def test_02_preflight_is_explicitly_not_install_permission(self):
        self.assertFalse(self.call("preflight")["install_allowed_by_preflight"])

    def test_03_default_install_denied(self):
        with self.assertRaisesRegex(m.ExactStaticReleaseDenied,"OWNER_OR"):
            self.call("install")

    def test_04_fake_ack_without_restore_gates_denied(self):
        with self.assertRaisesRegex(m.ExactStaticReleaseDenied,"OWNER_OR"):
            self.call("install",owner_ack=m.OWNER_ACK)

    def test_05_all_claims_except_legal_review_denied(self):
        gates=m.ReleaseReviews(True,True,True,False,True)
        with self.assertRaises(m.ExactStaticReleaseDenied):
            self.call("install",reviews=gates,owner_ack=m.OWNER_ACK)

    def test_06_all_claims_except_quota_denied(self):
        gates=m.ReleaseReviews(True,True,False,True,True)
        with self.assertRaises(m.ExactStaticReleaseDenied):
            self.call("install",reviews=gates,owner_ack=m.OWNER_ACK)

    def test_07_all_claims_except_independent_restore_denied(self):
        gates=m.ReleaseReviews(True,False,True,True,True)
        with self.assertRaises(m.ExactStaticReleaseDenied):
            self.call("install",reviews=gates,owner_ack=m.OWNER_ACK)

    def test_08_all_claims_except_rollback_review_denied(self):
        gates=m.ReleaseReviews(True,True,True,True,False)
        with self.assertRaises(m.ExactStaticReleaseDenied):
            self.call("install",reviews=gates,owner_ack=m.OWNER_ACK)

    def test_09_complete_claims_without_exact_owner_ack_denied(self):
        with self.assertRaises(m.ExactStaticReleaseDenied):
            self.call("install",reviews=self.approve(),owner_ack="not-this-release")

    def test_10_synthetic_install_creates_private_original(self):
        result=self.call("install",reviews=self.approve(),owner_ack=m.OWNER_ACK)
        self.assertEqual(result["status"],"PINNED_STATIC_INSTALLED")
        self.assertEqual(self.live.read_bytes(),NEW)
        self.assertEqual(self.backup.read_bytes(),ORIGINAL)
        self.assertEqual(stat.S_IMODE(self.backup.stat().st_mode),0o600)

    def test_11_rollback_restores_byte_exact_public_original(self):
        self.call("install",reviews=self.approve(),owner_ack=m.OWNER_ACK)
        result=self.call("rollback")
        self.assertEqual(result["status"],"PINNED_ORIGINAL_ROLLED_BACK")
        self.assertEqual(self.live.read_bytes(),ORIGINAL)
        self.assertTrue(self.backup.exists())

    def test_12_rollback_does_not_require_broker_or_payment_activation(self):
        self.call("install",reviews=self.approve(),owner_ack=m.OWNER_ACK)
        self.assertEqual(self.call("rollback")["verified_live_sha256"],m.ORIGINAL_SHA)

    def test_13_unknown_operation_refused(self):
        with self.assertRaisesRegex(m.ExactStaticReleaseDenied,"INVALID_OPERATION"):
            self.call("delete-production")

    def test_14_original_changed_before_preflight_denied(self):
        self.live.write_bytes(ORIGINAL+b"!")
        with self.assertRaises(m.ExactStaticReleaseDenied):
            self.call("preflight")

    def test_15_original_changed_before_apply_denied(self):
        self.live.write_bytes(ORIGINAL+b"!")
        with self.assertRaises(m.ExactStaticReleaseDenied):
            self.call("install",reviews=self.approve(),owner_ack=m.OWNER_ACK)
        self.assertFalse(self.backup.exists())

    def test_16_candidate_changed_denied(self):
        self.candidate.write_bytes(NEW+b"!")
        with self.assertRaises(m.ExactStaticReleaseDenied):
            self.call("preflight")

    def test_17_wrong_product_markers_refused_even_if_fake_hash_matches(self):
        payload=NEW.replace(b"MOJ-PROP-01",b"educational")
        with patch.object(m,"CANDIDATE_SHA",hashlib.sha256(payload).hexdigest()),\
             patch.object(m,"CANDIDATE_SIZE",len(payload)):
            self.candidate.write_bytes(payload)
            with self.assertRaisesRegex(m.ExactStaticReleaseDenied,"WARNINGS"):
                self.call("preflight")

    def test_18_broken_plan1_optin_refused_even_if_hash_matches(self):
        payload=NEW+b'href="/moj-prop-interest/form/"'
        with patch.object(m,"CANDIDATE_SHA",hashlib.sha256(payload).hexdigest()),\
             patch.object(m,"CANDIDATE_SIZE",len(payload)):
            self.candidate.write_bytes(payload)
            with self.assertRaisesRegex(m.ExactStaticReleaseDenied,"LIVE_404"):
                self.call("preflight")

    def test_19_candidate_is_symlink_denied(self):
        original=self.candidate.parent/"really.html"
        original.write_bytes(NEW)
        self.candidate.unlink()
        self.candidate.symlink_to(original)
        with self.assertRaises((m.ExactStaticReleaseDenied,OSError)):
            self.call("preflight")

    def test_20_live_symlink_denied(self):
        real=self.live.parent/"real.html"
        real.write_bytes(ORIGINAL)
        self.live.unlink()
        self.live.symlink_to(real)
        with self.assertRaises((m.ExactStaticReleaseDenied,OSError)):
            self.call("preflight")
        self.assertEqual(real.read_bytes(),ORIGINAL)

    def test_21_owner_private_backup_folder_required(self):
        self.backup.parent.chmod(0o755)
        with self.assertRaisesRegex(m.ExactStaticReleaseDenied,"ROLLBACK_FOLDER"):
            self.call("preflight")

    def test_22_world_writable_live_file_denied(self):
        self.live.chmod(0o666)
        with self.assertRaisesRegex(m.ExactStaticReleaseDenied,"PERMISSIONS"):
            self.call("preflight")

    def test_23_world_writable_candidate_denied(self):
        self.candidate.chmod(0o666)
        with self.assertRaisesRegex(m.ExactStaticReleaseDenied,"PERMISSIONS"):
            self.call("preflight")

    def test_24_existing_corrupted_rollback_denied(self):
        self.backup.write_bytes(b"bad")
        self.backup.chmod(0o600)
        with self.assertRaises(m.ExactStaticReleaseDenied):
            self.call("preflight")
        self.assertEqual(self.backup.read_bytes(),b"bad")

    def test_25_world_readable_backup_denied(self):
        self.backup.write_bytes(ORIGINAL)
        self.backup.chmod(0o644)
        with self.assertRaisesRegex(m.ExactStaticReleaseDenied,"BACKUP_NOT_PRIVATE"):
            self.call("preflight")

    def test_26_symlinked_backup_denied_and_target_retained(self):
        other=self.root/"other.txt"
        other.write_text("NOT A BACKUP")
        self.backup.symlink_to(other)
        with self.assertRaises((m.ExactStaticReleaseDenied,OSError)):
            self.call("preflight")
        self.assertEqual(other.read_text(),"NOT A BACKUP")

    def test_27_malicious_lock_mode_denied_no_overwrite(self):
        lock=self.backup.parent/m.LOCK.name
        lock.write_bytes(b"")
        lock.chmod(0o644)
        with self.assertRaisesRegex(m.ExactStaticReleaseDenied,"TRANSACTION_LOCK_UNSAFE"):
            self.call("install",reviews=self.approve(),owner_ack=m.OWNER_ACK)
        self.assertEqual(self.live.read_bytes(),ORIGINAL)

    def test_28_repeated_install_refused_after_success(self):
        self.call("install",reviews=self.approve(),owner_ack=m.OWNER_ACK)
        with self.assertRaises(m.ExactStaticReleaseDenied):
            self.call("install",reviews=self.approve(),owner_ack=m.OWNER_ACK)
        self.assertEqual(self.live.read_bytes(),NEW)

    def test_29_modified_installed_page_cannot_rollback_over_customer_change(self):
        self.call("install",reviews=self.approve(),owner_ack=m.OWNER_ACK)
        self.live.write_bytes(NEW+b"manual changed")
        with self.assertRaises(m.ExactStaticReleaseDenied):
            self.call("rollback")
        self.assertEqual(self.live.read_bytes(),NEW+b"manual changed")

    def test_30_bad_private_backup_blocks_rollback(self):
        self.call("install",reviews=self.approve(),owner_ack=m.OWNER_ACK)
        self.backup.write_bytes(b"bad")
        with self.assertRaises(m.ExactStaticReleaseDenied):
            self.call("rollback")
        self.assertEqual(self.live.read_bytes(),NEW)

    def test_31_preexisting_identical_rollback_is_preserved(self):
        self.backup.write_bytes(ORIGINAL)
        self.backup.chmod(0o600)
        self.call("install",reviews=self.approve(),owner_ack=m.OWNER_ACK)
        self.assertEqual(self.backup.read_bytes(),ORIGINAL)

    def test_32_cannot_use_candidate_as_live(self):
        with self.assertRaises(m.ExactStaticReleaseDenied):
            m.transact("preflight",live=self.live,backup=self.backup,
                       candidate=self.live,uid=self.uid)

    def test_33_cannot_use_backup_as_candidate(self):
        with self.assertRaises(m.ExactStaticReleaseDenied):
            m.transact("preflight",live=self.live,backup=self.backup,
                       candidate=self.backup,uid=self.uid)

    def test_34_no_candidate_refuses_preflight(self):
        with self.assertRaises(m.ExactStaticReleaseDenied):
            m.transact("preflight",live=self.live,backup=self.backup,
                       candidate=None,uid=self.uid)

    def test_35_restored_original_cannot_repeat_rollback(self):
        self.call("install",reviews=self.approve(),owner_ack=m.OWNER_ACK)
        self.call("rollback")
        with self.assertRaises(m.ExactStaticReleaseDenied):
            self.call("rollback")

    def test_36_insecure_backup_lock_not_removed_by_preflight(self):
        lock=self.backup.parent/m.LOCK.name
        lock.write_bytes(b"conflict")
        self.call("preflight")
        self.assertEqual(lock.read_bytes(),b"conflict")

    def test_37_preflight_does_not_claim_real_full_restore(self):
        self.assertFalse(self.call("preflight")["fresh_restore_independently_proven"])

    def test_38_successful_synthetic_install_never_enables_tron_payments(self):
        status=self.call("install",reviews=self.approve(),owner_ack=m.OWNER_ACK)
        self.assertFalse(status["payments_enabled"])
        self.assertFalse(status["database_modified"])

    def test_39_all_gates_default_to_unapproved(self):
        self.assertFalse(m.ReleaseReviews().approved())

    def test_40_validated_candidate_source_is_sha_pinned(self):
        self.assertEqual(m.digest(self.candidate.read_bytes()),m.CANDIDATE_SHA)

    def test_41_validated_old_public_source_is_sha_pinned(self):
        self.assertEqual(m.digest(self.live.read_bytes()),m.ORIGINAL_SHA)

    def test_42_no_owner_guards_can_be_satisfied_with_nonbool(self):
        v=m.ReleaseReviews(True,True,True,True,1)
        self.assertFalse(v.approved())


if __name__=="__main__":
    unittest.main()
