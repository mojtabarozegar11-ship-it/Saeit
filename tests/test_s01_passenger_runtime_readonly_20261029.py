"""Synthetic no-network regression tests for S-01 Passenger metadata probe."""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "scripts/s01_passenger_runtime_readonly_20261029.py"
spec = importlib.util.spec_from_file_location("s01_probe", SRC)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ProcessMetadataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def proc(self, pid, cmd, env):
        p = self.root / str(pid)
        p.mkdir()
        (p / "cmdline").write_bytes(cmd)
        (p / "environ").write_bytes(env)

    def test_scoped_process_and_redaction(self):
        self.proc(101, b"Passenger PythonApp\0/home/zomorod2/Saeit-staging\0",
                  b"DJANGO_SETTINGS_MODULE=config.settings\0DATABASE_URL=mysql://user:synthetic-secret@host/db\0")
        self.proc(102, b"other-app\0", b"DATABASE_URL=postgres://synthetic-other-secret\0")
        r = mod.probe(self.root, owner_uid=os.getuid())
        self.assertEqual(r["matching_app_processes"], 1)
        self.assertEqual(r["matching_db_configuration_key_env"], 1)
        self.assertEqual(r["passenger_like_processes"], 1)
        self.assertFalse(r["passenger_db_authority_verified"])
        self.assertNotIn("synthetic-secret", str(r))

    def test_dedicated_root_marker(self):
        self.proc(201, b"python\0", b"PASSENGER_APP_ROOT=/home/zomorod2/Saeit-staging\0")
        self.assertEqual(mod.probe(self.root)["matching_app_processes"], 1)

    def test_unrelated_environment_value_does_not_match(self):
        self.proc(301, b"python\0", b"PATH=/home/zomorod2/Saeit-staging\0")
        self.assertEqual(mod.probe(self.root)["matching_app_processes"], 0)

    def test_oversized_env_fails_closed(self):
        self.proc(401, b"Passenger /home/zomorod2/Saeit-staging\0",
                  b"A" * (mod.MAX_ENVIRON + 1))
        self.assertEqual(mod.probe(self.root)["matching_app_processes"], 0)

    def test_unavailable_proc_fails_closed(self):
        r = mod.probe(self.root / "missing")
        self.assertFalse(r["proc_readable"])
        self.assertFalse(r["passenger_db_authority_verified"])

    def test_no_file_mutation(self):
        self.proc(501, b"Passenger /home/zomorod2/Saeit-staging\0", b"")
        before = sorted(str(p) for p in self.root.rglob("*"))
        r = mod.probe(self.root)
        self.assertEqual(before, sorted(str(p) for p in self.root.rglob("*")))
        self.assertFalse(r["production_source_modified"])
        self.assertFalse(r["database_modified"])


if __name__ == "__main__":
    unittest.main()
