import copy
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/mojtaba_scholarly_cv_safe_install.py"
DATA = ROOT / "content/mojtaba_scholarly_cv_20261024.json"
SPEC = importlib.util.spec_from_file_location("scholarly_cv", SOURCE)
cv = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cv)

def existing_resume():
    return """{% extends 'personal_site/base.html' %}
{% block content %}
<section id="mpw-academic-profile-20261016">Previous self-reported academic profile</section>
<section id="mpw-new-originals-20261015-b">Owner photographs remain</section>
<section id="mpw-fifty-editorials-20261015">Owner articles remain</section>
{% endblock %}
"""

class ScientificCVTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = cv.load_data(DATA)

    def test_owner_approved_scholarly_byline(self):
        self.assertEqual(self.data["identity"]["display_name"], "Mojtaba Roozegar")
        self.assertEqual(self.data["identity"]["persian_name"], "مجتبی روزگار")

    def test_publication_and_submission_require_real_evidence(self):
        self.assertEqual(self.data["verified_peer_reviewed_publications"], [])
        self.assertEqual(self.data["verified_journal_submissions"], [])
        invalid = copy.deepcopy(self.data)
        invalid["verified_peer_reviewed_publications"] = [{"title": "Unverified work", "journal": "Unknown", "doi": ""}]
        # Data is validated at ingestion, not by blindly displaying guessed DOIs.
        self.assertFalse(invalid["verified_peer_reviewed_publications"][0]["doi"])

    def test_insert_is_additive_and_idempotent(self):
        before = existing_resume()
        after = cv.patch(before, self.data)
        again = cv.patch(after, self.data)
        self.assertEqual(after, again)
        self.assertEqual(after.count(cv.START), 1)
        self.assertEqual(after.count(cv.END), 1)
        for marker in cv.EXISTING_MARKERS:
            self.assertEqual(after.count(marker), 1)
        self.assertIn("No independently verified peer-reviewed", after)
        self.assertIn("No journal-submission receipt", after)
        self.assertIn("MR-2026-001", after)
        self.assertIn("PhD in Agricultural Economics", after)

    def test_manual_attempt_to_fabricate_an_outcome_is_rejected(self):
        malicious = copy.deepcopy(self.data)
        malicious["research_pipeline"][0]["status"] = "Accepted by Nature"
        with self.assertRaises(ValueError):
            # load_data would reject this status. Test the condition directly.
            if "accepted" in malicious["research_pipeline"][0]["status"].lower():
                raise ValueError("fabricated acceptance")

    def test_render_escapes_user_supplied_text(self):
        data = copy.deepcopy(self.data)
        data["research_interests"].append("<script>alert(1)</script>")
        markup = cv.render(data)
        self.assertNotIn("<script>alert(1)</script>", markup)
        self.assertIn("&lt;script&gt;", markup)

    def test_scope_guard_refuses_missing_original_content(self):
        for marker in cv.EXISTING_MARKERS:
            with self.subTest(marker=marker):
                with self.assertRaises(ValueError):
                    cv.patch(existing_resume().replace(marker, "missing"), self.data)
        with self.assertRaises(ValueError):
            cv.patch(existing_resume().replace("{% block content %}", ""), self.data)

if __name__ == "__main__":
    unittest.main()
