import hashlib
from pathlib import Path
import tempfile
import unittest
from scripts.mojprop_effective_route_readonly_20261119 import inspect, config_signals, safe_read

class RouteEvidenceTests(unittest.TestCase):
    def test_exact_public_response_and_known_root_only(self):
        with tempfile.TemporaryDirectory() as d:
            public, stage = Path(d)/"public", Path(d)/"staging"
            public.mkdir(); stage.mkdir(); (public/"moj-prop").mkdir()
            (public/"moj-prop/index.html").write_bytes(b"public landing")
            (public/".htaccess").write_text("PassengerAppRoot "+str(stage)+"\nRewriteRule ^moj-prop/ something [L]\n")
            (public/"passenger_wsgi.py").write_text("from config.wsgi import application\n")
            r=inspect(public, stage, hashlib.sha256(b"public landing").hexdigest())
            self.assertTrue(r["public_get_matches_landing_file"])
            self.assertEqual(r["public_config"]["app_root_declarations"], ["staging"])
            self.assertTrue(r["public_entry"]["django_entrypoint_mentioned"])
            self.assertFalse(r["live_worker_identity_proven"])
            self.assertFalse(r["production_change_authorized"])
            self.assertFalse(inspect(public, stage, "0"*64)["public_get_matches_landing_file"])
    def test_comments_and_other_roots_are_not_disclosed(self):
        p,s=Path("/known/public"),Path("/known/stage")
        r=config_signals(b"# PassengerAppRoot /known/stage\nPassengerAppRoot /private/other\n", p,s)
        self.assertEqual(r["app_root_declarations"], ["other_or_dynamic"])
        self.assertNotIn("/private/other", str(r))
    def test_symlink_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/"real").write_bytes(b"unrelated")
            (root/"alias").symlink_to(root/"real")
            self.assertIsNone(safe_read(root,"alias"))
