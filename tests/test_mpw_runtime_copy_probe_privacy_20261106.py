"""Read-only Passenger/WSGI evidence must not leak private cPanel paths."""
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts import mpw_runtime_copy_probe_20261106 as probe


class ReadOnlyRuntimeEvidenceTests(unittest.TestCase):
    def test_product_detail_source_map_records_only_hashes_and_candidates(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "Saeit-staging"
            (source / "core").mkdir(parents=True)
            (source / "templates").mkdir()
            view_file = source / "core" / "product_views.py"
            template_file = source / "templates" / "mpw_detail.html"
            view_file.write_text(
                'def detail(request):\n    return render(request, "mpw_detail.html")\n',
                encoding="utf-8",
            )
            template_file.write_text("<p>public template</p>", encoding="utf-8")

            def detail(request):
                return request

            def resolve(path):
                self.assertTrue(path.startswith("/store/product/"))
                return SimpleNamespace(func=detail, url_name="store_product_detail")

            def get_template(name):
                self.assertEqual(name, "mpw_detail.html")
                return SimpleNamespace(origin=SimpleNamespace(name=str(template_file)))

            with (patch.object(probe, "ROOT", source),
                  patch.object(probe.inspect, "getsourcefile", return_value=str(view_file))):
                result = probe.product_detail_source_map(resolve, get_template)
            self.assertEqual(set(result["configured_django_details"]), {"72", "225", "879"})
            for value in result["configured_django_details"].values():
                self.assertTrue(value["route_resolved"])
                self.assertTrue(value["view_source_available"])
                self.assertEqual(value["view_source_relative"], "core/product_views.py")
                self.assertEqual(len(value["view_source_sha256"]), 64)
                self.assertEqual(value["candidate_templates"][0]["relative"],
                                 "templates/mpw_detail.html")
            self.assertFalse(result["effective_public_worker_verified"])
            self.assertFalse(result["template_candidates_are_active"])
            self.assertFalse(result["release_permitted"])
            self.assertNotIn(str(source), repr(result))

    def test_product_detail_probe_rejects_symlinked_source_and_private_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            source = base / "Saeit-staging"
            source.mkdir()
            private = base / "private.py"
            private.write_text("PRIVATE_SECRET=123", encoding="utf-8")
            (source / "linked.py").symlink_to(private)

            def detail(_request):
                pass

            def resolve(_path):
                return SimpleNamespace(func=detail, url_name="detail")

            with (patch.object(probe, "ROOT", source),
                  patch.object(probe.inspect, "getsourcefile",
                               return_value=str(source / "linked.py"))):
                result = probe.product_detail_source_map(resolve, lambda _: None)
            self.assertTrue(all(not info["view_source_available"]
                                for info in result["configured_django_details"].values()))
            self.assertNotIn("PRIVATE_SECRET", repr(result))
            self.assertNotIn(str(base), repr(result))

    def test_product_detail_probe_missing_route_does_not_claim_release(self):
        def absent(_path):
            raise LookupError("private backend path")

        result = probe.product_detail_source_map(absent, lambda _: None)
        self.assertEqual(result["configured_django_details"]["72"],
                         {"route_resolved": False, "error_type": "LookupError"})
        self.assertNotIn("private backend path", repr(result))
        self.assertFalse(result["release_permitted"])

    def test_htaccess_produces_boolean_binding_hints_without_raw_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            site = base / "mojplaywin.com"
            source = base / "Saeit-staging"
            site.mkdir()
            source.mkdir()
            secret_path = "/home/other-account/never-expose"
            (site / ".htaccess").write_text(
                "PassengerAppRoot " + str(site) + "\n"
                "PassengerStartupFile passenger_wsgi.py\n"
                "PassengerBaseURI /\n"
                "PassengerAppRoot " + secret_path + "\n",
                encoding="utf-8",
            )
            with patch.object(probe, "LIVE", site), patch.object(probe, "ROOT", source):
                result = probe.passenger_hints()
            self.assertEqual(len(result["directives"]), 1)
            mapping = result["directives"][0]
            self.assertEqual(mapping["location_label"], "site_root")
            self.assertFalse(mapping["app_root_is_site_root"])  # last directive wins
            self.assertTrue(mapping["startup_is_passenger_wsgi"])
            self.assertTrue(mapping["base_uri_is_root"])
            self.assertNotIn(str(base), repr(result))
            self.assertNotIn(secret_path, repr(result))

    def test_wsgi_path_literals_are_reduced_to_safe_boolean_facts(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            site = base / "mojplaywin.com"
            source = base / "Saeit-staging"
            site.mkdir()
            source.mkdir()
            (site / "passenger_wsgi.py").write_text(
                "APP = " + repr(str(source)) + "\n"
                "UNRELATED = '/home/someone/private_project'\n",
                encoding="utf-8",
            )
            with patch.object(probe, "LIVE", site), patch.object(probe, "ROOT", source):
                result = probe.active_root_inventory()
            wsgi = result["files"]["passenger_wsgi.py"]
            self.assertEqual(wsgi["wsgi_parse_status"], "valid_python")
            self.assertTrue(wsgi["source_root_literal_present"])
            self.assertFalse(wsgi["site_root_literal_present"])
            self.assertNotIn(str(base), repr(result))
            self.assertNotIn("private_project", repr(result))
            self.assertNotIn("path_hints", repr(result))

    def test_wsgi_syntax_error_fails_evidence_without_disclosing_source(self):
        with tempfile.TemporaryDirectory() as folder:
            site = Path(folder) / "mojplaywin.com"
            site.mkdir()
            (site / "passenger_wsgi.py").write_text("PRIVATE=(\n", encoding="utf-8")
            with patch.object(probe, "LIVE", site):
                result = probe.active_root_inventory()
            wsgi = result["files"]["passenger_wsgi.py"]
            self.assertEqual(wsgi["wsgi_parse_status"], "syntax_error")
            self.assertNotIn("PRIVATE", repr(result))


if __name__ == "__main__":
    unittest.main()
