"""Static release contract: economic promotion must not replace the factory ABI."""

import ast
from pathlib import Path
import re
import shlex
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "deploy/activate_vps_master_agent.sh").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/vps-master-agent-activate.yml").read_text(encoding="utf-8")
SHARED_RUNTIME = {
    "core/tool_gateway.py", "core/worker_runner.py", "core/task_runtime.py",
}


class EconomicIsolationReleaseTests(unittest.TestCase):
    def test_deployment_module_inventory_excludes_factory_shared_runtime(self):
        match = re.search(r"(?m)^modules=\(\n(?P<names>.*?)\n\)", SCRIPT, re.DOTALL)
        self.assertIsNotNone(match)
        files = set(match.group("names").split())
        self.assertTrue(SHARED_RUNTIME.isdisjoint(files))
        self.assertIn("core/economic_execution.py", files)
        self.assertIn("core/management/commands/run_economic_worker.py", files)

    def test_workflow_archive_matches_installer_without_shared_runtime(self):
        line = next(line.strip() for line in WORKFLOW.splitlines()
                    if line.strip().startswith('tar -cf "$d/bundle.tar" '))
        archive = set(shlex.split(line)[3:])
        self.assertTrue(SHARED_RUNTIME.isdisjoint(archive))

        match = re.search(r"(?s)expected=(\{.*?\})\n\s+with tarfile.open", WORKFLOW)
        self.assertIsNotNone(match)
        manifest = ast.literal_eval(match.group(1))
        self.assertEqual(archive, manifest)
        self.assertIn("core/economic_execution.py", manifest)

    def test_no_implicit_production_activation_on_merge_and_guard_before_stage(self):
        self.assertIn("github.event_name == 'workflow_dispatch'", WORKFLOW)
        self.assertIn("github.ref == 'refs/heads/main'", WORKFLOW)
        self.assertLess(WORKFLOW.index("MASTER_VPS_REMOTE_DISK_GUARD_BLOCKED"),
                        WORKFLOW.index('tar -cf "$d/bundle.tar"'))
        self.assertLess(WORKFLOW.index("MASTER_VPS_REMOTE_DISK_GUARD_BLOCKED"),
                        WORKFLOW.index("master-activation-source\"'"))

    def test_preserves_factory_bytes_and_rolls_back_failed_first_cycle(self):
        for path in SHARED_RUNTIME:
            self.assertIn(path, SCRIPT)
        self.assertIn('shared_before="$(sha256sum "${shared_modules[@]}")"', SCRIPT)
        self.assertIn('test "$(sha256sum "${shared_modules[@]}")" = "$shared_before"', SCRIPT)
        self.assertIn("MASTER_INITIAL_CYCLE_FAILED_ROLLING_BACK", SCRIPT)
        self.assertIn("trap restore_all EXIT", SCRIPT)

    def test_full_disk_fails_before_cron_pause_or_source_replacement(self):
        preflight = SCRIPT.index("MASTER_DISK_PREFLIGHT_BLOCKED")
        cron_pause = SCRIPT.index('crontab "$paused"')
        deployment = SCRIPT.index('sources_mutated=1')
        self.assertLess(preflight, cron_pause)
        self.assertLess(preflight, deployment)
        self.assertIn('needed = source.stat().st_size + max(512 * 1024 * 1024', SCRIPT)

    def test_failure_restores_cron_even_if_source_rollback_fails(self):
        self.assertIn('rollback_sources || rollback_failed=1', SCRIPT)
        self.assertIn('if crontab "$old"; then', SCRIPT)
        self.assertIn('MASTER_ROLLBACK_INCOMPLETE', SCRIPT)
        initial_run = SCRIPT.index('if ! "$master/run-cycle.sh"')
        first_cycle_complete = SCRIPT.index('echo MASTER_INITIAL_CYCLE_COMPLETED')
        disable_rollback = SCRIPT.rindex('trap - EXIT')
        self.assertLess(initial_run, disable_rollback)
        self.assertLess(disable_rollback, first_cycle_complete)


if __name__ == "__main__":
    unittest.main()
