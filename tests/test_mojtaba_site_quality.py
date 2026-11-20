"""QA parity checks for legacy PHP structural site evidence criteria."""
import unittest
from core.mojtaba_site_quality import assess_html
from core.mojtaba_site_fleet import probe


def page(title="Site", h1=True, desc=True, link=True):
    result = "<html><head><title>" + title + "</title>"
    if desc:
        result += '<meta content="Useful page" name="description">'
    result += "</head><body>"
    if h1:
        result += "<h1>Heading</h1>"
    if link:
        result += '<a href="/more/">More</a>'
    result += "</body></html>" + "X" * 80
    return result.encode("utf-8")


class StructuralQualityTests(unittest.TestCase):
    def test_clean_html_yields_100_structural_points(self):
        r = assess_html(page())
        self.assertEqual(r["status"], "review")
        self.assertEqual(r["score"], 100)
        self.assertEqual(r["issues"], [])
        self.assertFalse(r["source_content_logged"])
        self.assertFalse(r["external_data_verified"])

    def test_missing_elements_degrade_quadratically_not_false_clean(self):
        r = assess_html(page("", False, False, False))
        self.assertEqual(r["score"], 0)
        self.assertEqual(len(r["issues"]), 4)
        self.assertEqual(r["h1_count"], 0)

    def test_overlong_title_is_flagged(self):
        r = assess_html(page("T" * 101))
        self.assertEqual(r["score"], 75)
        self.assertIn("title_over_100_chars", r["issues"])

    def test_short_and_invalid_unicode_fail_closed(self):
        self.assertEqual(assess_html(b"<html></html>")["status"], "blocked")
        self.assertEqual(assess_html(b"\xff" * 80)["status"], "blocked")
        self.assertEqual(assess_html("x")["status"], "blocked")

    def test_site_probe_includes_redacted_quality_not_title(self):
        result = probe(
            "zomorodmelal", "content",
            transport=lambda _: (200, "text/html; charset=UTF-8", page("Private Name"))
        )
        self.assertEqual(result["site_html_quality"]["score"], 100)
        self.assertNotIn("title", result["site_html_quality"])
        self.assertNotIn("Private Name", str(result))

    def test_no_html_quality_on_json(self):
        result = probe(
            "mojplaywin", "public_home",
            transport=lambda _: (200, "application/json", b'{"ok":true}' + b" " * 100),
        )
        self.assertEqual(result["state"], "http_probe_ok")
        self.assertIsNone(result["site_html_quality"])
