"""Read-only Passenger/WSGI evidence must not leak private cPanel paths."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import mpw_runtime_copy_probe_20261106 as probe


class ReadOnlyRuntimeEvidenceTests(unittest.TestCase):
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
