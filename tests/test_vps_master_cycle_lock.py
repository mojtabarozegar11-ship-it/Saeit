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

    def test_activation_rejects_incompatible_identity_before_any_mutation(self):
        """A canonical handoff cannot be reversed by the legacy-only installer."""
        source = (REPO_ROOT / 'deploy/activate_vps_master_agent.sh').read_text(encoding='utf-8')
        assert 'MASTER_ACTIVATION_CANONICAL_HANDOFF_NOT_SUPPORTED' in source
        assert 'MASTER_ACTIVATION_MULTIPLE_ACTIVE_RUNTIMES' in source
        assert 'MASTER_ACTIVATION_OPERATOR_DISABLED_RUNTIME' in source
        assert source.index('master_identity_preflight\nmaster_capacity_preflight') < source.index(
            'install -d -m 700 "$master"'
        )
        syntax = subprocess.run(['bash', '-n'], input=source, text=True, capture_output=True)
        self.assertEqual(syntax.returncode, 0, syntax.stderr)

    def test_cycle_has_one_nonblocking_lock_for_both_commands(self):
        script = _extract_runner()
        self.assertIn('exec 9>"$root/master-cycle.lock"', script)
        self.assertIn('if ! flock -n 9; then', script)
        self.assertIn('timeout 30 "$py" manage.py recover_stale_tasks', script)
        self.assertIn('timeout 780 "$py" manage.py autonomous_master_loop', script)
        self.assertNotIn('flock -n "$root/master-cycle.lock" timeout', script)
        syntax = subprocess.run(['bash', '-n'], input=script, text=True, capture_output=True)
        self.assertEqual(syntax.returncode, 0, syntax.stderr)

    def test_cycle_requires_fresh_readonly_policy_before_any_task(self):
        # A wrapper that skips the policy check must never pass this guard,
        # even if it still happens to enforce a filesystem lock.
        script = _extract_runner()
        self.assertIn('MASTER_EVOLUTION_CHECK_ONLY=', script)
        self.assertIn('--check-only', script)
        self.assertIn('preflight_passed=false', script)
        self.assertIn('MASTER_EVOLUTION_PREFLIGHT_BLOCKED_NO_TASK_EXECUTION', script)
        self.assertLess(script.index('--check-only'), script.index('recover_stale_tasks'))

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
                'if [ "$1" = "-" ]; then echo /fixture/read-only.sqlite3; exit 0; fi\n'
                'if [ "$1" = "$HOME/factory-runtime/operations/master-agent/evolution.py" ]; then\n'
                '  printf "MASTER_EVOLUTION_MAX_STEPS=1\\n"\n'
                '  printf "MASTER_EVOLUTION_PREVIOUS_MAX_STEPS=1\\n"\n'
                '  printf "MASTER_EVOLUTION_CHECK_ONLY=true\\n"\n'
                '  exit 0\n'
                'fi\n'
                'if [ "$1" = "manage.py" ]; then\n'
                '  printf "%s\\n" "$2" >> "$MOJ_AGENT_LOCK_TEST_LOG"\n'
                '  sleep 0.35\n'
                '  exit 0\n'
                'fi\n'
                'exit 23\n',
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


if __name__ == '__main__':
    unittest.main()
