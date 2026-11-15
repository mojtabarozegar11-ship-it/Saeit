"""Keep every Moj Prop public home on the real reviewable intake path.

This source-level contract prevents the older static page from silently
downgrading a visitor to a local-only mailto draft.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MojPropPublicSurfaceAlignmentTests(unittest.TestCase):
    def test_legacy_home_is_aligned_with_v4_backend_receipt_surface(self):
        legacy = (ROOT / "templates/moj-prop/index.html").read_text(encoding="utf-8")
        v4 = (ROOT / "templates/moj-prop-v4/index.html").read_text(encoding="utf-8")
        self.assertIn("MOJ_PROP_PUBLIC_HOME_ALIGNED_20261115", legacy)
        self.assertIn("const endpoint='/moj-prop-intake/';", legacy)
        self.assertIn('id="receipt-token"', legacy)
        self.assertIn('minlength="20"', legacy)
        self.assertIn('maxlength="5000"', legacy)
        self.assertNotIn("mailto:", legacy)
        self.assertNotIn("localStorage.setItem", legacy)
        self.assertIn("const endpoint='/moj-prop-intake/';", v4)

    def test_signal_desk_sends_the_selected_route_to_moj_prop(self):
        signal = (ROOT / "templates/moj-prop/signals/index.html").read_text(encoding="utf-8")
        self.assertIn('/moj-prop/?service=signals#request', signal)
        self.assertIn("Request educational signals", signal)
        self.assertIn("mojtaba.bot.ai", signal)
        self.assertIn("live feed and automatic subscription are not active", signal)
