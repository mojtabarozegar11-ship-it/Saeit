"""Fail-closed dependent-consumer scan, without access to any real host."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

FILE = Path(__file__).resolve().parents[1] / "scripts" / "mojtaba_site_consumer_cutover_readonly.py"
spec = importlib.util.spec_from_file_location("site_consumer_scan", FILE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def make_consumer_tree(root, *, dependencies=True):
    for records in module.CONSUMERS.values():
        for path, markers in records.values():
            file = Path(root) / path
            file.parent.mkdir(parents=True, exist_ok=True)
            content = "# " + " ".join(markers) if dependencies else "# replacement adapter implemented"
            file.write_text(content, encoding="utf-8")


class SourceConsumersTests(unittest.TestCase):
    def test_existing_php_console_and_mpw_dashboard_block_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_consumer_tree(tmp)
            x = module.inspect(Path(tmp))
            self.assertFalse(x["source_only_retirement_ready"])
            self.assertEqual(x["files_removed"], 0)
            self.assertFalse(x["live_host_cleanup_authorized"])
            self.assertEqual(len(x["sites"]["zomorodmelal"]["unresolved_consumer_ids"]), 2)
            self.assertEqual(len(x["sites"]["mojplaywin"]["unresolved_consumer_ids"]), 3)

    def test_missing_consumer_is_unknown_not_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            x = module.inspect(Path(tmp))
            self.assertFalse(x["source_only_retirement_ready"])
            self.assertIsNone(
                x["sites"]["mojplaywin"]["consumers"]["staff_dashboard"]["dependency_active"]
            )

    def test_removed_source_markers_only_allow_code_review_not_host_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_consumer_tree(tmp, dependencies=False)
            x = module.inspect(Path(tmp))
            self.assertTrue(x["source_only_retirement_ready"])
            self.assertFalse(x["live_host_cleanup_authorized"])
            self.assertEqual(x["crons_removed"], 0)

    def test_symlinked_parent_or_file_never_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_consumer_tree(tmp, dependencies=True)
            p = Path(tmp) / "command_center/mpw_monitor_views.py"
            p.unlink()
            protected = Path(tmp) / "outside"
            protected.write_text("private")
            p.symlink_to(protected)
            x = module.inspect(Path(tmp))
            self.assertEqual(x["sites"]["mojplaywin"]["consumers"]["staff_dashboard"]["state"],
                             "symlink_refused")
            self.assertFalse(x["source_only_retirement_ready"])
            self.assertEqual(protected.read_text(), "private")

    def test_mixed_source_states_produce_independent_site_blockers(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_consumer_tree(tmp, dependencies=False)
            p = Path(tmp) / "content/zomorod-business/app.php"
            p.write_text("<?php require_once $private.'/site_agents.php';", encoding="utf-8")
            x = module.inspect(Path(tmp))
            self.assertFalse(x["sites"]["zomorodmelal"]["all_declared_consumers_reviewed"])
            self.assertTrue(x["sites"]["mojplaywin"]["all_declared_consumers_reviewed"])
