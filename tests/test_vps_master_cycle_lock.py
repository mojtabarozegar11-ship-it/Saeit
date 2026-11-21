"""Verify that the private VPS master holds one lock across its full cycle.

Runs the actual embedded cron script with a harmless temporary Python stand-in.
No VPS, network, Django database or external action is accessed.
"""

import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _extract_runner():
    source = (REPO_ROOT / 'deploy/activate_vps_master_agent.sh').read_text(encoding='utf-8')
    opening = "cat > \"$master/run-cycle.sh.tmp\" <<'SH'\n"
    if opening not in source:
        raise AssertionError('The master run-cycle script is missing')
    return source.split(opening, 1)[1].split('\nSH\n', 1)[0] + '\n'


class VpsMasterCycleLockTests(unittest.TestCase):
    def test_cycle_has_one_nonblocking_lock_for_both_commands(self):
        script = _extract_runner()
        self.assertIn('exec 9>"$root/master-cycle.lock"', script)
        self.assertIn('if ! flock -n 9; then', script)
        self.assertIn('timeout 30 "$py" manage.py recover_stale_tasks', script)
        self.assertIn('timeout 780 "$py" manage.py autonomous_master_loop', script)
        self.assertNotIn('flock -n "$root/master-cycle.lock" timeout', script)
        syntax = subprocess.run(['bash', '-n'], input=script, text=True, capture_output=True)
        self.assertEqual(syntax.returncode, 0, syntax.stderr)

    def test_parallel_cron_starts_do_not_execute_overlapping_master_work(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = root / 'factory-runtime'
            app = runtime / 'django-app'
            app.mkdir(parents=True)
            (app / 'manage.py').touch()
            runner_dir = runtime / 'operations/master-agent'
            runner_dir.mkdir(parents=True)
            py = runtime / '.venv/bin/python'
            py.parent.mkdir(parents=True)
            log = root / 'events.txt'
            py.write_text(
                '#!/bin/sh\n'
                'if [ "$1" = "-" ]; then echo 1; exit 0; fi\n'
                'printf "%s\n" "$2" >> "$MOJ_AGENT_LOCK_TEST_LOG"\n'
                'sleep 0.35\n',
                encoding='utf-8',
            )
            py.chmod(0o700)
            runner = root / 'run-cycle.sh'
            runner.write_text(_extract_runner(), encoding='utf-8')
            runner.chmod(0o700)
            env = {**os.environ, 'HOME': str(root), 'MOJ_AGENT_LOCK_TEST_LOG': str(log)}

            first = subprocess.Popen(['bash', str(runner)], stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, env=env)
            try:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if log.exists() and 'autonomous_master_loop' in log.read_text(encoding='utf-8'):
                        break
                    time.sleep(0.02)
                else:
                    self.fail('The first cycle never entered its execution phase')

                second = subprocess.run(['bash', str(runner)], text=True, capture_output=True,
                                        env=env, timeout=5)
                self.assertEqual(second.returncode, 0, second.stderr)
                self.assertIn('MASTER_CYCLE_ALREADY_RUNNING', second.stdout)
            finally:
                stdout, stderr = first.communicate(timeout=5)
                self.assertEqual(first.returncode, 0, stderr + stdout)

            self.assertEqual(log.read_text(encoding='utf-8').splitlines(), [
                'recover_stale_tasks', 'autonomous_master_loop',
            ])


    def test_private_deployment_transfers_economic_autorun_lock_module(self):
        module = 'core/management/commands/economic_autorun.py'
        activation = (REPO_ROOT / 'deploy/activate_vps_master_agent.sh').read_text(
            encoding='utf-8')
        workflow = (REPO_ROOT / '.github/workflows/vps-master-agent-activate.yml').read_text(
            encoding='utf-8')
        # Source inclusion, transfer bundle, and unpack manifest must agree.
        self.assertIn('\n  ' + module + '\n', activation)
        tar_line = next(line for line in workflow.splitlines()
                        if line.lstrip().startswith('tar -cf "$d/bundle.tar"'))
        self.assertIn(module, tar_line)
        self.assertIn('"' + module + '"', workflow)
        # The verification job and both trigger filters must see future fixes.
        self.assertGreaterEqual(workflow.count(module), 6)

if __name__ == '__main__':
    unittest.main()
