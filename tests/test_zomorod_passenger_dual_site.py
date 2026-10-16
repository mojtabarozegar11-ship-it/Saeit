"""Regression tests for the CloudLinux/Passenger bootstrap; no live host involved."""
import os
import runpy
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "passenger_wsgi.py"


class PassengerCloudLinuxBootstrapTests(unittest.TestCase):
    def test_both_site_packages_dirs_loaded_without_replacing_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            lib = Path(temporary) / "virtualenv" / "Saeit" / "3.10"
            native = lib / "lib64" / "python3.10" / "site-packages"
            pure = lib / "lib" / "python3.10" / "site-packages"
            native.mkdir(parents=True)
            pure.mkdir(parents=True)
            observed = []
            fake_wsgi = types.ModuleType("config.wsgi")
            sentinel = object()
            fake_wsgi.application = sentinel
            with patch("os.path.expanduser", return_value=temporary), \
                 patch("site.addsitedir", side_effect=lambda path: observed.append(path)), \
                 patch.dict(sys.modules, {"config.wsgi": fake_wsgi}), \
                 patch.dict(os.environ, {"DJANGO_SETTINGS_MODULE": "config.settings"}), \
                 patch.object(sys, "path", list(sys.path)):
                namespace = runpy.run_path(str(ENTRY))
            self.assertEqual(observed, [str(native), str(pure)])
            self.assertIs(namespace["application"], sentinel)

    def test_missing_native_packages_prevents_incomplete_bootstrap(self):
        with tempfile.TemporaryDirectory() as temporary:
            fake_wsgi = types.ModuleType("config.wsgi")
            fake_wsgi.application = object()
            with patch("os.path.expanduser", return_value=temporary), \
                 patch.dict(sys.modules, {"config.wsgi": fake_wsgi}), \
                 patch.object(sys, "path", list(sys.path)):
                with self.assertRaisesRegex(RuntimeError, "site-packages"):
                    runpy.run_path(str(ENTRY))

    def test_does_not_exec_or_spawn_new_interpreter(self):
        source = ENTRY.read_text(encoding="utf-8")
        self.assertNotIn("os.execl(", source)
        self.assertNotIn("subprocess.Popen(", source)


if __name__ == "__main__":
    unittest.main()
