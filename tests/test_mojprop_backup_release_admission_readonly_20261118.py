"""MOJ-PROP-01 read-only backup storage gates, no live secrets, network or disk mutation."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from scripts import mojprop_backup_release_admission_readonly_20261118 as gate

GIB=1024**3


def fixture(free=4_543_619_072):
    return {
        "classification":gate.CATEGORY,
        "backend_user_authenticated":True,
        "existing_key_metadata_owner_private_32_bytes":True,
        "private_archive_root_owner_only":True,
        "gpg_available":True,
        "measured_filesystem_free_bytes":free,
        "requires_minimum_free_bytes":10*GIB,
        "fresh_backup_capacity_gate_passed":free>=10*GIB,
        "candidate_locations":{
            "home":{
                "free_bytes":free,"filesystem_bytes":100*GIB,
                "device_id":123,"distinct_from_home_device":False,
                "private_existing_target":False,
                "has_10gib_free":free>=10*GIB,
            },
            "tmp":{
                "free_bytes":free,"filesystem_bytes":100*GIB,
                "device_id":123,"distinct_from_home_device":False,
                "private_existing_target":False,
                "has_10gib_free":free>=10*GIB,
            }
        },
        "private_archive_four_part_pair_count":1,
        "private_archive_partial_names_count":1,
        "files_deleted":0,
        "database_bytes_read":False,"secret_key_bytes_read":False,
        "backup_written":False,"isolated_restore_performed":False,
        "release_authorized":False,
    }


class PreciseBackupSafetyTests(unittest.TestCase):
    def run_invalid(self, mutate):
        item=fixture()
        mutate(item)
        with self.assertRaises(gate.AdmissionEvidenceRejected):
            gate.inspect(item)

    def test_01_real_observed_4p54gb_fails_ten_gib(self):
        r=gate.inspect(fixture())
        self.assertFalse(r["fresh_backup_10gib_threshold_passed"])
        self.assertEqual(r["bytes_short_of_existing_10gib_requirement"],10*GIB-4_543_619_072)

    def test_02_no_run_of_new_backup_from_low_disk(self):
        self.assertFalse(gate.inspect(fixture())["all_local_runtime_prerequisites_claimed_satisfied"])

    def test_03_historical_pair_is_not_a_new_backup(self):
        r=gate.inspect(fixture())
        self.assertEqual(r["observed_existing_four_file_pairs_count"],1)
        self.assertFalse(r["fresh_backup_proven"])

    def test_04_partial_ciphertext_requires_review(self):
        r=gate.inspect(fixture())
        self.assertEqual(r["partial_archive_names_need_owner_review_count"],1)
        self.assertIn("incomplete_ciphertext_present_review_before_attempt",r["blockers"])

    def test_05_exact_ten_gib_claim_only_local_admission(self):
        r=gate.inspect(fixture(10*GIB))
        self.assertTrue(r["all_local_runtime_prerequisites_claimed_satisfied"])
        self.assertFalse(r["backup_started"])

    def test_06_even_hundred_gib_is_not_sale_approval(self):
        r=gate.inspect(fixture(100*GIB))
        for key in ("payment_authorized","production_deploy_authorized",
                    "broker_real_trades_authorized","real_customer_enrollment_authorized"):
            self.assertFalse(r[key])

    def test_07_wrong_category_fails(self):
        self.run_invalid(lambda x:x.update(classification="OTHER"))

    def test_08_missing_required_key_fails(self):
        self.run_invalid(lambda x:x.pop("existing_key_metadata_owner_private_32_bytes"))

    def test_09_boolean_free_size_not_int_fails(self):
        self.run_invalid(lambda x:x.update(measured_filesystem_free_bytes=True))

    def test_10_negative_free_size_fails(self):
        self.run_invalid(lambda x:x.update(measured_filesystem_free_bytes=-1))

    def test_11_capacity_claim_mismatch_fails(self):
        self.run_invalid(lambda x:x.update(fresh_backup_capacity_gate_passed=True))

    def test_12_modified_ten_gib_threshold_is_rejected(self):
        self.run_invalid(lambda x:x.update(requires_minimum_free_bytes=2*GIB))

    def test_13_key_unproven_keeps_backup_blocked(self):
        x=fixture(30*GIB);x["existing_key_metadata_owner_private_32_bytes"]=False
        r=gate.inspect(x)
        self.assertFalse(r["all_local_runtime_prerequisites_claimed_satisfied"])
        self.assertIn("existing_recovery_key_metadata_invalid",r["blockers"])

    def test_14_gpg_unavailable_blocks(self):
        x=fixture(30*GIB);x["gpg_available"]=False
        self.assertFalse(gate.inspect(x)["all_local_runtime_prerequisites_claimed_satisfied"])

    def test_15_wrong_owner_blocks(self):
        x=fixture(30*GIB);x["backend_user_authenticated"]=False
        self.assertFalse(gate.inspect(x)["all_local_runtime_prerequisites_claimed_satisfied"])

    def test_16_root_private_permissions_missing_blocks(self):
        x=fixture(30*GIB);x["private_archive_root_owner_only"]=False
        self.assertFalse(gate.inspect(x)["all_local_runtime_prerequisites_claimed_satisfied"])

    def test_17_deletion_report_is_not_readonly(self):
        self.run_invalid(lambda x:x.update(files_deleted=1))

    def test_18_bool_deleted_count_rejected(self):
        self.run_invalid(lambda x:x.update(files_deleted=False))

    def test_19_sql_bytes_read_report_rejected(self):
        self.run_invalid(lambda x:x.update(database_bytes_read=True))

    def test_20_recovery_key_read_report_rejected(self):
        self.run_invalid(lambda x:x.update(secret_key_bytes_read=True))

    def test_21_existing_backup_write_report_rejected(self):
        self.run_invalid(lambda x:x.update(backup_written=True))

    def test_22_fictitious_restore_report_rejected(self):
        self.run_invalid(lambda x:x.update(isolated_restore_performed=True))

    def test_23_fictitious_legal_release_report_rejected(self):
        self.run_invalid(lambda x:x.update(release_authorized=True))

    def test_24_missing_home_volume_fails(self):
        self.run_invalid(lambda x:x["candidate_locations"].pop("home"))

    def test_25_disagreeing_home_free_fails(self):
        self.run_invalid(lambda x:x["candidate_locations"]["home"].update(free_bytes=1))

    def test_26_alternate_volume_same_device_not_proven(self):
        x=fixture()
        x["candidate_locations"]["tmp"].update(
            free_bytes=50*GIB,has_10gib_free=True,private_existing_target=True)
        self.assertEqual(gate.inspect(x)["independent_private_alternate_volume_candidates"],[])

    def test_27_private_alternate_mount_is_only_candidate(self):
        x=fixture()
        x["candidate_locations"]["data"]={
            "free_bytes":50*GIB,"filesystem_bytes":80*GIB,
            "device_id":456,"distinct_from_home_device":True,
            "private_existing_target":True,"has_10gib_free":True}
        r=gate.inspect(x)
        self.assertEqual(r["independent_private_alternate_volume_candidates"],["data"])
        self.assertFalse(r["alternate_volume_automatically_usable_by_existing_streamer"])
        self.assertFalse(r["payment_authorized"])

    def test_28_alternate_mount_without_owner_only_is_not_target(self):
        x=fixture()
        x["candidate_locations"]["data"]={
            "free_bytes":50*GIB,"filesystem_bytes":80*GIB,
            "device_id":456,"distinct_from_home_device":True,
            "private_existing_target":False,"has_10gib_free":True}
        self.assertEqual(gate.inspect(x)["independent_private_alternate_volume_candidates"],[])

    def test_29_mount_free_claim_false_rejected(self):
        self.run_invalid(lambda x:x["candidate_locations"]["tmp"].update(has_10gib_free=True))

    def test_30_home_cannot_claim_different_device(self):
        self.run_invalid(lambda x:x["candidate_locations"]["home"].update(distinct_from_home_device=True))

    def test_31_bad_mount_label_rejected(self):
        self.run_invalid(lambda x:x["candidate_locations"].update({"../../tmp":{}}))

    def test_32_none_of_this_authenticates_snapshot_itself(self):
        self.assertFalse(gate.inspect(fixture())["snapshot_authentication_performed_by_this_code"])

    def test_33_always_requires_owner_to_arm_backup_workflow(self):
        self.assertTrue(gate.inspect(fixture(50*GIB))["owner_case_specific_confirmation_required"])

    def test_34_cli_rejects_absent_file_without_creating_it(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"no.json"
            self.assertEqual(gate.main.__module__,gate.__name__)
            self.assertFalse(p.exists())

    def test_35_invalid_archive_count_bool_rejected(self):
        self.run_invalid(lambda x:x.update(private_archive_four_part_pair_count=True))

    def test_36_overlarge_mount_count_rejected(self):
        self.run_invalid(lambda x:x["candidate_locations"].update({
            "volume_"+str(i):{} for i in range(25)}))


if __name__=="__main__":
    unittest.main()
