"""Guard the current-main Moj Prop and Signal Desk commercial funnel."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MojPropPublicSurfaceAlignmentTests(unittest.TestCase):
    def test_legacy_home_preserves_real_backend_contracts(self):
        page = (ROOT / "templates/moj-prop/index.html").read_text(encoding="utf-8")
        self.assertIn("MOJ_PROP_PUBLIC_HOME_ALIGNED_20261115_R3", page)
        self.assertIn("const endpoint='/moj-prop-intake/';", page)
        self.assertIn("const fieldErrors=body.fields", page)
        for code in ("education-weekly", "education-monthly", "education-quarterly"):
            self.assertIn(code, page)
        self.assertIn("Request ID: '+(id||'not allocated')", page)
        self.assertIn("!/^MOJPROP-[0-9]{8}-[A-F0-9]{8}$/.test(body.request_id)", page)
        self.assertIn('minlength="20"', page)
        self.assertIn('maxlength="5000"', page)
        self.assertNotIn("mailto:", page)
        self.assertNotIn("localStorage.setItem", page)

    def test_signal_desk_cta_selects_the_single_educational_route(self):
        page = (ROOT / "templates/moj-prop/index.html").read_text(encoding="utf-8")
        signal = (ROOT / "templates/moj-prop/signals/index.html").read_text(encoding="utf-8")
        self.assertIn('/moj-prop/?service=signals#request', page)
        self.assertIn('/moj-prop/?service=signals#request', signal)
        self.assertIn("Request educational signals", page)
        self.assertIn("Request educational signals", signal)
        self.assertIn("mojtaba.bot.ai", signal)
        self.assertIn("live feed and automatic subscription are not active", signal)
