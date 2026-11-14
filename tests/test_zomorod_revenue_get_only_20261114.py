"""Mock-only tests of the four-path revenue intake readiness probe."""
import importlib.util
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch
from urllib.error import URLError

SPEC = importlib.util.spec_from_file_location(
    "revenue_readiness",
    Path(__file__).resolve().parents[1] / "scripts" / "zomorod_revenue_inquiry_live_readonly_20261114.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

class FakeResponse:
    status=200
    def __init__(self,html,url):
        self.data=html.encode();self.url=url
    def __enter__(self):return self
    def __exit__(self,*a):return False
    def read(self,limit):return self.data[:limit]
    def geturl(self):return self.url

class Tests(TestCase):
    def test_route_whitelist_has_no_homepage(self):
        self.assertEqual(len(MOD.TARGETS),4)
        self.assertNotIn("/", MOD.TARGETS)
        with self.assertRaises(ValueError):
            MOD.inspect("/")

    def test_explicit_same_origin_post_and_csrf_only(self):
        p=MOD.Forms()
        p.feed('<form method="post" action="/ask-master/index.php?service=1"><input name="csrf" value="secret"></form>')
        self.assertTrue(MOD.official_contract(p.forms,MOD.ORIGIN+"/ask-master/index.php?service=1"))
        self.assertNotIn("secret",str(p.forms))

    def test_no_cross_origin_action_even_with_csrf(self):
        p=MOD.Forms()
        p.feed('<form method="POST" action="https://other.test/ask-master/index.php"><input name="csrf" value="private"></form>')
        self.assertFalse(MOD.official_contract(p.forms,MOD.ORIGIN+"/ask-master/index.php"))

    def test_a_get_request_never_submits_or_collects_a_lead(self):
        page=FakeResponse('<form method="post" action="/ask-master/index.php"><input name="csrf" value="PRIVATE"></form>',MOD.ORIGIN+MOD.TARGETS[-1])
        with patch.object(MOD, "urlopen", side_effect=AssertionError("must use explicit opener")):
            def fetch(req,timeout):
                self.assertEqual(req.get_method(),"GET")
                self.assertIsNone(req.data)
                self.assertEqual(req.full_url,MOD.ORIGIN+MOD.TARGETS[-1])
                return page
            result=MOD.inspect(MOD.TARGETS[-1],opener=fetch)
        self.assertEqual(result["http"],200)
        self.assertTrue(result["official_form_contract"])
        self.assertNotIn("PRIVATE",str(result))
        self.assertEqual(result["form_submissions"],0)
        self.assertEqual(result["site_writes"],0)
        self.assertFalse(result["source_deployed_proven"])

    def test_missing_csrf_is_never_approved(self):
        response=FakeResponse('<form method="post" action="/ask-master/index.php"></form>',MOD.ORIGIN+MOD.TARGETS[-1])
        result=MOD.inspect(MOD.TARGETS[-1],opener=lambda *a,**kw:response)
        self.assertFalse(result["official_form_contract"])

    def test_timeout_and_retry_are_reported(self):
        reply=FakeResponse("test",MOD.ORIGIN+MOD.TARGETS[0])
        sequence=iter([URLError("timeout"),reply])
        def opener(*args, **kwargs):
            item=next(sequence)
            if isinstance(item,Exception):
                raise item
            return item
        out=MOD.inspect(MOD.TARGETS[0],opener=opener,sleeper=lambda _:None)
        self.assertEqual(len(out["attempts"]),2)
        self.assertFalse(out["attempts"][0]["ok"])
        self.assertTrue(out["attempts"][1]["ok"])
        self.assertEqual(out["status"],"HTTP_200_READ_ONLY")

    def test_external_redirect_rejected(self):
        response=FakeResponse("<html>ok</html>","https://attacker.test/")
        out=MOD.inspect(MOD.TARGETS[0],opener=lambda *a,**kw:response)
        self.assertEqual(out["status"],"WRONG_ORIGIN")

    def test_redirect_to_homepage_is_not_a_200_verified_lead_page(self):
        response=FakeResponse("<html>ok</html>",MOD.ORIGIN+"/")
        out=MOD.inspect(MOD.TARGETS[0],opener=lambda *a,**kw:response)
        self.assertEqual(out["status"],"REDIRECTED_AWAY")

if __name__=="__main__":main()
