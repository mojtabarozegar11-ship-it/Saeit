"""Synthetic-only test of PUBLIC GET observer; no network or form POST."""
import unittest
from unittest.mock import patch
from scripts.mojprop_public_funnel_audit import (
    TARGETS, HOSTS, MAX_BYTES, FormCounter, audit, dns, safe_result,
    verify_target, public_get,
)


class PublicPlan1ObserverTests(unittest.TestCase):
    def test_expected_three_exact_targets(self):
        self.assertEqual(len(TARGETS), 3)

    def test_exact_primary_plan_one_path(self):
        self.assertEqual(TARGETS["plan1"], "https://mojplaywin.com/moj-prop/")

    def test_exact_primary_intake_path(self):
        self.assertEqual(TARGETS["intake"], "https://mojplaywin.com/moj-prop-intake/")

    def test_www_fallback_is_only_same_site(self):
        self.assertEqual(TARGETS["www_plan1"], "https://www.mojplaywin.com/moj-prop/")

    def test_allowlisted_paths_verify(self):
        for u in TARGETS.values():
            with self.subTest(target=u):
                self.assertIsNone(verify_target(u))

    def test_http_scheme_rejected(self):
        with self.assertRaises(ValueError):
            verify_target("http://mojplaywin.com/moj-prop/")

    def test_external_hostname_rejected(self):
        with self.assertRaises(ValueError):
            verify_target("https://example.org/moj-prop/")

    def test_lookalike_host_rejected(self):
        with self.assertRaises(ValueError):
            verify_target("https://mojplaywin.com.evil.org/moj-prop/")

    def test_credentials_in_url_rejected(self):
        with self.assertRaises(ValueError):
            verify_target("https://user:secret@mojplaywin.com/moj-prop/")

    def test_nonstandard_port_rejected(self):
        with self.assertRaises(ValueError):
            verify_target("https://mojplaywin.com:8443/moj-prop/")

    def test_query_string_rejected_no_tracking(self):
        with self.assertRaises(ValueError):
            verify_target("https://mojplaywin.com/moj-prop/?buyer=private")

    def test_path_leak_rejected(self):
        with self.assertRaises(ValueError):
            verify_target("https://mojplaywin.com/admin/")

    def test_fragment_rejected(self):
        with self.assertRaises(ValueError):
            verify_target("https://mojplaywin.com/moj-prop/#private")

    def test_content_hints_not_a_sale(self):
        html=b"<html>MOJ-PROP-01 30 TRX simulated 28 50 6 consent conditional 100</html>"
        a=safe_result(200,"text/html",html,TARGETS["plan1"])
        self.assertTrue(a["sku_moj_prop_01"])
        self.assertTrue(a["simulated_visible"])
        self.assertTrue(a["conditional_funding_visible"])

    def test_educational_product_collision_recorded(self):
        a=safe_result(200,"text/html",
            b"<p>MOJPROP-STARTER30 MOJ-PROP-01</p>",TARGETS["plan1"])
        self.assertTrue(a["starter30_seen"])

    def test_missing_simulation_detected(self):
        a=safe_result(200,"text/html",
            b"<p>MOJ-PROP-01 funded guaranteed</p>",TARGETS["plan1"])
        self.assertFalse(a["simulated_visible"])

    def test_failed_404_does_not_claim_page_content(self):
        a=safe_result(404,"text/html",b"MOJ-PROP-01",TARGETS["plan1"])
        self.assertNotIn("sku_moj_prop_01",a)

    def test_mime_nonhtml_not_parsed(self):
        a=safe_result(200,"application/json",b'{"sku":"MOJ-PROP-01"}',
                      TARGETS["plan1"])
        self.assertNotIn("sku_moj_prop_01",a)

    def test_unknown_external_redirect_refused(self):
        with self.assertRaises(ValueError):
            safe_result(200,"text/html",b"x","https://external.example/")

    def test_form_counter_does_not_submit(self):
        s=FormCounter()
        s.feed('<form method="post"><input name="email"><button>Next</button></form>')
        self.assertEqual((s.forms,s.post_forms,s.buttons),(1,1,1))

    def test_form_counter_default_method_is_not_post(self):
        s=FormCounter()
        s.feed("<form><input></form>")
        self.assertEqual(s.post_forms,0)

    def test_probe_has_truncation_flag(self):
        a=safe_result(200,"text/html",b"x"*(MAX_BYTES+1),TARGETS["plan1"])
        self.assertTrue(a["response_truncated"])

    def test_dns_rejects_unknown_host(self):
        with self.assertRaises(ValueError):
            dns("attacker.example")

    def test_dns_failure_not_treated_as_unregistered(self):
        with patch("scripts.mojprop_public_funnel_audit.socket.getaddrinfo",
                   side_effect=OSError("temporary resolver failure")):
            a=dns("mojplaywin.com")
        self.assertFalse(a["resolves"])
        self.assertEqual(a["error_type"],"OSError")

    def test_no_network_called_for_bad_external_url(self):
        with patch("scripts.mojprop_public_funnel_audit.urlopen") as op:
            with self.assertRaises(ValueError):
                public_get("https://not-our-domain.invalid/")
            op.assert_not_called()

    def test_audit_never_claims_customer_submission(self):
        with patch("scripts.mojprop_public_funnel_audit.dns",
                   return_value={"resolves":False,"address_count":0}),\
             patch("scripts.mojprop_public_funnel_audit.public_get",
                   return_value={"reachable":False,"error_type":"URLError"}):
            a=audit()
        self.assertFalse(a["customer_submission_proven"])
        self.assertFalse(a["real_sale_or_revenue_proven"])

    def test_dns_block_means_funnel_not_confirmed(self):
        with patch("scripts.mojprop_public_funnel_audit.dns",
                   return_value={"resolves":False,"address_count":0}),\
             patch("scripts.mojprop_public_funnel_audit.public_get",
                   return_value={"reachable":False}):
            a=audit()
        self.assertEqual(a["verdict"],"PUBLIC_SITE_NOT_CONFIRMED")

    def test_page_content_with_correct_sku_and_simulated_claim_can_be_visible(self):
        good={"reachable":True,"http_status":200,
              "sku_moj_prop_01":True,"simulated_visible":True}
        with patch("scripts.mojprop_public_funnel_audit.dns",
                   return_value={"resolves":True,"address_count":1}),\
             patch("scripts.mojprop_public_funnel_audit.public_get",
                   side_effect=[good,{"reachable":True,"http_status":405},good]):
            a=audit()
        self.assertTrue(a["canonical_plan1_disclosure_visible"])
        self.assertTrue(a["intake_route_present"])
        self.assertFalse(a["real_sale_or_revenue_proven"])

    def test_never_includes_full_public_html_in_result(self):
        a=safe_result(200,"text/html",b"<p>MOJ-PROP-01</p>",TARGETS["plan1"])
        self.assertNotIn("raw_html",a)
        self.assertNotIn("body",a)


if __name__ == "__main__":
    unittest.main()
