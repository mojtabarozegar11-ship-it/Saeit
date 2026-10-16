"""Offline safeguards for the read-only main-domain MojPlayWin audit agent."""
import unittest
from scripts import mojplaywin_site_quality_agent as qa


def fixture(title="MojPlayWin", canonical="https://mojplaywin.com/agents/", images=3, words=220):
    imgtags = ''.join(
        f'<img src="/static/site/heroes/ai{i}.webp" alt="Illustration {i}">'
        for i in range(images)
    )
    return (f'<!doctype html><html><head><title>{title}</title>'
            f'<link rel="canonical" href="{canonical}"></head>'
            f'<body><main><h1>Agent readiness guide</h1><p>'
            + "real useful documentation " * (words // 3 + 3)
            + f'</p>{imgtags}</main></body></html>')


class ReadOnlyQualityAgentTests(unittest.TestCase):
    def test_agent_never_lists_independent_subsites(self):
        self.assertNotIn("/mojtaba.roozegar/", qa.ROUTES)
        self.assertNotIn("/picm/", qa.ROUTES)
        self.assertNotIn("/saman/", qa.ROUTES)
        self.assertNotIn("/admin/", qa.ROUTES)
        self.assertTrue(all(path == "/" or path.startswith("/") for path in qa.ROUTES))
        self.assertEqual(len(qa.ROUTES), len(set(qa.ROUTES)))

    def test_scope_rejects_any_external_host_or_protected_path(self):
        for url in (
            "https://zomorodmelal.ir/",
            "https://mojplaywin.com/mojtaba.roozegar/",
            "https://mojplaywin.com/picm/",
            "https://mojplaywin.com/admin/",
            "http://mojplaywin.com/",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                qa.get_public_html(url)

    def test_good_page_passes(self):
        def fetch(url):
            return 200, fixture(canonical=url)
        result = qa.inspect_page("/agents/", fetch=fetch)
        self.assertTrue(result["ok"], result["issues"])
        self.assertEqual(result["main_images"], 3)

    def test_wrong_canonical_or_thin_page_is_reported(self):
        def fetch(url):
            return 200, fixture(canonical="https://zomorodmelal.ir/agents/",
                                images=1, words=18)
        result = qa.inspect_page("/agents/", fetch=fetch)
        self.assertFalse(result["ok"])
        self.assertIn("wrong_canonical", result["issues"])
        self.assertIn("thin_main_content", result["issues"])
        self.assertIn("insufficient_images", result["issues"])

    def test_agent_has_no_write_action(self):
        def fetch(url):
            return 200, fixture(canonical=url)
        report = qa.run(fetch=fetch)
        self.assertEqual(report["mode"], "read_only")
        self.assertEqual(report["pages_checked"], len(qa.ROUTES))
        self.assertEqual(report["pages_passed"], len(qa.ROUTES))
        self.assertNotIn("POST", " ".join(report["actions_taken"]))


if __name__ == "__main__":
    unittest.main()
