"""Static regression guard for the existing Zomorod homepage rotator.
This does not replace browser-based interaction and console testing.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "content/zomorod-vision-v3/assets/zm-reference-v3.js"
HTML = ROOT / "content/zomorod-vision-v3/index.html"

class RotatorReducedMotionSourceGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = SCRIPT.read_text(encoding="utf-8")
        cls.html = HTML.read_text(encoding="utf-8")

    def test_preference_change_pauses_existing_rotators(self):
        self.assertIn("motionPreference.addEventListener('change',event=>{", self.js)
        self.assertIn("if(event.matches){state.paused=true;state.delayUntil=0;update();}", self.js)

    def test_manual_scroll_respects_preference(self):
        self.assertIn("behavior:motionPreference.matches?'auto':'smooth'", self.js)

    def test_toggle_cannot_force_autoplay_under_reduced_motion(self):
        self.assertIn("state.paused=motionPreference.matches?true:!state.paused;", self.js)

    def test_four_existing_rotators_not_replaced(self):
        for rotator_id in ("fields-carousel", "services-strip", "products-strip", "projects-strip"):
            self.assertIn('id="'+rotator_id+'"', self.html)
        self.assertIn("window.__zmRotatorDiagnostics", self.js)

if __name__ == "__main__":
    unittest.main()
