"""Contract tests for exact MojPlayWin checkout security response headers.

No Django settings, website, database, order, email or TRX wallet required.
"""
import unittest
from core.mpw_checkout_security_middleware import (
    MojPlayWinCheckoutSecurityMiddleware, _exact_route,
    _owned_html_checkout, STRICT_CSP, NO_STORE,
)


class Request:
    def __init__(self,path="/store/product/72/checkout/",host="mojplaywin.com",
                 method="GET", error=None):
        self.path=path; self.host=host; self.method=method; self.error=error
    def get_host(self):
        if self.error: raise self.error
        return self.host


class Response(dict):
    def __init__(self,status=200,kind="text/html; charset=utf-8",**values):
        super().__init__(values)
        self.status_code=status
        if kind is not None: self["Content-Type"]=kind


class HeaderMiddlewareTests(unittest.TestCase):
    def check(self,request=None,response=None):
        request=request if request is not None else Request()
        response=response if response is not None else Response()
        return MojPlayWinCheckoutSecurityMiddleware(lambda _: response)(request)

    def test_01_exact_primary_checkout_headers(self):
        r=self.check()
        self.assertEqual(r["Content-Security-Policy"],STRICT_CSP)

    def test_02_script_src_is_exact_none(self):
        r=self.check()
        self.assertEqual(r["Content-Security-Policy"].count("script-src 'none'"),1)

    def test_03_form_action_is_same_origin(self):
        self.assertIn("form-action 'self'",self.check()["Content-Security-Policy"])

    def test_04_frame_ancestors_denies_embedding(self):
        self.assertIn("frame-ancestors 'none'",self.check()["Content-Security-Policy"])

    def test_05_object_embedding_denied(self):
        self.assertIn("object-src 'none'",self.check()["Content-Security-Policy"])

    def test_06_base_uri_same_origin(self):
        self.assertIn("base-uri 'self'",self.check()["Content-Security-Policy"])

    def test_07_no_store_applied(self):
        self.assertEqual(self.check()["Cache-Control"],NO_STORE)

    def test_08_legacy_public_cache_control_overwritten(self):
        self.assertEqual(self.check(response=Response(**{"Cache-Control":"public, max-age=3600"}))["Cache-Control"],NO_STORE)

    def test_09_referrer_information_not_leaked(self):
        self.assertEqual(self.check()["Referrer-Policy"],"no-referrer")

    def test_10_html_mime_not_sniffed(self):
        self.assertEqual(self.check()["X-Content-Type-Options"],"nosniff")

    def test_11_clickjacking_denied(self):
        self.assertEqual(self.check()["X-Frame-Options"],"DENY")

    def test_12_pragma_no_cache(self):
        self.assertEqual(self.check()["Pragma"],"no-cache")

    def test_13_vary_host_added(self):
        self.assertEqual(self.check()["Vary"],"Host")

    def test_14_existing_vary_preserved(self):
        r=self.check(response=Response(**{"Vary":"Accept-Encoding, Cookie"}))
        self.assertEqual(r["Vary"],"Accept-Encoding, Cookie, Host")

    def test_15_existing_host_dimension_not_duplicated(self):
        r=self.check(response=Response(**{"Vary":"Accept-Encoding, host"}))
        self.assertEqual(r["Vary"],"Accept-Encoding, host")

    def test_16_vary_wildcard_retained(self):
        self.assertEqual(self.check(response=Response(**{"Vary":"*"}))["Vary"],"*")

    def test_17_existing_unsafe_csp_replaced(self):
        r=self.check(response=Response(**{"Content-Security-Policy":"default-src *; script-src 'unsafe-inline'"}))
        self.assertEqual(r["Content-Security-Policy"],STRICT_CSP)
        self.assertNotIn("unsafe-inline'; script-src",r["Content-Security-Policy"])

    def test_18_www_host_supported(self):
        self.assertEqual(self.check(Request(host="www.mojplaywin.com"))["Cache-Control"],NO_STORE)

    def test_19_case_insensitive_host_supported(self):
        self.assertEqual(self.check(Request(host="MOJPLAYWIN.COM"))["Cache-Control"],NO_STORE)

    def test_20_host_with_numeric_port_supported(self):
        self.assertEqual(self.check(Request(host="mojplaywin.com:443"))["Cache-Control"],NO_STORE)

    def test_21_company_domain_not_changed(self):
        response=Response()
        self.assertIs(self.check(Request(host="zomorodmelal.ir"),response),response)
        self.assertNotIn("Content-Security-Policy",response)

    def test_22_malicious_subdomain_not_changed(self):
        r=self.check(Request(host="mojplaywin.com.evil.example"))
        self.assertNotIn("Content-Security-Policy",r)

    def test_23_missing_host_rejected(self):
        self.assertNotIn("Content-Security-Policy",self.check(Request(host=None)))

    def test_24_disallowed_host_does_not_break_response(self):
        r=self.check(Request(error=ValueError("private")))
        self.assertNotIn("Content-Security-Policy",r)

    def test_25_checkout_sku225_supported(self):
        self.assertEqual(self.check(Request(path="/store/product/225/checkout/"))["Cache-Control"],NO_STORE)

    def test_26_checkout_sku879_supported(self):
        self.assertEqual(self.check(Request(path="/store/product/879/checkout/"))["Cache-Control"],NO_STORE)

    def test_27_book_checkout_alias_supported(self):
        self.assertEqual(self.check(Request(path="/commerce/book/72/"))["Cache-Control"],NO_STORE)

    def test_28_book_alias_sku225_supported(self):
        self.assertEqual(self.check(Request(path="/commerce/book/225/"))["Cache-Control"],NO_STORE)

    def test_29_book_alias_sku879_supported(self):
        self.assertEqual(self.check(Request(path="/commerce/book/879/"))["Cache-Control"],NO_STORE)

    def test_30_product_detail_does_not_get_checkout_policy(self):
        self.assertNotIn("Content-Security-Policy",self.check(Request(path="/store/product/72/")))

    def test_31_store_catalog_not_treated_as_checkout(self):
        self.assertNotIn("Content-Security-Policy",self.check(Request(path="/store/")))

    def test_32_customer_recovery_not_treated_as_checkout(self):
        self.assertNotIn("Content-Security-Policy",self.check(Request(path="/commerce/trx-easy/recovery/")))

    def test_33_invoice_start_post_not_modified(self):
        self.assertNotIn("Content-Security-Policy",self.check(Request(path="/commerce/trx-easy/start/72/",method="POST")))

    def test_34_html_post_checkout_does_not_bypass_payment_gate(self):
        self.assertNotIn("Content-Security-Policy",self.check(Request(method="POST")))

    def test_35_head_checkout_still_noncacheable(self):
        self.assertEqual(self.check(Request(method="HEAD"))["Cache-Control"],NO_STORE)

    def test_36_redirect_untouched(self):
        r=self.check(response=Response(status=302))
        self.assertNotIn("Content-Security-Policy",r)

    def test_37_error_status_untouched(self):
        r=self.check(response=Response(status=500))
        self.assertNotIn("Content-Security-Policy",r)

    def test_38_json_response_untouched(self):
        r=self.check(response=Response(kind="application/json"))
        self.assertNotIn("Content-Security-Policy",r)

    def test_39_css_response_untouched(self):
        r=self.check(response=Response(kind="text/css"))
        self.assertNotIn("Content-Security-Policy",r)

    def test_40_missing_content_type_not_modified(self):
        r=self.check(response=Response(kind=None))
        self.assertNotIn("Content-Security-Policy",r)

    def test_41_non_ascii_path_not_modified(self):
        r=self.check(Request(path="/store/product/72/checkout/é"))
        self.assertNotIn("Content-Security-Policy",r)

    def test_42_path_prefix_spoof_not_modified(self):
        r=self.check(Request(path="/store/product/72/checkout/evil"))
        self.assertNotIn("Content-Security-Policy",r)

    def test_43_zero_product_id_not_accepted(self):
        self.assertFalse(_exact_route("/store/product/0/checkout/"))

    def test_44_missing_trailing_slash_not_accepted(self):
        self.assertFalse(_exact_route("/store/product/72/checkout"))

    def test_45_extra_zero_prefix_not_accepted(self):
        self.assertFalse(_exact_route("/commerce/book/072/"))

    def test_46_overlong_product_id_not_accepted(self):
        self.assertFalse(_exact_route("/commerce/book/1234567890/"))

    def test_47_query_string_in_path_not_accepted(self):
        self.assertFalse(_exact_route("/commerce/book/72/?mode=x"))

    def test_48_nonstring_path_not_accepted(self):
        self.assertFalse(_exact_route(None))

    def test_49_does_not_change_response_body(self):
        class Full(Response):pass
        response=Full()
        response.content=b"buyer email form content unchanged"
        self.check(response=response)
        self.assertEqual(response.content,b"buyer email form content unchanged")

    def test_50_preserves_existing_set_cookie_header(self):
        r=self.check(response=Response(**{"Set-Cookie":"sessionid=private; Secure; HttpOnly"}))
        self.assertEqual(r["Set-Cookie"],"sessionid=private; Secure; HttpOnly")

    def test_51_content_type_preserved(self):
        self.assertEqual(self.check()["Content-Type"],"text/html; charset=utf-8")

    def test_52_get_response_called_once(self):
        calls=[]
        def callback(r):
            calls.append(r);return Response()
        req=Request()
        MojPlayWinCheckoutSecurityMiddleware(callback)(req)
        self.assertEqual(calls,[req])

    def test_53_existing_no_script_policy_is_not_downgraded(self):
        r=self.check(response=Response(**{"Content-Security-Policy":"script-src 'none'"}))
        self.assertEqual(r["Content-Security-Policy"],STRICT_CSP)

    def test_54_no_additional_network_or_customer_side_effects(self):
        response=Response()
        result=self.check(response=response)
        self.assertIs(result,response)
        self.assertNotIn("Location",result)
        self.assertNotIn("Invoice-ID",result)

    def test_55_exact_route_is_case_sensitive(self):
        self.assertFalse(_exact_route("/Store/Product/72/Checkout/"))
