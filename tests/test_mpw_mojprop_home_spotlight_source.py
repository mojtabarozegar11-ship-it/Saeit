"""Source-level regression checks for the isolated MOJ PROP homepage spotlight."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts"/"mpw_mojprop_home_spotlight_20261121.py"
spec=importlib.util.spec_from_file_location("mpw_prop_home", SCRIPT)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def original_fixture():
    return """
<!doctype html><html lang="en"><head>
<title>Moj Play Win | Games, AI, Research & Digital Products</title>
<meta name="description" content="Moj Play Win (MojPlayWin) brings together original games, AI tools, scientific research, web development and digital products.">
<link rel="canonical" href="https://mojplaywin.com/">
<meta property="og:title" content="Moj Play Win | Games, AI, Research & Digital Products">
<meta property="og:description" content="Explore original games, AI tools, scientific research and digital products at Moj Play Win (MojPlayWin).">
<meta name="twitter:title" content="Moj Play Win | Games, AI, Research & Digital Products">
<meta name="twitter:description" content="Original games, research, AI and digital products at Moj Play Win.">
</head><body><main id="main-content">
<header><h1 id="mw-home-title">Moj <em>Play</em> Win</h1></header>
<section class="mpo-experience" data-mojplaywin-orbital="v1" aria-labelledby="mw-home-title">
<div class="mpo-experience-header">KEEP_ORIGINAL_HEADER</div>
  <section class="mpx-featured" id="starter30-direct-home" aria-labelledby="starter30-direct-home-title">
    <div><a href="/moj-prop/starter-30-trx/">Open Starter30 details</a></div>
  </section>
  <div class="mpo-orbits" aria-label="Seventeen interactive project and service rows">KEEP_ORIGINAL_ORBITS</div>
</section>
<footer>KEEP_ORIGINAL_FOOTER</footer></main></body></html>
"""

class SpotlightSourceTests(unittest.TestCase):
    def test_seo_and_banner_are_additive_to_surrounding_content(self):
        source=original_fixture()
        patched=mod.patch(source)
        self.assertEqual(patched.count(mod.MARKER),1)
        self.assertEqual(patched.count('href="/moj-prop/"'),1)
        self.assertNotIn('id="starter30-direct-home"',patched)
        self.assertIn('KEEP_ORIGINAL_HEADER',patched)
        self.assertIn('KEEP_ORIGINAL_ORBITS',patched)
        self.assertIn('KEEP_ORIGINAL_FOOTER',patched)
        self.assertIn('id="mw-home-title"',patched)
        self.assertEqual(patched.count('rel="canonical" href="https://mojplaywin.com/"'),1)
        self.assertIn("<title>"+mod.TITLE+"</title>",patched)
        self.assertIn('name="description" content="'+mod.DESCRIPTION+'"',patched)
        self.assertIn("mpw-mojprop-home-schema-20261121",patched)
        self.assertIn("mpw-mojprop-home-spotlight-css-20261121",patched)
        self.assertIn('@media(max-width:430px)',patched)
        self.assertLess(patched.index(mod.MARKER),patched.index('class="mpo-experience"'))
    def test_fail_closed_on_second_patch(self):
        with self.assertRaisesRegex(RuntimeError,"Already patched"):
            mod.patch(mod.patch(original_fixture()))
    def test_fail_closed_if_original_spotlight_unrecognised(self):
        with self.assertRaises((ValueError, RuntimeError)):
            mod.patch(original_fixture().replace('id="starter30-direct-home"','id="other"'))

if __name__=="__main__":
    unittest.main()
