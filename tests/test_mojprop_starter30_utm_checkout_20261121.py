"""Guard client-side Starter30 campaign attribution without touching checkout or PII."""

from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1] / "templates/moj-prop-v4/starter-30-trx"
HTML = ROOT / "index.html"
JS = ROOT / "checkout-attribution.js"
SCRIPT_TAG = '<script defer src="/moj-prop/starter-30-trx/checkout-attribution.js"></script>'


class Starter30UTMLandingContract(unittest.TestCase):
    def test_static_html_keeps_free_terms_cta_and_scoped_script(self):
        html = HTML.read_text("utf-8")
        self.assertEqual(html.count(SCRIPT_TAG), 1)
        self.assertIn('href="/moj-prop-intake/?format=html&amp;service=blueprint&amp;package=starter-30-trx&amp;utm_source=moj_prop&amp;utm_medium=onsite&amp;utm_campaign=starter30_lead&amp;utm_content=free_terms"', html)
        self.assertIn('href="/mojprop-starter30-checkout/"', html)
        self.assertIn('<link rel="canonical" href="https://mojprop.top/moj-prop/starter-30-trx/">', html)
        self.assertIn("30 TRX", html)
        self.assertIn("simulated", html.lower())

    def test_script_is_allowlisted_and_has_no_telemetry_or_payments(self):
        js = JS.read_text("utf-8")
        for term in ["utm_source", "utm_medium", "utm_campaign", "utm_content",
                     "url.pathname !== '/mojprop-starter30-checkout/'",
                     "url.origin !== window.location.origin",
                     "raw.length <= 80", "anchor.setAttribute('href'"]:
            with self.subTest(term=term):
                self.assertIn(term, js)
        for forbidden in ["fetch(", "XMLHttpRequest", "sendBeacon", "localStorage",
                          "sessionStorage", "document.cookie", "window.location =",
                          "issue_invoice", "incoming.get('email')", "incoming.get('wallet')"]:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, js)

    @unittest.skipUnless(shutil.which("node"), "Node needed for isolated browser simulation")
    def test_real_javascript_behaviour(self):
        script = r"""
const vm = require('node:vm'), fs = require('node:fs');
const js = fs.readFileSync(process.argv[1], 'utf8');
function check(query, expected, href='/mojprop-starter30-checkout/') {
 const link={href,getAttribute(){return this.href},setAttribute(k,v){this.href=v}};
 const external={href:'https://example.invalid/mojprop-starter30-checkout/',
  getAttribute(){return this.href},setAttribute(k,v){this.href=v}};
 vm.runInNewContext(js,{URL,URLSearchParams,
  window:{location:{search:query,origin:'https://mojplaywin.com'}},
  document:{querySelectorAll(){return [link,external]}}},{timeout:1000});
 if(link.href !== expected || external.href !== 'https://example.invalid/mojprop-starter30-checkout/')
  throw Error('Unexpected checkout attribution rewrite: '+link.href);
}
check('?utm_source=facebook&utm_medium=organic_social&utm_campaign=mojprop_starter30_202611&utm_content=offer_overview',
 '/mojprop-starter30-checkout/?utm_source=facebook&utm_medium=organic_social&utm_campaign=mojprop_starter30_202611&utm_content=offer_overview');
check('?email=a%40b.com&wallet=private&utm_source=facebook',
 '/mojprop-starter30-checkout/?utm_source=facebook');
check('?utm_source=bad%2Fsource&utm_campaign=valid',
 '/mojprop-starter30-checkout/?utm_campaign=valid');
check('?utm_source=facebook&utm_medium=organic',
 '/mojprop-starter30-checkout/?utm_source=original&utm_medium=organic',
 '/mojprop-starter30-checkout/?utm_source=original');
check('?ref=other', '/mojprop-starter30-checkout/');
check('?utm_source='+('x'.repeat(81)), '/mojprop-starter30-checkout/');
console.log('6 simulated cases passed');
"""
        syntax = subprocess.run([shutil.which("node"), "--check", str(JS)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        result = subprocess.run([shutil.which("node"), "-e", script, str(JS)],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("6 simulated cases passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
