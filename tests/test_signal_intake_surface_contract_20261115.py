"""Contract tests for the clean Signal Desk intake surface."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "templates" / "moj-prop" / "index.html"
SIGNALS = ROOT / "templates" / "moj-prop" / "signals" / "index.html"


class SignalIntakeSurfaceTests(unittest.TestCase):
    def test_legacy_form_rejects_short_notes_in_browser(self):
        text = LEGACY.read_text(encoding="utf-8")
        self.assertIn('id="notes" required minlength="20" maxlength="5000"', text)

    def test_signal_desk_links_select_the_canonical_service(self):
        text = SIGNALS.read_text(encoding="utf-8")
        self.assertGreaterEqual(text.count('/moj-prop/?service=signals#request'), 2)
        self.assertNotIn('href="/moj-prop/#request"', text)


if __name__ == "__main__":
    unittest.main()
