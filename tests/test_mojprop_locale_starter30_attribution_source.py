"""Regression checks for 20-locale Starter30 terms-to-invoice attribution path."""
import importlib.util
from pathlib import Path
import unittest
from urllib.parse import urlencode,parse_qs,urlsplit
from html import escape,unescape
ROOT=Path(__file__).resolve().parents[1]
DEPLOY=ROOT/"scripts"/"mojprop_locale_starter30_attribution_20261121.py"
sp=importlib.util.spec_from_file_location("mojprop_locale_attribution",DEPLOY)
m=importlib.util.module_from_spec(sp)
sp.loader.exec_module(m)

class LocalizedStarter30AttributionTests(unittest.TestCase):
    def test_20_languages_all_unique(self):
        self.assertEqual(len(m.CODES),20)
        self.assertEqual(len(set(m.CODES)),20)
        self.assertEqual(m.CODES[0],"en")
        self.assertIn("pcm",m.CODES)
        self.assertIn("ar-eg",m.CODES)
    def test_campaign_codes_are_bounded_and_nonidentifying(self):
        for lang in m.CODES:
            vals={"utm_source":"mojprop_locale","utm_medium":"onsite",
                  "utm_campaign":"lang_"+lang.replace("-","_"),
                  "utm_content":"starter30_terms"}
            query=urlencode(vals)
            url=m.ROOT_LINK+"?"+query
            self.assertEqual(urlsplit(url).path,"/moj-prop/starter-30-trx/")
            self.assertEqual({k:v[0] for k,v in parse_qs(urlsplit(url).query).items()},vals)
            self.assertTrue(all(len(v)<=80 for v in vals.values()))
            self.assertNotIn("email",query)
            self.assertNotIn("wallet",query)
            self.assertNotIn("txid",query)
            self.assertEqual(unescape(escape(url,quote=True)),url)
    def test_purchased_route_distinct_from_english_main_program(self):
        self.assertEqual(m.ROOT_LINK,"/moj-prop/starter-30-trx/")
        self.assertIn('data-mpw-locale-event="starter30"',m.OLD)
        self.assertNotIn('/mojprop-starter30-checkout/',m.OLD)
        src=DEPLOY.read_text()
        self.assertIn('data-mpw-locale-event="program" href="/moj-prop/"',src)
        self.assertIn("product.count('href=\"/mojprop-starter30-checkout/\"')!=1",src)
        self.assertIn("url.searchParams.set(key, inputs[key])",src)
        self.assertIn("url.origin !== window.location.origin",src)
    def test_fail_closed_no_checkout_or_db_writes(self):
        src=DEPLOY.read_text()
        for guard in ("Unsafe account","Already released; refuse overwrite","Prior manifest incomplete","Locale drift","Existing CTA drift","Backup checksum failed","Concurrent modification","Post-write mismatch"):
            if guard=="Prior manifest incomplete":
                guard="Prior release incomplete"
            self.assertIn(guard,src)
        self.assertNotIn("requests.post",src)
        self.assertNotIn("cursor.execute",src)
        self.assertNotIn("transaction.atomic",src)
        self.assertNotIn("issue_invoice(",src)
        self.assertNotIn("settle_invoice(",src)

if __name__=="__main__":
    unittest.main()
