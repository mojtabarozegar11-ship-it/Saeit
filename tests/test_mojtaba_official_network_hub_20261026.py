"""Isolated regression checks for the Mojtaba personal network hub."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/mojtaba_official_network_hub_20261026.py"
REGISTRY = Path(__file__).resolve().parents[1] / "content/mojtaba_official_social_registry_20261026.json"
spec = importlib.util.spec_from_file_location("mojtaba_hub", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def example():
    return """{% extends 'personal_site/base.html' %}
{% block content %}
<section id="mpw-primary-personal-profile-20261016">Original profile</section>
<section class="hero"><h1 id="hero-title">Mojtaba Roozegar</h1></section>
<nav class="mpw-complete-toc" id="mpw-complete-standard-20261019-toc">Previous navigation</nav>
<section id="research">Research and journal retained.</section>
{% endblock %}
"""

class NetworkHubTests(unittest.TestCase):
    def test_registry_initially_verified_only(self):
        result = module.registry(REGISTRY)
        self.assertEqual(set(result), {"personal", "zomorod", "mojplaywin"})
        self.assertTrue(all(not links for links in result.values()))

    def test_home_patch_preserves_all_existing_sections(self):
        old = example()
        new = module.patch(old, module.registry(REGISTRY))
        self.assertEqual(new.count(module.START), 1)
        self.assertEqual(new.count(module.END), 1)
        self.assertLess(new.index('id="hero-title"'), new.index(module.START))
        self.assertLess(new.index(module.END), new.index('id="mpw-complete-standard-20261019-toc"'))
        self.assertIn("Research and journal retained.", new)
        self.assertIn("Original profile", new)
        self.assertIn("https://zomorodmelal.ir/", new)
        self.assertIn("https://mojplaywin.com/store/", new)
        self.assertIn("/mojtaba.roozegar/contact/", new)
        self.assertNotIn('href="https://instagram.com/"', new)
        self.assertEqual(old.count("{%"), new.count("{%"))
        self.assertEqual(new, module.patch(new, module.registry(REGISTRY)))

    def test_reject_changed_home_anchor(self):
        with self.assertRaises(ValueError):
            module.patch(example().replace('mpw-complete-standard-20261019-toc', 'missing'), {})

    def test_verified_social_renders_with_safe_external_link(self):
        channels = {"personal": [{"platform": "YouTube", "url": "https://www.youtube.com/@VerifiedOwnedSample", "label": "Mojtaba official"}], "zomorod": [], "mojplaywin": []}
        rendered = module.patch(example(), channels)
        self.assertIn("https://www.youtube.com/@VerifiedOwnedSample", rendered)
        self.assertIn('rel="noopener noreferrer"', rendered)
        with tempfile.TemporaryDirectory() as dirname:
            p = Path(dirname) / "registry.json"
            p.write_text(json.dumps({"schema_version": 1, "channels": channels}), encoding="utf-8")
            self.assertEqual(module.registry(p), channels)

    def test_forbid_wrong_host_duplicate_and_restricted_account(self):
        good = {"schema_version": 1, "channels": {"personal": [], "zomorod": [], "mojplaywin": []}}
        samples = [
            {"platform":"Instagram", "url":"https://evil.example/path", "label":"Official"},
            {"platform":"Instagram", "url":"https://www.instagram.com/dr.mojtaba.rozegar/", "label":"Restricted"},
            {"platform":"Telegram", "url":"http://t.me/owner", "label":"Official"},
        ]
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "reg.json"
            for item in samples:
                good["channels"]["personal"] = [item]
                path.write_text(json.dumps(good), encoding="utf-8")
                with self.assertRaises(ValueError):
                    module.registry(path)

    def test_no_touch_to_shared_root_or_commerce(self):
        self.assertIn("/mojtaba_personal/mojtaba_roozegar_personal_v17", str(module.APP))
        self.assertEqual(module.REL, "templates/personal_site/core/home.html")
        self.assertNotIn("public_html", module.REL)
        self.assertNotIn("factory", module.REL)

if __name__ == "__main__":
    unittest.main()
