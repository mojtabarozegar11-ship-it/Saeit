"""Synthetic exact cPanel UAPI registration source proof, no live calls."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from subprocess import TimeoutExpired
from types import SimpleNamespace
from unittest.mock import Mock

from scripts import mpw_onepass_cpanel_source_provenance_readonly_20261113 as m


class RegisteredRootEvidenceTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home=Path(temp.name)/"account"
        self.home.mkdir()
        self.root=self.home/"registered-mpw"
        self.root.mkdir()
        self.files={
            "wsgi":self.root/"passenger_wsgi.py",
            "manage":self.root/"manage.py",
            "store":self.root/"core/mojplaywin_views.py",
            "checkout":self.root/"mpw_commerce/product_checkout_page.py",
            "template":self.root/"mpw_commerce/templates/mpw_commerce/product_checkout.html",
        }
        for x in self.files.values():
            x.parent.mkdir(parents=True,exist_ok=True)
            x.write_bytes(b"synthetic safe source only\n")
        self.executed=[]

    def response(self, rows=None, *, status=1):
        if rows is None:
            rows=[{"domain":"mojplaywin.com","app_root":str(self.root),"base_uri":"/"}]
        return json.dumps({"result":{"status":status,"data":rows}}).encode()

    def runner(self, result=None, *, returncode=0, raised=None):
        payload=self.response() if result is None else result
        def one(cmd,**kw):
            self.executed.append((cmd,kw))
            if raised is not None:
                raise raised
            return SimpleNamespace(returncode=returncode,stdout=payload)
        return one

    def inspect(self, result=None, **kw):
        return m.inspect_uapi_registered_root(
            self.home,self.runner(result,**kw))

    def test_01_valid_exact_registered_directory_is_source_only(self):
        r=self.inspect()
        self.assertEqual(r["classification"],"registered_directory_has_commerce_source_on_disk")

    def test_02_all_five_expected_markers_counted(self):
        r=self.inspect()
        self.assertEqual(r["registered_source_marker_count"],5)

    def test_03_no_full_root_path_in_report(self):
        r=self.inspect()
        self.assertNotIn(str(self.home),json.dumps(r))
        self.assertNotIn(str(self.root),json.dumps(r))

    def test_04_exact_original_uapi_string_is_fingerprinted(self):
        r=self.inspect()
        self.assertEqual(r["registered_root_sha256_prefix"],
                         hashlib.sha256(str(self.root).encode()).hexdigest()[:16])

    def test_05_provides_real_checkout_view_content_sha_prefix(self):
        r=self.inspect()
        expected=hashlib.sha256(self.files["checkout"].read_bytes()).hexdigest()[:16]
        self.assertEqual(r["registered_checkout_view_sha256_prefix"],expected)

    def test_06_provides_template_content_sha_prefix_without_contents(self):
        r=self.inspect()
        expected=hashlib.sha256(self.files["template"].read_bytes()).hexdigest()[:16]
        self.assertEqual(r["registered_template_sha256_prefix"],expected)
        self.assertNotIn("synthetic safe source",str(r))

    def test_07_only_fixed_read_only_uapi_command(self):
        self.inspect()
        self.assertEqual(self.executed[0][0],list(m.UAPI_CMD))

    def test_08_no_shell_injection_or_unbounded_uapi_execution(self):
        self.inspect()
        args=self.executed[0][1]
        self.assertEqual(args["timeout"],12)
        self.assertIs(args["check"],False)
        self.assertNotIn("shell",args)

    def test_09_stdout_is_piped_and_stderr_suppressed(self):
        self.inspect()
        options=self.executed[0][1]
        self.assertEqual(options["stdout"],m.PIPE)
        self.assertEqual(options["stderr"],m.DEVNULL)
        self.assertEqual(options["stdin"],m.DEVNULL)

    def test_10_source_claim_cannot_authorize_release(self):
        self.assertFalse(self.inspect()["production_release_permitted"])

    def test_11_source_claim_does_not_verify_worker(self):
        self.assertFalse(self.inspect()["effective_passenger_worker_verified"])

    def test_12_source_claim_does_not_verify_django_view(self):
        self.assertFalse(self.inspect()["effective_django_view_verified"])

    def test_13_source_claim_does_not_verify_template_loader(self):
        self.assertFalse(self.inspect()["effective_checkout_template_verified"])

    def test_14_source_claim_does_not_verify_buyer_post(self):
        self.assertFalse(self.inspect()["buyer_email_post_verified"])

    def test_15_source_claim_does_not_verify_trx_settlement(self):
        self.assertFalse(self.inspect()["paid_settlement_verified"])

    def test_16_source_claim_does_not_verify_paid_delivery(self):
        self.assertFalse(self.inspect()["paid_delivery_verified"])

    def test_17_collected_revenue_remains_unknown(self):
        self.assertIsNone(self.inspect()["actual_collected_revenue"])

    def test_18_missing_source_module_marks_missing(self):
        self.files["checkout"].unlink()
        r=self.inspect()
        self.assertFalse(r["registered_checkout_view_marker_on_disk"])
        self.assertEqual(r["classification"],"registered_directory_missing_commerce_source_markers")

    def test_19_missing_template_does_not_become_valid_proof(self):
        self.files["template"].unlink()
        r=self.inspect()
        self.assertFalse(r["registered_checkout_template_marker_on_disk"])
        self.assertIsNone(r["registered_template_sha256_prefix"])

    def test_20_missing_wsgifile_does_not_become_runtime_proof(self):
        self.files["wsgi"].unlink()
        self.assertFalse(self.inspect()["registered_wsgi_marker_on_disk"])

    def test_21_symlink_checkout_module_not_followed(self):
        self.files["checkout"].unlink()
        self.files["checkout"].symlink_to(self.files["store"])
        self.assertFalse(self.inspect()["registered_checkout_view_marker_on_disk"])

    def test_22_symlinked_registered_root_is_rejected(self):
        real=self.home/"actual"
        self.root.rename(real)
        self.root.symlink_to(real,target_is_directory=True)
        r=self.inspect()
        self.assertEqual(r["classification"],"root_not_safe_inside_account")

    def test_23_symlinked_parent_component_is_rejected(self):
        real=self.home/"real-parent";real.mkdir()
        inside=real/"app";inside.mkdir()
        link=self.home/"linked-parent";link.symlink_to(real,target_is_directory=True)
        r=self.inspect(self.response([{"domain":"mojplaywin.com","app_root":str(link/"app")}]))
        self.assertEqual(r["classification"],"root_not_safe_inside_account")

    def test_24_other_account_root_not_inspected(self):
        r=self.inspect(self.response([{"domain":"mojplaywin.com","app_root":"/home/other-owner/app"}]))
        self.assertEqual(r["classification"],"root_not_safe_inside_account")

    def test_25_relative_root_not_guessed(self):
        r=self.inspect(self.response([{"domain":"mojplaywin.com","app_root":"registered-mpw"}]))
        self.assertEqual(r["classification"],"root_not_safe_inside_account")

    def test_26_traversal_root_refused(self):
        r=self.inspect(self.response([{"domain":"mojplaywin.com","app_root":str(self.home)+"/../other"}]))
        self.assertEqual(r["classification"],"root_not_safe_inside_account")

    def test_27_double_slash_root_refused(self):
        r=self.inspect(self.response([{"domain":"mojplaywin.com","app_root":str(self.home)+"//registered-mpw"}]))
        self.assertEqual(r["classification"],"root_not_safe_inside_account")

    def test_28_target_domain_casefold_supported(self):
        r=self.inspect(self.response([{"domain":"MOJPLAYWIN.COM","app_root":str(self.root)}]))
        self.assertTrue(r["registered_root_regular_same_account_directory"])

    def test_29_www_alias_supported(self):
        r=self.inspect(self.response([{"domain":"www.mojplaywin.com","app_root":str(self.root)}]))
        self.assertEqual(r["target_registration_count_capped"],1)

    def test_30_no_target_registration_is_not_evidence_of_missing_app(self):
        r=self.inspect(self.response([{"domain":"example.org","app_root":str(self.root)}]))
        self.assertEqual(r["classification"],"uapi_target_absent")

    def test_31_two_distinct_registration_roots_are_ambiguous(self):
        rows=[{"domain":"mojplaywin.com","app_root":str(self.root)},
              {"domain":"www.mojplaywin.com","app_root":str(self.home/"other")}]
        r=self.inspect(self.response(rows))
        self.assertEqual(r["classification"],"uapi_target_ambiguous")

    def test_32_duplicate_exact_registration_deduplicated(self):
        row={"domain":"mojplaywin.com","app_root":str(self.root)}
        self.assertEqual(self.inspect(self.response([row,row]))["target_registration_count_capped"],1)

    def test_33_conflicting_app_root_aliases_fail_closed(self):
        row={"domain":"mojplaywin.com","app_root":str(self.root),
             "application_root":str(self.home/"different")}
        self.assertEqual(self.inspect(self.response([row]))["classification"],
                         "uapi_missing_or_unavailable")

    def test_34_explicit_failed_uapi_not_trusted(self):
        self.assertEqual(self.inspect(self.response(status=0))["classification"],
                         "uapi_missing_or_unavailable")

    def test_35_malformed_json_rejected_without_echo(self):
        self.assertEqual(self.inspect(b'{"secret":"private-path"}')["classification"],
                         "uapi_missing_or_unavailable")

    def test_36_duplicate_json_key_rejected(self):
        payload=b'{"result":{"status":1,"status":0,"data":[]}}'
        self.assertEqual(self.inspect(payload)["classification"],
                         "uapi_missing_or_unavailable")

    def test_37_oversized_uapi_output_rejected(self):
        payload=b'{' + b' '*m.UAPI_OUTPUT_LIMIT + b'}'
        self.assertEqual(self.inspect(payload)["classification"],
                         "uapi_missing_or_unavailable")

    def test_38_nonzero_process_exit_rejected(self):
        r=self.inspect(returncode=1)
        self.assertEqual(r["classification"],"uapi_missing_or_unavailable")

    def test_39_uapi_timeout_is_rejected_not_raised(self):
        error=TimeoutExpired(cmd="uapi",timeout=12,output=b"private")
        r=self.inspect(raised=error)
        self.assertEqual(r["classification"],"uapi_missing_or_unavailable")

    def test_40_failed_binary_lookup_is_rejected_not_raised(self):
        self.assertEqual(self.inspect(raised=FileNotFoundError("private"))["classification"],
                         "uapi_missing_or_unavailable")

    def test_41_code_never_reads_customer_database(self):
        r=self.inspect()
        self.assertFalse(r["customer_data_read"])
        self.assertFalse(r["files_modified"])

    def test_42_byte_budget_and_tree_budget_fixed(self):
        self.assertLessEqual(m.UAPI_OUTPUT_LIMIT,131072)
        self.assertLessEqual(m.UAPI_TREE_NODE_LIMIT,384)

    def test_43_app_root_other_source_alias_permitted_if_unique(self):
        row={"domain":"mojplaywin.com","app_path":str(self.root)}
        self.assertTrue(self.inspect(self.response([row]))["registered_root_regular_same_account_directory"])

    def test_44_oversized_checkout_source_not_accepted(self):
        self.files["checkout"].write_bytes(b"a"*240001)
        self.assertFalse(self.inspect()["registered_checkout_view_marker_on_disk"])

    def test_45_source_probe_invokes_uapi_only_on_explicit_optin(self):
        report=m.inspect(self.root,self.home)
        self.assertEqual(report["registered_root_disk_evidence"]["classification"],
                         "not_requested_in_source_fixture")

    def test_46_explicit_optin_executes_one_readonly_uapi(self):
        report=m.inspect(self.root,self.home,check_registration=True,
                         registration_runner=self.runner())
        self.assertEqual(len(self.executed),1)
        self.assertEqual(report["registered_root_disk_evidence"]["registered_source_marker_count"],5)

    def test_47_invalid_target_root_is_not_an_exception_text(self):
        r=self.inspect(self.response([{"domain":"mojplaywin.com","app_root":"/secret/key"}]))
        self.assertNotIn("/secret",str(r))

    def test_48_uapi_nonfinite_json_number_refused(self):
        self.assertEqual(self.inspect(b'{"result":{"status":1,"data":[NaN]}}')["classification"],
                         "uapi_missing_or_unavailable")

    def test_49_required_email_control_in_same_root_source_classified(self):
        self.files["template"].write_bytes(
            b'<form method="post" action="/commerce/trx-easy/start/72/">'
            b'<input type="email" name="email" required></form>')
        self.assertTrue(self.inspect()["registered_template_required_email_control_on_disk"])

    def test_50_email_label_without_control_not_counted(self):
        self.files["template"].write_bytes(
            b'<!-- <input name="email" type="email" required> -->')
        self.assertFalse(self.inspect()["registered_template_required_email_control_on_disk"])

    def test_51_hidden_email_in_registered_template_not_counted(self):
        self.files["template"].write_bytes(
            b'<form method="post" action="/commerce/trx-easy/start/72/">'
            b'<input type="email" name="email" required hidden></form>')
        self.assertFalse(self.inspect()["registered_template_required_email_control_on_disk"])

    def test_52_registered_checkout_csp_string_only_static_marker(self):
        self.files["checkout"].write_bytes(b'header = "script-src \x27none\x27"')
        r=self.inspect()
        self.assertTrue(r["registered_checkout_view_script_src_marker_on_disk"])
        self.assertFalse(r["effective_django_view_verified"])

    def test_53_registered_checkout_without_script_src_marker_unproven(self):
        self.files["checkout"].write_bytes(b'def checkout(): return None')
        self.assertFalse(self.inspect()["registered_checkout_view_script_src_marker_on_disk"])

    def test_54_registered_template_invalid_utf8_fail_closed(self):
        self.files["template"].write_bytes(b"\xff\xff")
        self.assertFalse(self.inspect()["registered_template_required_email_control_on_disk"])
