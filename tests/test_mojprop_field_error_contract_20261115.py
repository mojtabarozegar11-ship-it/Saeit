"""Signal-funnel intake UX contract.

The page must explain backend validation failures without unsafe HTML rendering
and must mirror the backend minimum notes length before a request is sent.
"""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "templates" / "moj-prop" / "index.html"


class MojPropFieldErrorContractTests(unittest.TestCase):
    def test_notes_constraint_and_field_errors_are_visible(self):
        text = PAGE.read_text(encoding="utf-8")
        self.assertIn('<textarea id="notes" required minlength="20" maxlength="5000"', text)
        self.assertIn("const fieldErrors=body.fields", text)
        self.assertIn("Object.entries(body.fields)", text)
        self.assertIn("field+': '+detail", text)
        self.assertIn("fieldErrors].filter(Boolean).join(' ')", text)
        self.assertNotIn("result.innerHTML", text)


if __name__ == "__main__":
    unittest.main()
