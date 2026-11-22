"""Mock-only tests for no-credential cPanel HTTPS auth surface probes."""
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from scripts import mpw_cpanel_https_surface_readonly as p

class Stub:
    def __init__(self,code):self.code=code;self.request=None
    def open(self,req,timeout):
        self.request=req
        return self
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def getcode(self):return self.code

class AuthGateTests(unittest.TestCase):
    def test_01_tls_url(self):
        self.assertTrue(p.URL.startswith("https://zohal.pws-dns.net:2083/"))
    def test_02_exact_read_api(self):
        self.assertTrue(p.URL.endswith("/PassengerApps/list_applications"))
    def test_03_no_query(self):
        self.assertNotIn("?",p.URL)
    def test_04_bounded_timeout(self):
        self.assertLessEqual(p.TIMEOUT,8)
    def test_05_http_unauthorized_expected(self):
        with patch.object(Stub,"open",side_effect=HTTPError(p.URL,401,"unauth",{},None)):
            self.assertEqual(p.run(Stub(0))["status"],"auth_challenge_expected")
    def test_06_http_forbidden_expected(self):
        with patch.object(Stub,"open",side_effect=HTTPError(p.URL,403,"forbidden",{},None)):
            self.assertEqual(p.run(Stub(0))["status"],"auth_challenge_expected")
    def test_07_success_without_auth_flagged(self):
        self.assertEqual(p.run(Stub(200))["status"],"http200_unauthenticated_unknown_content_type")
    def test_08_no_token_in_request(self):
        opener=Stub(401)
        p.run(opener)
        self.assertIsNone(opener.request.get_header("Authorization"))
        self.assertIsNone(opener.request.get_header("Cookie"))
    def test_09_request_is_get(self):
        opener=Stub(403)
        p.run(opener)
        self.assertEqual(opener.request.get_method(),"GET")
    def test_10_never_claim_login(self):
        self.assertFalse(p.run(Stub(200))["user_authenticated"])
    def test_11_network_failure_class_only(self):
        with patch.object(Stub,"open",side_effect=URLError("no route")):
            r=p.run(Stub(0))
        self.assertEqual(r["status"],"tls_or_network_error")
        self.assertNotIn("no route",str(r))
    def test_12_no_data_or_writes_reported(self):
        r=p.run(Stub(401))
        self.assertFalse(r["remote_data_read"])
        self.assertEqual(r["operations_modified"],0)
    def test_13_html_login_not_auth(self):
        fake=Stub(200)
        fake.headers={"Content-Type":"text/html; charset=utf-8"}
        r=p.run(fake)
        self.assertEqual(r["status"],"html_response_unauthenticated_login_or_error")
        self.assertFalse(r["user_authenticated"])
    def test_14_json_without_auth_is_not_authenticated(self):
        fake=Stub(200)
        fake.headers={"Content-Type":"application/json; charset=utf-8"}
        r=p.run(fake)
        self.assertEqual(r["status"],"json_response_unauthenticated_review_required")
        self.assertFalse(r["user_authenticated"])

if __name__=="__main__":
    unittest.main()
