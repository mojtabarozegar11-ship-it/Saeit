"""Non-network Passenger UAPI matching — redacted, source-only, fail-closed."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from scripts import mpw_passenger_root_reconciliation_20261114 as m
from scripts.mojplaywin_cpanel_readonly_inventory import sanitize

ROOT = Path(__file__).resolve().parents[1]
STAGE = "/home/zomorod2/Saeit-staging"
PUBLIC = "/home/zomorod2/mojplaywin.com"


def evidence(root=STAGE, uri="/", records=2):
    clean = sanitize({
        "result": {"status":1, "data": [
            {"domain":"mojplaywin.com","base_uri":uri,"app_root":root},
            {"domain":"example.org","base_uri":"/","app_root":"/home/other/app"},
        ]}
    })
    clean["uapi_records_discovered"] = records
    return clean


class PassengerRootReconciliation(unittest.TestCase):
    def test_01_real_sanitizer_stage_exact_match(self):
        r=m.inspect(evidence())
        self.assertTrue(r["source_root_matches_staging_candidate"])

    def test_02_stage_registration_does_not_attest_effective_worker(self):
        self.assertFalse(m.inspect(evidence())["effective_wsgi_worker_attested"])

    def test_03_public_root_classified_separately(self):
        self.assertTrue(m.inspect(evidence(PUBLIC))["source_root_matches_public_candidate"])

    def test_04_unrelated_root_is_mismatch_not_commerce_proof(self):
        r=m.inspect(evidence("/other/location","/internal-path/"))
        self.assertTrue(r["root_registration_mismatch"])
        self.assertFalse(r["source_root_matches_either_candidate"])

    def test_05_missing_mapping_stays_unproved(self):
        x=evidence();x["mojplaywin_passenger_mappings"]=[]
        self.assertFalse(m.inspect(x)["single_mpw_mapping"])

    def test_06_two_mappings_are_not_single_root_proof(self):
        x=evidence()
        x["mojplaywin_passenger_mappings"].append(
            dict(x["mojplaywin_passenger_mappings"][0],domain="www.mojplaywin.com"))
        self.assertFalse(m.inspect(x)["single_mpw_mapping"])

    def test_07_duplicate_mapping_rejected(self):
        x=evidence()
        x["mojplaywin_passenger_mappings"].append(x["mojplaywin_passenger_mappings"][0])
        with self.assertRaises(ValueError):m.inspect(x)

    def test_08_invalid_fingerprint_rejected(self):
        x=evidence();x["mojplaywin_passenger_mappings"][0]["app_root_fingerprint"]="../../secret"
        with self.assertRaises(ValueError):m.inspect(x)

    def test_09_uppercase_hash_rejected(self):
        x=evidence();x["mojplaywin_passenger_mappings"][0]["app_root_fingerprint"]="A"*16
        with self.assertRaises(ValueError):m.inspect(x)

    def test_10_wrong_domain_rejected(self):
        x=evidence();x["mojplaywin_passenger_mappings"][0]["domain"]="example.org"
        with self.assertRaises(ValueError):m.inspect(x)

    def test_11_raw_unredacted_path_rejected(self):
        x=evidence();x["mojplaywin_passenger_mappings"][0]["base_uri"]="/private/secret/"
        with self.assertRaises(ValueError):m.inspect(x)

    def test_12_root_alias_redacted_not_certified_slash(self):
        r=m.inspect(evidence("/other","/some-private-route/"))
        self.assertTrue(r["unlisted_base_uri"])
        self.assertFalse(r["base_uri_explicit_slash"])

    def test_13_slash_registered_but_not_worker_proof(self):
        r=m.inspect(evidence())
        self.assertTrue(r["base_uri_explicit_slash"])
        self.assertFalse(r["effective_django_template_attested"])

    def test_14_owner_policy_can_never_be_auto_approved(self):
        self.assertFalse(m.inspect(evidence())["release_permitted"])

    def test_15_source_match_cannot_attest_db_migration(self):
        self.assertFalse(m.inspect(evidence())["migration_applied_attested"])

    def test_16_source_match_cannot_attest_customer_purchase(self):
        self.assertFalse(m.inspect(evidence())["checkout_email_post_attested"])

    def test_17_source_match_cannot_attest_chain_finality(self):
        self.assertFalse(m.inspect(evidence())["paid_settlement_attested"])

    def test_18_source_match_cannot_attest_private_delivery(self):
        self.assertFalse(m.inspect(evidence())["customer_entitlement_attested"])

    def test_19_source_match_cannot_attest_live_csp(self):
        self.assertFalse(m.inspect(evidence())["correct_public_csp_attested"])

    def test_20_source_match_cannot_attest_dynamic_catalog(self):
        self.assertFalse(m.inspect(evidence())["dynamic_store_attested"])

    def test_21_actual_money_is_unknown_not_zero(self):
        self.assertIsNone(m.inspect(evidence())["actual_collected_revenue"])

    def test_22_no_secret_or_sensitive_root_in_json_output(self):
        serialized=json.dumps(m.inspect(evidence()))
        self.assertNotIn("/home/",serialized)
        self.assertNotIn("example.org",serialized)

    def test_23_non_boolean_release_report_rejected(self):
        x=evidence();x["release_permitted"]=None
        with self.assertRaises(ValueError):m.inspect(x)

    def test_24_spoofed_isolation_proof_rejected(self):
        x=evidence();x["production_isolation_proven"]=True
        with self.assertRaises(ValueError):m.inspect(x)

    def test_25_spoofed_backup_proof_rejected(self):
        x=evidence();x["recoverable_backups_verified"]=True
        with self.assertRaises(ValueError):m.inspect(x)

    def test_26_report_with_raw_roots_flag_rejected(self):
        x=evidence();x["secrets_or_full_app_root_paths_printed"]=True
        with self.assertRaises(ValueError):m.inspect(x)

    def test_27_malformed_record_count_rejected(self):
        x=evidence();x["uapi_records_discovered"]=-1
        with self.assertRaises(ValueError):m.inspect(x)

    def test_28_mapping_exceeds_count_rejected(self):
        x=evidence();x["uapi_records_discovered"]=0
        with self.assertRaises(ValueError):m.inspect(x)

    def test_29_non_boolean_staging_flag_rejected(self):
        x=evidence();x["mojplaywin_passenger_mappings"][0]["references_shared_saeit_staging"]="false"
        with self.assertRaises(ValueError):m.inspect(x)

    def test_30_allowlisted_protected_route_still_not_root_slash(self):
        r=m.inspect(evidence(STAGE,"/picm/"))
        self.assertFalse(r["base_uri_explicit_slash"])

    def test_31_duplicate_json_key_is_refused(self):
        stream=io.BytesIO(b'{"classification":"READ_ONLY_PASSENGER_INVENTORY","classification":"bad"}')
        with self.assertRaises(ValueError):m.load_sanitized(stream)

    def test_32_nonfinite_json_refused(self):
        stream=io.BytesIO(b'{"classification":"READ_ONLY_PASSENGER_INVENTORY","value":NaN}')
        with self.assertRaises(ValueError):m.load_sanitized(stream)

    def test_33_oversized_payload_refused(self):
        stream=io.BytesIO(b"{" + b" "*m.MAX_INPUT_BYTES + b"}")
        with self.assertRaises(ValueError):m.load_sanitized(stream)

    def test_34_raw_uapi_report_rejected(self):
        stream=io.BytesIO(b'{"result":{"status":1,"data":[]}}')
        with self.assertRaises(ValueError):m.load_sanitized(stream)

    def test_35_valid_sanitized_json_loaded(self):
        x=evidence();data=json.dumps(x).encode()
        self.assertEqual(m.load_sanitized(io.BytesIO(data))["classification"],
                         "READ_ONLY_PASSENGER_INVENTORY")

    def test_36_main_cli_keeps_mismatch_redacted(self):
        x=evidence("/home/something/unrelated","/some-unlisted-path/")
        proc=subprocess.run([sys.executable,str(ROOT/"scripts/mpw_passenger_root_reconciliation_20261114.py")],
                            input=json.dumps(x),capture_output=True,text=True,timeout=10,cwd=ROOT)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertIn('"root_registration_mismatch":true',proc.stdout)
        self.assertNotIn("/home/something",proc.stdout)

    def test_37_invalid_cli_has_fixed_error_only(self):
        proc=subprocess.run([sys.executable,str(ROOT/"scripts/mpw_passenger_root_reconciliation_20261114.py")],
                            input='{"secret":"untrusted"}',capture_output=True,text=True,timeout=10,cwd=ROOT)
        self.assertEqual(proc.returncode,2)
        self.assertEqual(proc.stdout.strip(),"MPW_PASSENGER_RECONCILIATION=INVALID_SANITIZED_EVIDENCE")

    def test_38_canonical_identity_fixed(self):
        self.assertEqual(m.inspect(evidence())["canonical_bot"],"mojtaba.bot.ai")

    def test_39_no_database_or_customer_access(self):
        r=m.inspect(evidence())
        self.assertFalse(r["customer_data_read"])
        self.assertFalse(r["external_network_access"])
        self.assertFalse(r["files_modified"])

    def test_40_sanitizer_and_reconciler_use_same_exact_digest(self):
        x=evidence(STAGE)
        expected=hashlib.sha256(STAGE.encode("utf-8")).hexdigest()[:16]
        self.assertEqual(x["mojplaywin_passenger_mappings"][0]["app_root_fingerprint"],expected)
        self.assertTrue(m.inspect(x)["source_root_matches_staging_candidate"])
