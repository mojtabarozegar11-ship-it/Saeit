"""Synthetic 17x20 homepage rows: preserves 18 original cards and footer without photos duplicated."""
import hashlib,re,unittest
from unittest.mock import patch
from scripts import mojplaywin_main_home_17x20_atomic as m

def original_html():
    cards=[]
    parts=[]
    for row,label in enumerate(("web","digital","ventures")):
        items=[]
        for idx in range(6):
            items.append(f'<li class="mpo-orbit-item"><a class="mpo-orbit-card" href="/research/"><img src="/static/original-image-{row}-{idx}.svg" alt="" loading="lazy"><span class="mpo-orbit-card-copy"><strong>Original {row} {idx}</strong><small>Original approved details</small></span></a></li>')
        cards+=items
        parts.append(f'<section class="mpo-ring" data-orbit="{label}" aria-labelledby="mpo-ring-{label}">'
          f'<div class="mpo-ring-head"><h2 id="mpo-ring-{label}">{label}</h2></div>'
          f'<div class="mpo-track-shell"><ul class="mpo-orbit-track">{"".join(items)}</ul></div></section>')
    html=('<html><head><title>MojPlayWin</title></head><body class="mojplaywin-home">'
          '<div class="mpo-orbits" aria-label="Three interactive project and service orbits">'
          +''.join(parts)+'</div><div class="mpo-orbit-bottom"><button data-orbit-toggle aria-pressed="false">Start gentle rotation</button></div>'
          '<div id="independent-original-content">PRODUCT, ORDERS AND ALL ORIGINAL LINKS PRESERVED</div>'
          '<footer><div class="mpx-bottom-bar"><span data-mpw-copyright-founder="true">Mojtaba Roozegar</span></div></footer>'
          '</body></html>')
    return html.encode(),cards

class MainOnlyRowTests(unittest.TestCase):
    def test_expansion_exact_count_and_original_order(self):
        raw,originals=original_html()
        with patch.object(m,"EXPECTED_SHA",hashlib.sha256(raw).hexdigest()):
            new=m.rewrite(raw)
            with self.assertRaises(RuntimeError):m.rewrite(new)
        text=new.decode()
        sections=m.PATTERN.findall(text)
        self.assertEqual(len(sections),17)
        self.assertTrue(all(s.count('class="mpo-orbit-card"')+s.count('class="mpo-orbit-card mpo-topic-card"')==20 for s in sections))
        self.assertEqual(text.count('class="mpo-orbit-card"'),18)
        self.assertEqual(text.count('class="mpo-orbit-card mpo-topic-card"'),322)
        self.assertEqual(text.count('mpo-topic-visual"'),322)
        self.assertEqual(text.count('id="mpw-17x20-mainonly-style"'),1)
        self.assertEqual(text.count('id="mpw-17x20-mainonly-autostart"'),1)
        for c in originals:
            self.assertEqual(text.count(c),1)
        self.assertIn('data-mpw-copyright-founder="true"',text)
        self.assertIn('PRODUCT, ORDERS AND ALL ORIGINAL LINKS PRESERVED',text)
        self.assertIn("prefers-reduced-motion",text)
        self.assertIn('data-orbit="partners"',text)
        hues=re.findall(r'--mpo-hue:(\d+)',text)
        self.assertEqual(len(hues),322)
        self.assertEqual(len(set(hues)),322)
        self.assertNotIn('<img',text.split('class="mpo-orbit-card mpo-topic-card"')[1].split('</li>')[0])
    def test_only_same_domain_main_routes_are_link_targets(self):
        allow={"/services/","/research/","/company/","/studio/","/ai/",
            "/knowledge/","/store/","/blockchain/","/ventures/ecommerce/",
            "/economy/","/ventures/agriculture/","/ventures/jewelry-gold/",
            "/ventures/carpets/","/ventures/hospitality/"}
        self.assertEqual(len(m.ROWS),17)
        self.assertTrue(all(len(x["topics"])==20 and x["url"] in allow for x in m.ROWS))
        self.assertFalse(any(x["url"].startswith(("/farnaz/","/saman/","/studio.Roham/","/mojtaba.roozegar/","/taniya/","/zahra")) for x in m.ROWS))
    def test_refuses_missing_original_card(self):
        raw,_=original_html()
        changed=raw.replace(b'class="mpo-orbit-card"',b'class="other-card"',1)
        with patch.object(m,"EXPECTED_SHA",hashlib.sha256(changed).hexdigest()):
            with self.assertRaisesRegex(RuntimeError,"original 3 rows"):
                m.rewrite(changed)

if __name__=="__main__":
    unittest.main()
