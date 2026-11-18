"""Strictly offline adversarial classification of owner VPS ciphertext allocation."""
import copy
import unittest
from scripts import mojprop_owner_archive_reclaim_planner_readonly_20261118 as guard

GIB=1024**3
def sample(free=4*GIB):
    cats={x:{"files":0,"allocated_bytes":0,"logical_bytes":0,
              "largest_allocated_bytes":0,"youngest_age_hours":None,
              "oldest_age_hours":None} for x in guard.KINDS}
    for kind,size in (
        ("mysql_gpg_complete",2*GIB),
        ("files_gpg_complete",int(.7*GIB)),
        ("partial_incomplete",int(1.5*GIB)),
        ("other_regular",int(2*GIB)),
    ):
        cats[kind]={"files":1,"allocated_bytes":size,"logical_bytes":size,
                    "largest_allocated_bytes":size,
                    "youngest_age_hours":400.0,"oldest_age_hours":400.0}
    return {
        "schema":guard.SCHEMA,
        "owner_verified":True,
        "private_root_valid":True,
        "all_entries_processed":True,
        "ciphertext_content_read":False,
        "manifest_content_read":False,
        "customer_identifiers_printed":False,
        "archive_names_printed":False,
        "production_changed":False,
        "backup_deleted":False,
        "backup_moved":False,
        "offsite_uploaded":False,
        "owner_release_authorized":False,
        "categories":cats,
        "filesystem_free_bytes":free,
        "bytes_short_of_10gib_start_gate":max(0,10*GIB-free),
        "entry_count":4,
        "unreadable_entries_count":0,
    }

class StrictArchiveDecisionTests(unittest.TestCase):
    def rejected(self,modifier):
        d=sample()
        modifier(d)
        with self.assertRaises(guard.UnsafeArchiveEvidence):
            guard.inspect(d)

    def test_01_4gib_has_exact_6gib_deficit(self):
        self.assertEqual(guard.inspect(sample())["bytes_still_missing_without_any_changes"],6*GIB)

    def test_02_no_direct_backup_execution(self):
        self.assertFalse(guard.inspect(sample())["backup_operation_performed"])

    def test_03_no_archive_delete_permission(self):
        r=guard.inspect(sample())
        self.assertEqual(r["archive_automatically_safe_to_remove_count"],0)
        self.assertEqual(r["bytes_safe_to_delete_now"],0)

    def test_04_no_buyer_release_or_trx_payment(self):
        self.assertFalse(guard.inspect(sample())["release_or_payment_permitted"])

    def test_05_no_automatic_restore_proof(self):
        self.assertFalse(guard.inspect(sample())["existing_backups_independently_restored"])

    def test_06_two_drive_copies_not_assumed(self):
        self.assertFalse(guard.inspect(sample())["two_independent_verified_offsite_copies"])

    def test_07_old_complete_files_are_not_final_backup(self):
        self.assertTrue(guard.inspect(sample())["existing_mysql_and_files_ciphertext_candidates_observed"])
        self.assertFalse(guard.inspect(sample())["archive_cleanup_case_specific_owner_authorization"])

    def test_08_never_claim_current_snapshot_authentication(self):
        self.assertFalse(guard.inspect(sample())["snapshot_independently_authenticated_by_this_pure_script"])

    def test_09_evidence_schema_required(self):
        self.rejected(lambda x:x.update(schema="fake"))

    def test_10_missing_category_rejected(self):
        self.rejected(lambda x:x["categories"].pop("mysql_gpg_complete"))

    def test_11_added_unknown_category_rejected(self):
        self.rejected(lambda x:x["categories"].update({"extra":{"files":0}}))

    def test_12_negative_size_rejected(self):
        self.rejected(lambda x:x["categories"]["partial_incomplete"].update(allocated_bytes=-1))

    def test_13_too_big_value_rejected(self):
        self.rejected(lambda x:x["categories"]["other_regular"].update(allocated_bytes=2**55))

    def test_14_fake_fresh_capacity_rejected(self):
        self.rejected(lambda x:x.update(bytes_short_of_10gib_start_gate=0))

    def test_15_bool_free_not_integer_rejected(self):
        self.rejected(lambda x:x.update(filesystem_free_bytes=False))

    def test_16_marked_content_read_rejected(self):
        self.rejected(lambda x:x.update(ciphertext_content_read=True))

    def test_17_reading_secret_manifest_not_metadata_only(self):
        self.rejected(lambda x:x.update(manifest_content_read=True))

    def test_18_personal_filename_disclosure_rejected(self):
        self.rejected(lambda x:x.update(archive_names_printed=True))

    def test_19_archive_delete_record_rejected(self):
        self.rejected(lambda x:x.update(backup_deleted=True))

    def test_20_archive_move_record_rejected(self):
        self.rejected(lambda x:x.update(backup_moved=True))

    def test_21_archive_upload_proof_must_be_separate(self):
        self.rejected(lambda x:x.update(offsite_uploaded=True))

    def test_22_owner_release_claim_rejected(self):
        self.rejected(lambda x:x.update(owner_release_authorized=True))

    def test_23_partial_scan_cannot_claim_completed(self):
        self.rejected(lambda x:x.update(entry_count=8))

    def test_24_unreadable_entry_cannot_claim_clean(self):
        self.rejected(lambda x:x.update(unreadable_entries_count=1))

    def test_25_oversized_largest_file_rejected(self):
        self.rejected(lambda x:x["categories"]["mysql_gpg_complete"].update(
            largest_allocated_bytes=9*GIB))

    def test_26_invalid_age_order_rejected(self):
        self.rejected(lambda x:x["categories"]["mysql_gpg_complete"].update(
            youngest_age_hours=500.0))

    def test_27_empty_class_with_bytes_rejected(self):
        self.rejected(lambda x:x["categories"]["directories"].update(allocated_bytes=1))

    def test_28_no_actual_bytes_freed_despite_many_files(self):
        r=guard.inspect(sample())
        self.assertGreater(r["allocated_bytes_of_all_classified_direct_regular_files_NOT_RECLAIMABLE_PROOF"],6*GIB)
        self.assertEqual(r["bytes_safe_to_delete_now"],0)

    def test_29_more_free_space_is_not_proof_of_restoration(self):
        r=guard.inspect(sample(20*GIB))
        self.assertTrue(r["sufficient_fresh_backup_capacity_without_changes"])
        self.assertFalse(r["existing_backups_independently_restored"])

    def test_30_missing_direct_ciphertext_does_not_infer_full_pair(self):
        x=sample()
        x["categories"]["files_gpg_complete"]={
            "files":0,"allocated_bytes":0,"logical_bytes":0,
            "largest_allocated_bytes":0,"youngest_age_hours":None,"oldest_age_hours":None}
        x["entry_count"]=3
        self.assertFalse(guard.inspect(x)["existing_mysql_and_files_ciphertext_candidates_observed"])

    def test_31_incomplete_scan_marked_partial_not_silent_full(self):
        x=sample();x["all_entries_processed"]=False;x["entry_count"]=2501
        r=guard.inspect(x)
        self.assertFalse(r["metadata_classification_complete_claim"])

    def test_32_directory_file_contents_are_not_double_counted(self):
        x=sample();x["categories"]["directories"]={
            "files":1,"allocated_bytes":4096,"logical_bytes":0,
            "largest_allocated_bytes":4096,"youngest_age_hours":400.0,
            "oldest_age_hours":400.0}
        x["entry_count"]=5
        r=guard.inspect(x)
        self.assertEqual(r["files_in_classes"],5)

    def test_33_false_positive_owner_rejected_as_complete(self):
        x=sample();x["owner_verified"]=False
        self.assertFalse(guard.inspect(x)["metadata_classification_complete_claim"])

    def test_34_whole_archive_space_not_treated_as_safe(self):
        x=sample();r=guard.inspect(x)
        self.assertEqual(r["cleanup_operation_performed"],False)
        self.assertIn(r["next_step"],(
            "secure_verified_offsite_then_restoration_then_owner_decision",
            "find_additional_private_capacity_without_deletion"))

    def test_35_attempt_to_claim_production_changed_rejected(self):
        self.rejected(lambda x:x.update(production_changed=True))

    def test_36_category_boolean_files_count_rejected(self):
        self.rejected(lambda x:x["categories"]["other_regular"].update(files=True))

if __name__=="__main__":
    unittest.main()
