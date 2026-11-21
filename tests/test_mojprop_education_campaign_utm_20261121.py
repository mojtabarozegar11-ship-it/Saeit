"""Guard first-party MOJ PROP educational campaign continuity into Starter30.

No network, database, payment or private data writes. Optional Node.js VM
executes the exact committed public JavaScript in a simulated DOM.
"""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
EDU = ROOT / "templates/moj-prop/education"
GUIDES = ("risk-management", "drawdown-and-position-sizing", "simulated-versus-live")
JS = EDU / "campaign-attribution.js"
TAG = '<script defer src="/moj-prop/education/campaign-attribution.js"></script>'


class EducationalCampaignContinuityTests(unittest.TestCase):
    def test_three_campaign_guides_load_a_single_local_script(self):
        for name in GUIDES:
            with self.subTest(guide=name):
                page = (EDU / name / "index.html").read_text("utf-8")
                self.assertEqual(page.count(TAG), 1)
                self.assertIn('href="/moj-prop/starter-30-trx/"', page)
                self.assertIn('rel="canonical"', page)
                self.assertIn('lang="en"', page)
                self.assertNotIn('name="robots" content="noindex', page)

    def test_script_is_first_party_campaign_only_without_data_collection(self):
        s = JS.read_text("utf-8")
        for token in ('utm_source', 'utm_medium', 'utm_campaign', 'utm_content',
                      'url.origin !== window.location.origin',
                      'url.pathname', 'allowedPath(url.pathname)',
                      "raw.length <= 80" if False else "value.length <= 80",
                      '/moj-prop/starter-30-trx/',
                      "document.querySelectorAll('a[href]')"):
            with self.subTest(token=token):
                self.assertIn(token, s)
        for danger in ('fetch(', 'XMLHttpRequest', 'sendBeacon(', 'localStorage',
                       'sessionStorage', 'document.cookie', 'window.location =',
                       'window.open(', 'navigator.sendBeacon('):
            with self.subTest(danger=danger):
                self.assertNotIn(danger, s)

    @unittest.skipUnless(shutil.which("node"), "Node.js required for DOM-simulated behaviour")
    def test_node_vm_campaign_navigation(self):
        vm = r"""
const fs=require('node:fs'),vm=require('node:vm');
const src=fs.readFileSync(process.argv[1],'utf8');
const hrefs=['/moj-prop/starter-30-trx/','/moj-prop/education/best-day-consistency/',
 '/moj-prop/rules/','/moj-prop/payment/','/mojprop-starter30-checkout/',
 'https://external.example/store/'];
function run(search, overrideProduct=null) {
 const links=hrefs.map((href,i)=>({
  href:i===0&&overrideProduct?overrideProduct:href,
  getAttribute(){return this.href},setAttribute(k,v){this.href=v}
 }));
 vm.runInNewContext(src,{URL,URLSearchParams,
  window:{location:{search,origin:'https://mojplaywin.com'}},
  document:{querySelectorAll(){return links}}},{timeout:1000});
 return links.map(x=>x.href);
}
let out=run('?utm_source=facebook&utm_medium=organic_social&utm_campaign=mojprop_education_202611&utm_content=risk_intro&email=secret%40example.com');
for(let i=0;i<3;i++){if(!out[i].includes('utm_source=facebook'))throw Error('internal attribution missing');}
for(let i=3;i<6;i++){if(out[i]!==hrefs[i])throw Error('forbidden path rewritten');}
if(out.some(x=>x.includes('email=')))throw Error('private query leaked');
out=run('?utm_source=invalid%2Ftag&utm_campaign=good');
if(out[0].includes('utm_source')||!out[0].includes('utm_campaign=good'))throw Error('allowlist invalid');
out=run('?ref=unknown');if(out[0]!==hrefs[0])throw Error('empty attribution failed');
out=run('?utm_source=facebook&utm_content=landing','/moj-prop/starter-30-trx/?utm_source=direct');
if(!out[0].includes('utm_source=direct')||!out[0].includes('utm_content=landing'))throw Error('existing attribution overwritten');
out=run('?utm_source='+('x'.repeat(81)));if(out[0]!==hrefs[0])throw Error('oversized tag carried');
console.log('6 actual JS navigation cases passed');
"""
        lint = subprocess.run([shutil.which("node"), "--check", str(JS)],
                              text=True, capture_output=True, timeout=10)
        self.assertEqual(lint.returncode, 0, lint.stderr)
        result = subprocess.run([shutil.which("node"), "-e", vm, str(JS)],
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("6 actual JS navigation cases passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
