"""Guard current-main Moj Prop contracts and the single signal request route."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MojPropPublicSurfaceAlignmentTests(unittest.TestCase):
    def test_legacy_home_preserves_real_backend_contracts(self):
        page = (ROOT / "templates/moj-prop/index.html").read_text(encoding="utf-8")
        self.assertIn("MOJ_PROP_PUBLIC_HOME_ALIGNED_20261115_R2", page)
        self.assertIn("const endpoint='/moj-prop-intake/';", page)
        self.assertIn("const fieldErrors=body.fields", page)
        self.assertIn("education-weekly", page)
        self.assertIn("education-monthly", page)
        self.assertIn("education-quarterly", page)
        self.assertIn("Request ID: '+(id||'not allocated')", page)
        self.assertIn("!/^MOJPROP-[0-9]{8}-[A-F0-9]{8}$/.test(body.request_id)", page)
        self.assertIn('minlength="20"', page)
        self.assertIn('maxlength="5000"', page)
        self.assertNotIn("mailto:", page)
        self.assertNotIn("localStorage.setItem", page)

    def test_home_exposes_explicit_educational_signal_route(self):
        page = (ROOT / "templates/moj-prop/index.html").read_text(encoding="utf-8")
        signal = (ROOT / "templates/moj-prop/signals/index.html").read_text(encoding="utf-8")
        self.assertIn('/moj-prop/?service=signals#request', page)
        self.assertIn('/moj-prop/?service=signals#request', signal)
        self.assertIn("Request educational signals", page)
        self.assertIn("Request educational signals", signal)
        self.assertIn("mojtaba.bot.ai", signal)
        self.assertIn("live feed and automatic subscription are not active", signal)
