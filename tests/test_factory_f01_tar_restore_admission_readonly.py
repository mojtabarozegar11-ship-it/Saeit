"""Offline adversarial verification; no factory archive, customer data or secrets."""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

from scripts.f01_tar_restore_admission_readonly import evaluate, evaluate_file

ARCHIVE = "fbf2153da30e01842b84a6a068c50051ea49839a5f4a567073f771cac30952b8"


def evidence():
    return {
        "schema":"moj.f01.tar-gzip-readonly-audit.v1",
        "verified":{"archive_sha256_matches":True,"archive_bytes_match":True,
                    "gzip_crc_and_trailer_verified":True,"gcm_parts_authenticated":3,
                    "plain_archive_sha256":ARCHIVE,"plain_archive_bytes":4040955486,
                    "decrypted_data_written_to_disk":False,"extraction_performed":False,
                    "full_application_restore_performed":False},
        "tar_inventory":{"regular_files":105869,"directories":28743,"symlinks":3273,
                          "hardlinks":16,"other_members":3289,"absolute_paths":0,
                          "parent_traversal_names":0,"device_nodes":0,
                          "top_level_item_categories":1,"top_level_roots":["factory-runtime"]},
        "special_mode_counts":{},
        "unsafe_symlink_targets":3,"unsafe_hardlink_targets":0,
        "link_target_checks":{"absolute_symlink_targets":3,
                              "non_escalating_relative_symlink_targets":3270,
                              "non_escalating_hardlink_targets":16},
    }


class FailClosed(unittest.TestCase):
    def gate(self, doc):return evaluate(doc, expected_archive_sha256=ARCHIVE)
    def assertHold(self, doc, reason=None):
        out=self.gate(doc)
        self.assertEqual(out["decision"], "HOLD")
        self.assertFalse(out["isolated_extraction_authorized"])
        self.assertFalse(out["live_restore_authorized"])
        self.assertFalse(out["destructive_cleanup_authorized"])
        if reason:self.assertIn(reason,out["reasons"])

    def test_01_real_shaped_evidence_blocks_3_symlinks(self):
        out=self.gate(evidence());self.assertEqual(out["unsafe_link_count"],3)
        self.assertEqual(out["reasons"],["UNSAFE_LINK_TARGETS"])
    def test_02_no_evidence(self):self.assertHold(None,"UNKNOWN_AUDIT_SCHEMA")
    def test_03_invalid_schema(self):
        d=evidence();d["schema"]="fake";self.assertHold(d,"UNKNOWN_AUDIT_SCHEMA")
    def test_04_wrong_plain_digest(self):
        d=evidence();d["verified"]["plain_archive_sha256"]="0"*64;self.assertHold(d,"ARCHIVE_DIGEST_NOT_PINNED_MATCH")
    def test_05_wrong_expected_digest(self):
        self.assertEqual(evaluate(evidence(),expected_archive_sha256="none")["decision"],"HOLD")
    def test_06_invalid_gcm(self):
        d=evidence();d["verified"]["gcm_parts_authenticated"]=2;self.assertHold(d)
    def test_07_bool_gcm_rejected(self):
        d=evidence();d["verified"]["gcm_parts_authenticated"]=True;self.assertHold(d)
    def test_08_missing_crc(self):
        d=evidence();d["verified"].pop("gzip_crc_and_trailer_verified");self.assertHold(d)
    def test_09_false_archive_bytes(self):
        d=evidence();d["verified"]["archive_bytes_match"]=False;self.assertHold(d)
    def test_10_plaintext_written_unknown(self):
        d=evidence();d["verified"].pop("decrypted_data_written_to_disk");self.assertHold(d)
    def test_11_extraction_reported(self):
        d=evidence();d["verified"]["extraction_performed"]=True;self.assertHold(d)
    def test_12_disguised_symlink_count_bool(self):
        d=evidence();d["tar_inventory"]["symlinks"]=True;self.assertHold(d)
    def test_13_symlink_count_inconsistent(self):
        d=evidence();d["tar_inventory"]["symlinks"]+=1;self.assertHold(d)
    def test_14_hardlink_count_inconsistent(self):
        d=evidence();d["tar_inventory"]["hardlinks"]-=1;self.assertHold(d)
    def test_15_unknown_link_counter_invalid(self):
        d=evidence();d["link_target_checks"]["absolute_symlink_targets"]=-1;self.assertHold(d)
    def test_16_absolute_tar_member_rejected(self):
        d=evidence();d["tar_inventory"]["absolute_paths"]=1;self.assertHold(d)
    def test_17_parent_traversal_rejected(self):
        d=evidence();d["tar_inventory"]["parent_traversal_names"]=1;self.assertHold(d)
    def test_18_device_member_rejected(self):
        d=evidence();d["tar_inventory"]["device_nodes"]=1;self.assertHold(d)
    def test_19_unclassified_member_rejected(self):
        d=evidence();d["tar_inventory"]["other_members"]+=1;self.assertHold(d)
    def test_20_unknown_root_rejected(self):
        d=evidence();d["tar_inventory"]["top_level_roots"]=["unexpected"];self.assertHold(d)
    def test_21_modes_rejected(self):
        d=evidence();d["special_mode_counts"]={"setuid":1};self.assertHold(d)
    def test_22_false_unsafe_summary_rejected(self):
        d=evidence();d["unsafe_symlink_targets"]=0;self.assertHold(d)
    def test_23_zero_hazards_never_authorize_extract(self):
        d=evidence();d["link_target_checks"]["absolute_symlink_targets"]=0
        d["link_target_checks"]["non_escalating_relative_symlink_targets"]=3273
        d["unsafe_symlink_targets"]=0
        out=self.gate(d)
        self.assertEqual(out["decision"],"CANDIDATE_FOR_SEPARATE_ISOLATED_REVIEW_ONLY")
        self.assertFalse(out["isolated_extraction_authorized"])
        self.assertFalse(out["live_restore_authorized"])
    def test_24_no_expected_audit_digest_rejected(self):
        with tempfile.TemporaryDirectory() as p:
            f=pathlib.Path(p)/"audit.json";f.write_text(json.dumps(evidence()))
            self.assertEqual(evaluate_file(f,expected_audit_sha256="",expected_archive_sha256=ARCHIVE)["decision"],"HOLD")
    def test_25_tampered_evidence_sha_rejected(self):
        with tempfile.TemporaryDirectory() as p:
            f=pathlib.Path(p)/"audit.json";f.write_text(json.dumps(evidence()))
            self.assertEqual(evaluate_file(f,expected_audit_sha256="0"*64,expected_archive_sha256=ARCHIVE)["decision"],"HOLD")
    def test_26_bogus_json_rejected(self):
        with tempfile.TemporaryDirectory() as p:
            f=pathlib.Path(p)/"audit.json";f.write_text("nope")
            self.assertEqual(evaluate_file(f,expected_audit_sha256=hashlib.sha256(b"nope").hexdigest(),expected_archive_sha256=ARCHIVE)["decision"],"HOLD")
    def test_27_duplicate_json_key_rejected(self):
        with tempfile.TemporaryDirectory() as p:
            f=pathlib.Path(p)/"audit.json";s='{"schema":"a","schema":"b"}';f.write_text(s)
            self.assertEqual(evaluate_file(f,expected_audit_sha256=hashlib.sha256(s.encode()).hexdigest(),expected_archive_sha256=ARCHIVE)["decision"],"HOLD")
    def test_28_symlink_to_audit_rejected(self):
        with tempfile.TemporaryDirectory() as p:
            f=pathlib.Path(p)/"audit.json";f.write_text(json.dumps(evidence()))
            link=pathlib.Path(p)/"ref.json";link.symlink_to(f)
            self.assertEqual(evaluate_file(link,expected_audit_sha256=hashlib.sha256(f.read_bytes()).hexdigest(),expected_archive_sha256=ARCHIVE)["decision"],"HOLD")
    def test_29_actual_readonly_file_matches_pinned_audit(self):
        with tempfile.TemporaryDirectory() as p:
            f=pathlib.Path(p)/"audit.json";f.write_text(json.dumps(evidence()))
            out=evaluate_file(f,expected_audit_sha256=hashlib.sha256(f.read_bytes()).hexdigest(),expected_archive_sha256=ARCHIVE)
            self.assertEqual(out["reasons"],["UNSAFE_LINK_TARGETS"])
    def test_30_malformed_unsafe_count_bool_rejected(self):
        d=evidence();d["unsafe_hardlink_targets"]=True;self.assertHold(d)
    def test_31_no_restoration_even_if_candidate(self):
        d=evidence();d["link_target_checks"].update({"absolute_symlink_targets":0,"non_escalating_relative_symlink_targets":3273});d["unsafe_symlink_targets"]=0
        self.assertFalse(self.gate(d)["destructive_cleanup_authorized"])


if __name__ == "__main__":unittest.main()
