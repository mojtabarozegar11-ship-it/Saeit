"""No server writes; test source-only live routing fingerprint with dummy trees."""
import tempfile
import unittest
from pathlib import Path

from scripts.mojplaywin_live_routing_fingerprint import audit, literal_routes


class LiveRoutingReadonlyTests(unittest.TestCase):
    def test_shared_wsgi_detected_and_release_is_never_authorized(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            doc = root / "website"
            app = root / "shared"
            (app / "config").mkdir(parents=True)
            doc.mkdir()
            (doc / "passenger_wsgi.py").write_text("sys.path.insert(0, '/home/example/Saeit-staging')")
            (doc / ".htaccess").write_text("PassengerEnabled on\nRewriteRule ^ /index.php")
            (app / "config" / "urls.py").write_text(
                "urlpatterns=[path('picm/', view), path('mojtaba.roozegar/', view), path('store/', view)]"
            )
            result = audit(doc, app)
            self.assertTrue(result["wsgi_references_shared_saeit_staging"])
            self.assertTrue(result["htaccess_passenger_config_present"])
            self.assertTrue(result["htaccess_rewrite_rules_present"])
            self.assertTrue(result["known_independent_routes_mentioned_in_source"]["picm"])
            self.assertFalse(result["release_permitted"])
            self.assertNotIn("/home/example", str(result))

    def test_unknown_or_dynamic_routes_are_not_guessed(self):
        self.assertEqual(literal_routes("urlpatterns=[path('<slug:name>/', x), path('abc/', x)]"), {"abc"})
        self.assertEqual(literal_routes("invalid python ="), set())

    def test_missing_files_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = audit(root / "no-docroot", root / "no-app")
            self.assertIsNone(result["wsgi_references_shared_saeit_staging"])
            self.assertFalse(result["production_isolation_proven"])


if __name__ == "__main__":
    unittest.main()
