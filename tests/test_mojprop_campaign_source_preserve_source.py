"""MOJ PROP international campaign preservation: safe-source release invariants."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "mojprop_campaign_source_preserve_20261121.py"
spec = importlib.util.spec_from_file_location("mpw_source_preserve", SOURCE)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class InternationalCampaignPreservationTests(unittest.TestCase):
    def test_exactly_twenty_supported_locales(self):
        self.assertEqual(len(release.CODES), 20)
        self.assertEqual(len(set(release.CODES)), 20)
        self.assertIn("pcm", release.CODES)
        self.assertIn("ar-eg", release.CODES)

    def test_source_preserves_external_origin_and_locale(self):
        s = release.SCRIPT
        self.assertIn('query.get("utm_source")', s)
        self.assertIn('query.get("utm_medium")', s)
        self.assertIn('query.get("utm_campaign")', s)
        self.assertIn('"lang_"+code.replace("-","_")+"__"+campaign', s)
        self.assertIn('url.pathname==="/moj-prop/starter-30-trx/"', s)
        self.assertIn('url.pathname==="/moj-prop/"', s)
        self.assertIn('url.searchParams.set("utm_source",source)', s)
        self.assertIn('url.origin!==window.location.origin', s)
        self.assertIn('if(!source||source==="mojprop_locale")return', s)
        self.assertNotIn("document.cookie", s)
        self.assertNotIn("localStorage.", s)
        self.assertNotIn("sessionStorage.", s)

    def test_deployment_is_hash_guarded_and_safely_backed_up(self):
        s = SOURCE.read_text(encoding="utf8")
        for piece in (
            "Chooser drift",
            "Concurrent locale edits",
            "Already performed; refuse overwrite",
            "Expected 21 HTML files",
            "Backup verification failed",
            "Concurrent file mutation",
            "HTML publish mismatch",
            "JS publish mismatch",
        ):
            self.assertIn(piece, s)
        self.assertIn('len(changes)', s)
        self.assertNotIn('transaction.atomic(', s)
        self.assertNotIn('issue_invoice(', s)
        self.assertNotIn('settle_invoice(', s)

    @unittest.skipUnless(shutil.which("node"), "Node is unavailable")
    def test_actual_javascript_rewrites_social_language_path(self):
        harness = r"""
const vm=require('vm');
const js=process.argv[1];
function run(path,search,links){
 const a=links.map(x=>({attrs:{href:x.href,...(x.attrs||{})},
  getAttribute(k){return this.attrs[k]||null},setAttribute(k,v){this.attrs[k]=v}}));
 vm.runInNewContext(js,{window:{location:{origin:'https://mojplaywin.com',
   pathname:path,search}},document:{querySelectorAll(){return a}},URL,URLSearchParams});
 return a.map(x=>x.attrs.href);
}
const q='?utm_source=facebook&utm_medium=organic_social&utm_campaign=global20&utm_content=guide';
const hub=run('/moj-prop/languages/',q,[{href:'/moj-prop/languages/es/'},{href:'https://outside.invalid/'}]);
if(!hub[0].includes('utm_source=facebook')||hub[1]!=='https://outside.invalid/')
 throw Error('language selector failed');
const local=run('/moj-prop/languages/es/',q,[
 {href:'/moj-prop/starter-30-trx/?utm_source=mojprop_locale',attrs:{'data-mpw-locale-event':'starter30'}},
 {href:'/moj-prop/',attrs:{'data-mpw-locale-event':'program'}},
 {href:'/moj-prop/languages/fr/'}]);
if(!local[0].includes('utm_source=facebook')||
 !local[0].includes('utm_campaign=lang_es__global20'))throw Error('terms link failed');
if(!local[1].includes('lang_es__global20'))throw Error('program link failed');
if(!local[2].includes('utm_campaign=global20'))throw Error('language switch failed');
const clean=run('/moj-prop/languages/es/','',[{href:'/moj-prop/starter-30-trx/?utm_source=mojprop_locale',
 attrs:{'data-mpw-locale-event':'starter30'}}]);
if(clean[0]!=='/moj-prop/starter-30-trx/?utm_source=mojprop_locale')
 throw Error('direct, untagged visits changed');
console.log('four cases passed');
"""
        out = subprocess.run(
            ["node", "-e", harness, release.SCRIPT],
            capture_output=True, text=True, timeout=5, check=False
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("four cases passed", out.stdout)


if __name__ == "__main__":
    unittest.main()
