"""Isolated offline tests for the private VPS SQLite agent repair."""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/vps_private_sqlite_contention_repair_20261023.py"
spec = importlib.util.spec_from_file_location("vps_private_sqlite_repair", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PrivateSQLiteAgentRepairTests(unittest.TestCase):
    def test_tick_patch_is_guarded_idempotent_and_compilable(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "factory_staging_tick.py"
            p.write_text(
                'class Command:\n'
                '    def handle(self):\n'
                '        call_command("seed_factory_agents")\n',
                encoding="utf8",
            )
            replacement = module.planned_patch(p, "tick")
            self.assertIn(module.TICK_MARKER, replacement)
            self.assertIn("FACTORY_AGENT_SEED_HEALTHY_NO_WRITE", replacement)
            self.assertIn('if not (_factory_expected', replacement)
            compile(replacement, str(p), "exec")
            p.write_text(replacement, encoding="utf8")
            self.assertIsNone(module.planned_patch(p, "tick"))

    def test_settings_patch_timeout_and_idempotency(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "config" / "settings.py"
            p.parent.mkdir()
            p.write_text(
                'DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3"}}\n',
                encoding="utf8",
            )
            replacement = module.planned_patch(p, "settings")
            self.assertIn(module.DB_MARKER, replacement)
            self.assertIn('["timeout"] = 45', replacement)
            compile(replacement, str(p), "exec")
            p.write_text(replacement, encoding="utf8")
            self.assertIsNone(module.planned_patch(p, "settings"))

    def test_changed_tick_fingerprint_fails_closed(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "factory_staging_tick.py"
            p.write_text("def handle(self):\n    pass\n",encoding="utf8")
            with self.assertRaisesRegex(RuntimeError, "FINGERPRINT"):
                module.planned_patch(p, "tick")


if __name__ == "__main__":
    unittest.main()
