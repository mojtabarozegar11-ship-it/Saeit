"""Portable production-policy tests; intentionally independent of Django.

Run: python -m unittest tests/test_company_inquiry_policy_portable_20261114.py
"""
import unittest

from core import company_inquiry_policy as policy

FP_A = "a" * 64
FP_B = "b" * 64
NOW = 9000


def row(fp=FP_A, when=NOW, pk=1):
    return {"fingerprint": fp, "created": when, "inquiry_id": pk}


class PolicyTests(unittest.TestCase):
    def test_empty_history(self): self.assertEqual(policy.clean_history([], NOW), [])
    def test_nonlist_is_ignored(self): self.assertEqual(policy.clean_history({}, NOW), [])
    def test_bad_now_denied(self): self.assertEqual(policy.clean_history([row()], "9000"), [])
    def test_negative_now_denied(self): self.assertEqual(policy.clean_history([row()], -1), [])
    def test_current_record_kept(self): self.assertEqual(policy.clean_history([row()], NOW), [row()])
    def test_future_record_removed(self): self.assertEqual(policy.clean_history([row(when=NOW+1)], NOW), [])
    def test_expired_record_removed(self): self.assertEqual(policy.clean_history([row(when=NOW-3600)], NOW), [])
    def test_just_within_hour_kept(self): self.assertEqual(policy.clean_history([row(when=NOW-3599)], NOW), [row(when=NOW-3599)])
    def test_bool_id_removed(self): self.assertEqual(policy.clean_history([row(pk=True)], NOW), [])
    def test_zero_id_removed(self): self.assertEqual(policy.clean_history([row(pk=0)], NOW), [])
    def test_bool_timestamp_removed(self): self.assertEqual(policy.clean_history([row(when=True)], NOW), [])
    def test_invalid_fingerprint_removed(self): self.assertEqual(policy.clean_history([row(fp="bad")], NOW), [])
    def test_uppercase_fingerprint_removed(self): self.assertEqual(policy.clean_history([row(fp="A"*64)], NOW), [])
    def test_unknown_fields_removed(self): self.assertEqual(policy.clean_history([{**row(), "customer_email":"private@example.com"}], NOW), [])
    def test_newest_same_fp_wins(self): self.assertEqual(policy.clean_history([row(when=NOW-5),row(when=NOW,pk=2)],NOW),[row(when=NOW,pk=2)])
    def test_a_b_a_preserves_first_reference(self): self.assertEqual(policy.replay_inquiry_id([row(),row(fp=FP_B,pk=2)],FP_A,NOW),1)
    def test_replay_boundary_included(self): self.assertEqual(policy.replay_inquiry_id([row(when=NOW-899)],FP_A,NOW),1)
    def test_replay_boundary_excluded(self): self.assertIsNone(policy.replay_inquiry_id([row(when=NOW-900)],FP_A,NOW))
    def test_replay_invalid_fp_rejected(self): self.assertIsNone(policy.replay_inquiry_id([row()],"not-a-hash",NOW))
    def test_replay_no_match(self): self.assertIsNone(policy.replay_inquiry_id([row()],FP_B,NOW))
    def test_accept_when_five(self): self.assertTrue(policy.can_create([row(fp=f"{x:x}"*64,pk=x+1) for x in range(5)],NOW))
    def test_reject_when_six(self): self.assertFalse(policy.can_create([row(fp=f"{x:x}"*64,pk=x+1) for x in range(6)],NOW))
    def test_add_sixth(self): self.assertEqual(len(policy.add_new([row(fp=f"{x:x}"*64,pk=x+1) for x in range(5)],FP_A,NOW,77)),6)
    def test_reject_add_seventh(self):
        with self.assertRaises(ValueError): policy.add_new([row(fp=f"{x:x}"*64,pk=x+1) for x in range(6)],FP_A,NOW,77)
    def test_reject_add_bad_fp(self):
        with self.assertRaises(ValueError): policy.add_new([],"bad",NOW,1)
    def test_reject_add_bad_pk(self):
        with self.assertRaises(ValueError): policy.add_new([],FP_A,NOW,True)
    def test_reject_add_negative_timestamp(self):
        with self.assertRaises(ValueError): policy.add_new([],FP_A,-1,1)
    def test_provenance_good(self): self.assertTrue(policy.provenance("commercial",policy.FARM_SUBJECT,"INTAKE_CONSENT_V1; confirmed_at=2026-11-14T12:00:00+00:00; source=farm"))
    def test_provenance_fake_subject_only(self): self.assertFalse(policy.provenance("commercial",policy.FARM_SUBJECT,""))
    def test_provenance_generic_source_rejected(self): self.assertFalse(policy.provenance("commercial",policy.FARM_SUBJECT,"INTAKE_CONSENT_V1; confirmed_at=x; source=company"))
    def test_provenance_noncommercial_rejected(self): self.assertFalse(policy.provenance("research",policy.FARM_SUBJECT,"INTAKE_CONSENT_V1; confirmed_at=x; source=farm"))
    def test_provenance_nonfarm_title_rejected(self): self.assertFalse(policy.provenance("commercial","other","INTAKE_CONSENT_V1; confirmed_at=x; source=farm"))
    def test_provenance_injected_suffix_rejected(self): self.assertFalse(policy.provenance("commercial",policy.FARM_SUBJECT,"INTAKE_CONSENT_V1; confirmed_at=x; source=farm; source=company"))
    def test_provenance_none_rejected(self): self.assertFalse(policy.provenance("commercial",policy.FARM_SUBJECT,None))
    def test_staff_appended_notes_do_not_lose_verified_farm_status(self):
        self.assertTrue(policy.provenance("commercial",policy.FARM_SUBJECT,"INTAKE_CONSENT_V1; confirmed_at=x; source=farm\nSecond staff note"))
    def test_staff_note_cannot_forge_original_server_line(self):
        self.assertFalse(policy.provenance("commercial",policy.FARM_SUBJECT,"Other note\nINTAKE_CONSENT_V1; confirmed_at=x; source=farm"))
    def test_older_session_legacy_not_duplicated(self): self.assertEqual(policy.replay_inquiry_id([row(when=NOW-50)],FP_A,NOW),1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
