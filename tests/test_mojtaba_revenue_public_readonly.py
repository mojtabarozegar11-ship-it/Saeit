"""No-network unit tests of the public sales visibility read-only probe."""
import importlib.util
from pathlib import Path
import unittest
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
s = importlib.util.spec_from_file_location(
    "public_revenue_probe", ROOT/"scripts/mojtaba_revenue_public_attestation_readonly.py")
mod = importlib.util.module_from_spec(s)
s.loader.exec_module(mod)

class Response:
    def __init__(self,url,html="<html>ok</html>",status=200,content_type="text/html"):
        self.url=url
        self.data=html.encode("utf8")
        self.status=status
        self.headers={"Content-Type":content_type}
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self,n): return self.data[:n]

class LocalOpener:
    def __init__(self,response):
        self.response=response
        self.calls=0
    def open(self,request,timeout):
        self.calls+=1
        assert request.get_method()=="GET"
        assert request.data is None
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

def subject():
    return mod.TARGETS[0]

class Tests(unittest.TestCase):
    def test_only_three_fixed_targets(self):
        self.assertEqual(len(mod.TARGETS),3)
        self.assertEqual(len(set(mod.TARGETS)),3)
        self.assertEqual({x[1] for x in mod.TARGETS},
                         {"https://zomorodmelal.ir/services/",
                          "https://mojplaywin.com/services/",
                          "https://mojtaba.bot.ai/"})

    def test_no_arbitrary_url_is_observed(self):
        with self.assertRaises(ValueError):
            mod.observe("thirdparty","https://example.invalid/","marker",opener=None)

    def test_get_only_and_no_production_effects(self):
        name,url,marker=subject()
        p=LocalOpener(Response(url,html="<html>"+marker+"</html>"))
        r=mod.observe(name,url,marker,opener=p)
        self.assertEqual(p.calls,1)
        self.assertEqual(r["site_writes"],0)
        self.assertEqual(r["form_submissions"],0)
        self.assertEqual(r["payments"],0)
        self.assertFalse(r["source_file_identity_proven"])

    def test_found_marker_is_not_deployed_receipt(self):
        name,url,marker=subject()
        r=mod.observe(name,url,marker,opener=LocalOpener(
            Response(url,"<html>"+marker+"</html>")))
        self.assertEqual(r["state"],"VISIBLE_MARKER_NOT_DEPLOYMENT_PROOF")
        self.assertTrue(r["marker_visible"])
        self.assertFalse(r["live_bot_execution_proven"])
        self.assertFalse(r["collected_revenue_proven"])

    def test_missing_marker_is_not_a_live_release(self):
        name,url,marker=subject()
        r=mod.observe(name,url,marker,opener=LocalOpener(Response(url)))
        self.assertEqual(r["state"],"HTML200_MARKER_NOT_OBSERVED")
        self.assertFalse(r["marker_visible"])

    def test_redirect_to_homepage_is_rejected(self):
        name,url,marker=subject()
        r=mod.observe(name,url,marker,opener=LocalOpener(
            Response("https://zomorodmelal.ir/")))
        self.assertEqual(r["state"],"WRONG_PATH")

    def test_cross_domain_url_is_rejected(self):
        name,url,marker=subject()
        r=mod.observe(name,url,marker,opener=LocalOpener(
            Response("https://external.invalid/services/")))
        self.assertEqual(r["state"],"WRONG_ORIGIN")

    def test_insecure_redirect_is_rejected(self):
        name,url,marker=subject()
        r=mod.observe(name,url,marker,opener=LocalOpener(
            Response("http://zomorodmelal.ir/services/")))
        self.assertEqual(r["state"],"WRONG_ORIGIN")

    def test_non_html_is_not_verified(self):
        name,url,marker=subject()
        r=mod.observe(name,url,marker,opener=LocalOpener(
            Response(url,content_type="text/plain")))
        self.assertEqual(r["state"],"UNVERIFIED_RESPONSE")

    def test_http_404_not_mistaken_for_success(self):
        name,url,marker=subject()
        error=HTTPError(url,404,"missing",{},None)
        r=mod.observe(name,url,marker,opener=LocalOpener(error))
        self.assertEqual(r["state"],"HTTP_NOT_200")
        self.assertEqual(r["http"],404)

    def test_network_failure_is_unknown(self):
        name,url,marker=subject()
        r=mod.observe(name,url,marker,opener=LocalOpener(
            URLError("PRIVATE_TOKEN_1234 timed out")))
        self.assertEqual(r["state"],"UNKNOWN_FETCH_OR_REDIRECT_FAILURE")
        self.assertNotIn("PRIVATE_TOKEN_1234",str(r))

    def test_oversize_document_rejected(self):
        name,url,marker=subject()
        r=mod.observe(name,url,marker,opener=LocalOpener(
            Response(url,html="x"*(mod.MAX_BODY+1))))
        self.assertEqual(r["state"],"BODY_TOO_LARGE")

    def test_mojtaba_bot_cannot_be_accepted_from_http_title_alone(self):
        name,url,marker=mod.TARGETS[-1]
        r=mod.observe(name,url,marker,opener=LocalOpener(
            Response(url,html="<title>mojtaba.bot.ai</title>")))
        self.assertFalse(r["live_bot_execution_proven"])
        self.assertFalse(r["source_file_identity_proven"])

if __name__=="__main__":
    unittest.main()
