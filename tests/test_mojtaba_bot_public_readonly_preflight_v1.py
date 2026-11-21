"""One-domain bot public GET check; fake transports only, zero live test calls."""
import importlib.util
from pathlib import Path
import io
import sys
import unittest
import urllib.error
R=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("mojtaba_public_get",R/"ops/revenue/mojtaba_bot_public_readonly_preflight_v1.py")
MOD=importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name]=MOD
SPEC.loader.exec_module(MOD)

class Response:
 def __init__(self,status=200,mime="text/html",body="<html>Bot holding page</html>"):
  self.status=status
  self.headers={"Content-Type":mime}
  self.handle=io.BytesIO(body.encode())
 def __enter__(self):return self
 def __exit__(self,*a):self.handle.close()
 def read(self,count):return self.handle.read(count)
class Opener:
 def __init__(self,res):self.res=res
 def open(self,req,timeout):
  self.request=req
  self.timeout=timeout
  if isinstance(self.res,Exception):raise self.res
  return self.res
class PublicBotReadOnlyTests(unittest.TestCase):
 def test_01_canonical_domain_exact(self):
  self.assertEqual(MOD.URL,"https://mojtaba.bot.ai/")
 def test_02_successful_public_html_does_not_prove_a_live_bot(self):
  r=MOD.check(Opener(Response()))
  self.assertTrue(r["public_html_observed"])
  self.assertFalse(r["bot_backend_runtime_verified"])
 def test_03_does_not_claim_payments_from_html(self):
  r=MOD.check(Opener(Response()))
  self.assertFalse(r["subscription_billing_verified"])
  self.assertFalse(r["bot_sales_runtime_verified"])
 def test_04_request_is_get_only(self):
  o=Opener(Response());MOD.check(o)
  self.assertEqual(o.request.get_method(),"GET")
 def test_05_timeout_is_bounded(self):
  o=Opener(Response());MOD.check(o)
  self.assertEqual(o.timeout,10)
 def test_06_no_credentials_or_body(self):
  o=Opener(Response());MOD.check(o)
  self.assertNotIn("Authorization",o.request.headers)
  self.assertNotIn("Cookie",o.request.headers)
  self.assertIsNone(o.request.data)
 def test_07_404_is_explicitly_unverified(self):
  r=MOD.check(Opener(urllib.error.HTTPError(MOD.URL,404,"missing",{},None)))
  self.assertFalse(r["public_html_observed"])
  self.assertEqual(r["http_status"],404)
 def test_08_redirect_is_not_success(self):
  r=MOD.check(Opener(urllib.error.HTTPError(MOD.URL,302,"redirect",{"Location":"https://other.site/"},None)))
  self.assertFalse(r["public_html_observed"])
 def test_09_no_automatic_redirects(self):
  self.assertIsNone(MOD.NoRedirect().redirect_request(None,None,None,None,None,None))
 def test_10_wrong_mime_rejected(self):
  self.assertFalse(MOD.check(Opener(Response(mime="application/json")))["public_html_observed"])
 def test_11_empty_html_rejected(self):
  self.assertFalse(MOD.check(Opener(Response(body="")))["public_html_observed"])
 def test_12_oversized_html_rejected(self):
  self.assertFalse(MOD.check(Opener(Response(body="x"*(MOD.MAX_BYTES+1))))["public_html_observed"])
 def test_13_network_failure_is_not_domain_status_claim(self):
  r=MOD.check(Opener(urllib.error.URLError("network unavailable")))
  self.assertIsNone(r["http_status"])
  self.assertEqual(r["issue"],"public_transport_unavailable")
 def test_14_one_public_request_no_customer_side_effects(self):
  r=MOD.check(Opener(Response()))
  for key in ("customer_messages_sent","forms_submitted","authenticated_requests","site_writes"):
   self.assertEqual(r[key],0)
 def test_15_http_200_non_html_is_not_bot_app(self):
  r=MOD.check(Opener(Response(status=200,mime="text/plain")))
  self.assertFalse(r["bounded_nonempty_html_observed"])
if __name__=="__main__":unittest.main()
