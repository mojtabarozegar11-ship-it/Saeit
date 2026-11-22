"""Offline tests for a strictly metadata-only commercial inquiry census.

No cPanel connection, customer data, email, database or external account access.
Run: python3 -m unittest discover -s tests -p 'test_mpw_encrypted_inquiry_queue_readonly.py' -v
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from scripts import mpw_encrypted_inquiry_queue_readonly as c


class InquiryQueueCensusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.chmod(0o700)
        self.now = 2000000000.0
        self.name = "20261114-AB1234567890CDEF12.json"
        self.path = self.root / self.name

    def lead(self, age=0):
        self.path.write_text("encrypted container placeholder", encoding="utf8")
        os.utime(self.path, (self.now-age,self.now-age))
        return self.path

    def dispatched(self):
        marker = self.root / (c.MARKER +
            hashlib.sha256(self.name.encode("ascii")).hexdigest() + ".json")
        marker.write_text('{"queued":"true"}',encoding="utf8")
        return marker

    def test_01_empty_private_directory(self):
        r=c.census(self.root,self.now)
        self.assertTrue(r["available"])
        self.assertEqual(r["encrypted_record_candidates"],0)

    def test_02_recent_unmarked_lead_count(self):
        self.lead()
        r=c.census(self.root,self.now)
        self.assertEqual((r["not_dispatched_marker"],r["last_7d_unmarked"]),(1,1))

    def test_03_record_marker_count(self):
        self.lead()
        self.dispatched()
        r=c.census(self.root,self.now)
        self.assertEqual((r["marker_present"],r["not_dispatched_marker"]),(1,0))

    def test_04_marker_is_not_delivery_evidence(self):
        self.lead();self.dispatched()
        self.assertIs(c.census(self.root,self.now)["dispatch_marker_is_delivery_proof"],False)

    def test_05_aging_24_hours(self):
        self.lead(25*3600)
        self.assertEqual(c.census(self.root,self.now)["older_than_24h_unmarked"],1)

    def test_06_aging_72_hours(self):
        self.lead(73*3600)
        self.assertEqual(c.census(self.root,self.now)["older_than_72h_unmarked"],1)

    def test_07_early_age_not_older_than_24h(self):
        self.lead(23*3600)
        self.assertEqual(c.census(self.root,self.now)["older_than_24h_unmarked"],0)

    def test_08_beyond_seven_days_not_recent(self):
        self.lead(8*86400)
        self.assertEqual(c.census(self.root,self.now)["last_7d_candidates"],0)

    def test_09_suspicious_symlink_record_rejected(self):
        outside=self.root/"other"
        outside.write_text("sensitive")
        self.path.symlink_to(outside)
        r=c.census(self.root,self.now)
        self.assertEqual(r["invalid_metadata"],1)

    def test_10_nonconforming_filename_ignored(self):
        (self.root/"customer@example.com.json").write_text("sensitive")
        self.assertEqual(c.census(self.root,self.now)["files_inspected"],0)

    def test_11_privacy_flags_never_claim_access(self):
        self.lead()
        r=c.census(self.root,self.now)
        self.assertFalse(r["private_payload_read"])
        self.assertFalse(r["recipient_identity_read"])
        self.assertFalse(r["record_decrypted"])

    def test_12_no_mail_or_state_modification(self):
        self.lead()
        r=c.census(self.root,self.now)
        self.assertFalse(r["mail_sent"])
        self.assertFalse(r["files_modified"])
        self.assertFalse(r["markers_created"])

    def test_13_source_record_bytes_unchanged(self):
        self.lead()
        before=self.path.read_bytes()
        stat_before=self.path.stat()
        c.census(self.root,self.now)
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(self.path.stat().st_mtime_ns,stat_before.st_mtime_ns)

    def test_14_private_root_required(self):
        self.root.chmod(0o755)
        self.assertFalse(c.census(self.root,self.now)["available"])

    def test_15_missing_directory_not_available(self):
        self.assertFalse(c.census(self.root/"does-not-exist",self.now)["available"])

    def test_16_symlink_root_refused(self):
        link=self.root.parent/(self.root.name+"-link")
        link.symlink_to(self.root)
        self.addCleanup(lambda:link.unlink(missing_ok=True))
        self.assertFalse(c.census(link,self.now)["available"])

    def test_17_zero_byte_record_invalid(self):
        self.path.write_bytes(b"")
        self.assertEqual(c.census(self.root,self.now)["invalid_metadata"],1)

    def test_18_oversized_record_invalid(self):
        with self.path.open("wb") as stream:
            stream.truncate(c.MAX_SIZE+1)
        self.assertEqual(c.census(self.root,self.now)["invalid_metadata"],1)

    def test_19_symlink_marker_does_not_confirm_dispatch(self):
        self.lead()
        marker=self.root/(c.MARKER+
            hashlib.sha256(self.name.encode("ascii")).hexdigest()+".json")
        marker.symlink_to(self.path)
        self.assertEqual(c.census(self.root,self.now)["not_dispatched_marker"],1)

    def test_20_marker_for_another_record_is_not_matched(self):
        self.lead()
        other=self.root/(c.MARKER+"A"*64+".json")
        other.write_text('{"queued":true}')
        self.assertEqual(c.census(self.root,self.now)["not_dispatched_marker"],1)

    def test_21_scan_cap_is_explicit_and_fails_overscan(self):
        self.lead()
        with patch.object(c,"MAX_SCAN",0):
            result=c.census(self.root,self.now)
        self.assertTrue(result["scan_truncated"])

    def test_22_dispatched_old_lead_not_in_unmarked_aging(self):
        self.lead(100*3600)
        self.dispatched()
        result=c.census(self.root,self.now)
        self.assertEqual(result["older_than_72h_unmarked"],0)

    def test_23_unknown_encryption_remains_unverified(self):
        self.lead()
        self.assertTrue(c.census(self.root,self.now)[
            "numbers_are_unverified_encrypted_record_candidates"])

    def test_24_non_numeric_now_refused(self):
        with self.assertRaises(ValueError):
            c.census(self.root,"today")

    def test_25_same_reader_is_deterministic(self):
        self.lead()
        self.assertEqual(c.census(self.root,self.now),c.census(self.root,self.now))


if __name__=="__main__":
    unittest.main()
