"""Synthetic-only root proof reconciliation tests — no SSH, commerce or paths."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

from scripts import mpw_readonly_app_root_evidence_join_20261114 as x
from scripts.mojplaywin_cpanel_readonly_inventory import sanitize


def reports(path="/home/zomorod2/example-registration",scan="bounded_immediate_home_scan"):
    fp=hashlib.sha256(path.encode()).hexdigest()[:16]
    uapi=sanitize({"result":{"status":1,"data":[
        {"domain":"mojplaywin.com","base_uri":"/","app_root":path},
        {"domain":"other.example","base_uri":"/","app_root":"/elsewhere"},
    ]}})
    source={
        "schema":"mpw.cpanel.source_provenance.readonly.v1",
        "customer_data_read":False,
        "database_accessed":False,
        "files_modified":False,
        "production_release_permitted_by_this_report":False,
        "neighbor_root_fingerprints":{
            "status":scan,
            "release_permitted":False,
            "effective_passenger_worker_attested":False,
            "candidate_count":1 if scan=="bounded_immediate_home_scan" else 0,
            "candidates":[{"root_sha256_prefix":fp,
                           "marker_class":"wsgi_marker_only",
                           "registered_root_verified":False,
                           "effective_checkout_verified":False}]
                         if scan=="bounded_immediate_home_scan" else [],
        },
    }
    return uapi,source


class EvidenceJoinTests(unittest.TestCase):
    def test_01_matching_fingerprint_classified_as_source_candidate_only(self):
        u,s=reports()
        self.assertEqual(x.compare(u,s)["classification"],
                         "one_immediate_root_fingerprint_corresponds")

    def test_02_source_correspondence_is_not_passenger_worker_proof(self):
        u,s=reports()
        self.assertFalse(x.compare(u,s)["effective_passenger_worker_verified"])

    def test_03_source_correspondence_cannot_authorize_release(self):
        u,s=reports()
        self.assertFalse(x.compare(u,s)["release_permitted"])

    def test_04_source_correspondence_cannot_verify_checkout_template(self):
        u,s=reports()
        self.assertFalse(x.compare(u,s)["effective_checkout_template_verified"])

    def test_05_source_correspondence_cannot_verify_settlement(self):
        u,s=reports()
        self.assertFalse(x.compare(u,s)["payment_finality_verified"])

    def test_06_source_correspondence_cannot_verify_paid_delivery(self):
        u,s=reports()
        self.assertFalse(x.compare(u,s)["paid_delivery_verified"])

    def test_07_revenue_unknown_not_zero(self):
        u,s=reports()
        self.assertIsNone(x.compare(u,s)["actual_collected_revenue"])

    def test_08_output_contains_no_home_directory_path(self):
        u,s=reports()
        self.assertNotIn("/home/",json.dumps(x.compare(u,s)))

    def test_09_output_contains_single_canonical_bot(self):
        u,s=reports()
        self.assertEqual(x.compare(u,s)["canonical_bot"],"mojtaba.bot.ai")

    def test_10_different_uapi_root_not_found_in_scan(self):
        u,s=reports()
        s["neighbor_root_fingerprints"]["candidates"][0]["root_sha256_prefix"]="f"*16
        self.assertEqual(x.compare(u,s)["classification"],
                         "no_immediate_root_fingerprint_corresponds")

    def test_11_entry_overflow_is_incomplete_not_root_missing(self):
        u,s=reports(scan="entry_budget_exceeded")
        self.assertEqual(x.compare(u,s)["classification"],
                         "bounded_source_scan_incomplete")

    def test_12_missing_home_is_not_negative_root_proof(self):
        u,s=reports(scan="home_unavailable_or_unsafe")
        self.assertEqual(x.compare(u,s)["classification"],
                         "bounded_source_scan_incomplete")

    def test_13_multiple_uapi_roots_stay_ambiguous(self):
        u,s=reports()
        u["mojplaywin_passenger_mappings"].append({
            "domain":"www.mojplaywin.com","base_uri":"/",
            "app_root_fingerprint":"a"*16,
            "references_shared_saeit_staging":False})
        self.assertEqual(x.compare(u,s)["classification"],
                         "missing_or_multiple_uapi_roots")

    def test_14_zero_uapi_roots_is_not_match(self):
        u,s=reports()
        u["mojplaywin_passenger_mappings"]=[]
        self.assertEqual(x.compare(u,s)["classification"],
                         "missing_or_multiple_uapi_roots")

    def test_15_duplicate_uapi_digest_rejected(self):
        u,s=reports()
        u["mojplaywin_passenger_mappings"].append(
            dict(u["mojplaywin_passenger_mappings"][0]))
        with self.assertRaises(ValueError):x.compare(u,s)

    def test_16_duplicate_source_digest_rejected(self):
        u,s=reports()
        a=s["neighbor_root_fingerprints"]["candidates"][0]
        s["neighbor_root_fingerprints"]["candidates"].append(dict(a))
        s["neighbor_root_fingerprints"]["candidate_count"]=2
        with self.assertRaises(ValueError):x.compare(u,s)

    def test_17_conflicting_source_candidate_count_rejected(self):
        u,s=reports()
        s["neighbor_root_fingerprints"]["candidate_count"]=0
        with self.assertRaises(ValueError):x.compare(u,s)

    def test_18_invalid_hex_root_rejected(self):
        u,s=reports()
        s["neighbor_root_fingerprints"]["candidates"][0]["root_sha256_prefix"]="not-hex"
        with self.assertRaises(ValueError):x.compare(u,s)

    def test_19_unknown_marker_class_rejected(self):
        u,s=reports()
        s["neighbor_root_fingerprints"]["candidates"][0]["marker_class"]="exec_command"
        with self.assertRaises(ValueError):x.compare(u,s)

    def test_20_spoofed_worker_attestation_rejected(self):
        u,s=reports()
        s["neighbor_root_fingerprints"]["effective_passenger_worker_attested"]=True
        with self.assertRaises(ValueError):x.compare(u,s)

    def test_21_spoofed_registered_root_attestation_rejected(self):
        u,s=reports()
        s["neighbor_root_fingerprints"]["candidates"][0]["registered_root_verified"]=True
        with self.assertRaises(ValueError):x.compare(u,s)

    def test_22_unredacted_uapi_rejected(self):
        u,s=reports()
        u["secrets_or_full_app_root_paths_printed"]=True
        with self.assertRaises(ValueError):x.compare(u,s)

    def test_23_uapi_release_permission_true_rejected(self):
        u,s=reports()
        u["release_permitted"]=True
        with self.assertRaises(ValueError):x.compare(u,s)

    def test_24_source_release_permission_true_rejected(self):
        u,s=reports()
        s["production_release_permitted_by_this_report"]=True
        with self.assertRaises(ValueError):x.compare(u,s)

    def test_25_source_customer_data_read_assertion_rejected(self):
        u,s=reports()
        s["customer_data_read"]=True
        with self.assertRaises(ValueError):x.compare(u,s)

    def test_26_wrong_source_schema_rejected(self):
        u,s=reports()
        s["schema"]="untrusted"
        with self.assertRaises(ValueError):x.compare(u,s)

    def test_27_wrong_uapi_classification_rejected(self):
        u,s=reports()
        u["classification"]="RAW_UAPI"
        with self.assertRaises(ValueError):x.compare(u,s)

    def test_28_duplicate_json_keys_rejected(self):
        data=b'{"uapi":{},"uapi":{},"source":{}}'
        with self.assertRaises(ValueError):x.read_bounded(io.BytesIO(data))

    def test_29_bad_json_constant_rejected(self):
        with self.assertRaises(ValueError):
            x.read_bounded(io.BytesIO(b'{"uapi":NaN,"source":{}}'))

    def test_30_raw_payload_missing_wrapper_rejected(self):
        with self.assertRaises(ValueError):
            x.read_bounded(io.BytesIO(b'{"result":{"status":1}}'))

    def test_31_payload_over_limit_rejected(self):
        with self.assertRaises(ValueError):
            x.read_bounded(io.BytesIO(b"{" + b" "*x.MAX_INPUT + b"}"))

    def test_32_valid_report_pair_parsed(self):
        u,s=reports()
        self.assertEqual(x.read_bounded(io.BytesIO(
            json.dumps({"uapi":u,"source":s}).encode()))["uapi"]["classification"],
            "READ_ONLY_PASSENGER_INVENTORY")

    def test_33_malformed_domain_rejected(self):
        u,s=reports()
        u["mojplaywin_passenger_mappings"][0]["domain"]="attacker.example"
        with self.assertRaises(ValueError):x.compare(u,s)

    def test_34_cli_matching_synthetic_does_not_show_private_path(self):
        u,s=reports()
        root=Path(__file__).resolve().parents[1]
        p=subprocess.run([sys.executable,str(root/"scripts/mpw_readonly_app_root_evidence_join_20261114.py")],
                         input=json.dumps({"uapi":u,"source":s}),
                         text=True,capture_output=True,timeout=10,cwd=root)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn("one_immediate_root_fingerprint_corresponds",p.stdout)
        self.assertNotIn("/home/",p.stdout)

    def test_35_invalid_cli_has_fixed_no_secret_message(self):
        root=Path(__file__).resolve().parents[1]
        p=subprocess.run([sys.executable,str(root/"scripts/mpw_readonly_app_root_evidence_join_20261114.py")],
                         input='{"secret":"private"}',text=True,capture_output=True,timeout=10,cwd=root)
        self.assertEqual(p.returncode,2)
        self.assertEqual(p.stdout.strip(),"MPW_ROOT_EVIDENCE_JOIN=INVALID_SANITIZED_INPUT")
