"""No payment reconciliation from an out-of-date staging CLI tree."""
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from scripts import mpw_reconcile_scheduler as scheduler


class ReconcileLiveRuntimeParityTests(TestCase):
    def _check(self, text, expected_error=None):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "runtime"
            root.mkdir()
            wsgi = Path(d) / "passenger_wsgi.py"
            wsgi.write_text(text.replace("@ROOT@", str(root)), encoding="utf-8")
            with patch.object(scheduler, "ROOT", root), patch.object(scheduler, "PUBLIC_WSGI", wsgi):
                if expected_error:
                    with self.assertRaisesRegex(ValueError, expected_error):
                        scheduler.require_effective_wsgi_source()
                else:
                    scheduler.require_effective_wsgi_source()

    def test_exact_literal_live_root_permitted(self):
        self._check("APP = '@ROOT@'\n")

    def test_separate_active_candidate_blocks_staging_writer(self):
        self._check("APP = '/different/production/application'\n", "differs")

    def test_nonliteral_or_ambiguous_app_blocks(self):
        self._check("APP = get_app_root()\n", "literal")
        self._check("APP = '@ROOT@'\nAPP = '@ROOT@'\n", "ambiguous")

    def test_symlinked_wsgi_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "runtime"
            root.mkdir()
            actual = Path(d) / "real_wsgi.py"
            actual.write_text("APP = " + repr(str(root)) + "\n")
            link = Path(d) / "passenger_wsgi.py"
            link.symlink_to(actual)
            with patch.object(scheduler, "ROOT", root), patch.object(scheduler, "PUBLIC_WSGI", link):
                with self.assertRaisesRegex(ValueError, "cannot be established"):
                    scheduler.require_effective_wsgi_source()

    def test_guard_is_executed_before_state_directory_writes(self):
        source = Path(scheduler.__file__).read_text(encoding="utf-8")
        self.assertLess(source.index("    require_effective_wsgi_source()\n    private_dir(STATE)"),
                        source.index("    private_dir(STATE)\n    fd = os.open"))
