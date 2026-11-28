import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from scripts import mojprop_wsgi_binding_readonly_c125 as probe

class C125Tests(unittest.TestCase):
    def test_size_bands(self):
        self.assertEqual(probe.size_band(0), "0")
        self.assertEqual(probe.size_band(4096), "1-4KB")
        self.assertEqual(probe.size_band(4097), "4-16KB")

    def test_safe_ast_metadata_only(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "passenger_wsgi.py"
            path.write_text(
                "import os, sys\\nAPP='/home/zomorod2/Saeit-mojprop-candidate-20261122'\\n"
                "sys.path.insert(0, APP)\\nos.chdir(APP)\\n"
                "from django.core.wsgi import get_wsgi_application\\n"
                "application = get_wsgi_application()\\n",
                encoding="utf-8",
            )
            with patch.object(probe, "HOME", Path("/home/zomorod2")):
                result = probe.inspect(path)
            self.assertTrue(result["parseable_python"])
            self.assertTrue(result["has_sys_path_insert"])
            self.assertTrue(result["has_os_chdir"])
            self.assertTrue(result["has_get_wsgi_application"])
            self.assertIn("/home/zomorod2/Saeit-mojprop-candidate-20261122",
                          result["safe_home_path_literals"])
            self.assertNotIn("SECRET", str(result))

    def test_report_is_fail_closed(self):
        self.assertIn('"files_modified": False', probe.__dict__["main"].__code__.co_consts.__str__())

if __name__ == "__main__":
    unittest.main()
