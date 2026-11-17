"""Offline adversarial static-page replacement preflight; no network or file writes."""
import hashlib
import unittest
from scripts import mojprop_public_live_static_exact_guard_20261118 as guard

OLD=(b'<!-- MOJ_PROP_CATALOG_RELEASE_V4 -->\n'
     b'<html><select id="horizon"><option>week</option></select></html>')
NEW=(b'<html><h1>MOJ-PROP-01</h1>'
     b'<a>Contact MOJ PROP about Plan 1 (free)</a>'
     b'<p>do not send the bearer token by email</p>'
     b'<strong>Do not send money today.</strong></html>')


def classify(old=OLD,new=NEW):
    return guard.classify(old,new,
       old_sha=hashlib.sha256(OLD).hexdigest(),old_size=len(OLD),
       new_sha=hashlib.sha256(NEW).hexdigest(),new_size=len(NEW))


class FixedHashSafeReleaseTests(unittest.TestCase):
    def fail(self,old=OLD,new=NEW):
        with self.assertRaises(guard.StaticSourceIdentityRejected):
            classify(old,new)

    def test_01_expected_two_reviewed_inputs_accepted_as_evidence_only(self):
        self.assertTrue(classify()["candidate_source_matches_documented_code"])

    def test_02_paid_deploy_never_unlocked(self):
        self.assertFalse(classify()["release_allowed"])

    def test_03_live_passenger_never_assumed(self):
        self.assertFalse(classify()["cPanel_live_passenger_backend_proven"])

    def test_04_fresh_backup_not_guessed(self):
        self.assertFalse(classify()["fresh_restorable_offsite_backup_proven"])

    def test_05_case_specific_owner_permission_still_needed(self):
        self.assertFalse(classify()["owner_case_specific_deploy_approval_obtained"])

    def test_06_past_public_content_tampered_rejected(self):
        self.fail(old=OLD.replace(b"week",b"day!"))

    def test_07_candidate_page_tampered_rejected(self):
        self.fail(new=NEW+b" ")

    def test_08_no_prior_page_rejected(self):
        self.fail(old=b"")

    def test_09_no_candidate_page_rejected(self):
        self.fail(new=b"")

    def test_10_non_bytes_rejected(self):
        self.fail(old="hello")

    def test_11_unknown_old_template_family_rejected(self):
        original=b'<html><select id="horizon"></select></html>'
        with self.assertRaisesRegex(guard.StaticSourceIdentityRejected,"unexpected public"):
            guard.classify(original,NEW,
                old_sha=hashlib.sha256(original).hexdigest(),old_size=len(original),
                new_sha=hashlib.sha256(NEW).hexdigest(),new_size=len(NEW))

    def test_12_old_missing_real_public_form_rejected(self):
        original=b'<!-- MOJ_PROP_CATALOG_RELEASE_V4 -->\n<html></html>'
        with self.assertRaisesRegex(guard.StaticSourceIdentityRejected,"old|previous"):
            guard.classify(original,NEW,
                old_sha=hashlib.sha256(original).hexdigest(),old_size=len(original),
                new_sha=hashlib.sha256(NEW).hexdigest(),new_size=len(NEW))

    def invalid_candidate_section(self,payload,expected):
        with self.assertRaisesRegex(guard.StaticSourceIdentityRejected,expected):
            guard.classify(OLD,payload,
                old_sha=hashlib.sha256(OLD).hexdigest(),old_size=len(OLD),
                new_sha=hashlib.sha256(payload).hexdigest(),new_size=len(payload))

    def test_13_not_other_product(self):
        self.invalid_candidate_section(NEW.replace(b"MOJ-PROP-01",b"OTHER-PLAN01"),
                                      "genuine challenge")

    def test_14_missing_safe_contact_rejected(self):
        self.invalid_candidate_section(NEW.replace(b"Contact MOJ PROP about Plan 1 (free)",b"Paid enrollment now"),
                                      "prelaunch contact")

    def test_15_private_receipt_warning_required(self):
        self.invalid_candidate_section(NEW.replace(b"do not send the bearer token by email",b"Email your private bearer token"),
                                      "receipt privacy")

    def test_16_must_not_ask_for_payment(self):
        self.invalid_candidate_section(NEW.replace(b"Do not send money today.",b"Pay us 30 TRX now."),
                                      "anti-payment")

    def test_17_must_never_link_known_dead_optin(self):
        self.invalid_candidate_section(NEW+b'href="/moj-prop-interest/form/"',
                                      "production-404")

    def test_18_mutable_list_not_bytes(self):
        self.fail(new=list(NEW))

    def test_19_oversized_source_rejected(self):
        self.fail(old=b"X"*(guard.MAX_HTML_BYTES+1))

    def test_20_different_live_page_after_release_rejected(self):
        self.fail(old=NEW)

    def test_21_both_urls_are_static_known_canonical_site(self):
        self.assertEqual(classify()["public_url"],"https://mojplaywin.com/moj-prop/")

    def test_22_does_not_treat_match_as_an_actual_sale(self):
        self.assertFalse(classify()["payment_opened"])
        self.assertFalse(classify()["lead_created"])

    def test_23_no_personal_data_is_used(self):
        self.assertFalse(classify()["private_customer_data_read"])

    def test_24_public_change_is_blocked_if_source_sha_mismatches(self):
        self.fail(new=NEW+b" <!-- stale -->")


if __name__=="__main__":
    unittest.main()
