import datetime as dt
import importlib.util
from pathlib import Path
import unittest

src = Path(__file__).resolve().parents[1] / 'scripts/f01_s01_release_preflight_20261029.py'
spec = importlib.util.spec_from_file_location('f01_s01_preflight', src)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
NOW = dt.datetime(2026, 10, 29, 15, 40, tzinfo=dt.timezone.utc)


def snapshot():
    return {'schema': 'f01-vps-console-readonly.v1', 'read_only': True,
            'production_change': False, 'observed_utc': NOW.isoformat(),
            'filesystem': {'target_1': {'state': 'OBSERVED', 'available_bytes': 4 * 1024**3}},
            'guest': {'cpu_count': 4, 'loadavg': [2, 2, 2], 'memory': {'MemAvailable_kib': 1024 * 1024}},
            'process_pressure': {'state': 'OBSERVED', 'all_process_states': {'D': 0}, 'factory_max_children_same_parent': 2},
            'offhost_backup_restored': 'NOT_VERIFIED', 'worker_running_verified': False}


class ReleaseGateTests(unittest.TestCase):
    def test_missing_restore_is_no_go(self):
        result = mod.evaluate(snapshot(), NOW)
        self.assertEqual(result['guest_capacity_screen'], 'NO_GO')
        self.assertFalse(result['production_deployment_authorized'])
        self.assertIn('OFFHOST_RESTORE_UNVERIFIED', result['blockers'])

    def test_zero_disk_is_no_go(self):
        s = snapshot()
        s['filesystem']['target_1']['available_bytes'] = 0
        self.assertIn('ROOT_DISK_RESERVE_UNVERIFIED_OR_LOW', mod.evaluate(s, NOW)['blockers'])

    def test_stale_snapshot_is_no_go(self):
        s = snapshot()
        s['observed_utc'] = (NOW - dt.timedelta(hours=1)).isoformat()
        self.assertIn('STALE_OR_FUTURE_SNAPSHOT', mod.evaluate(s, NOW)['blockers'])

    def test_io_wait_storm_blocks_shared_release(self):
        s = snapshot()
        s['process_pressure']['all_process_states']['D'] = 26
        s['process_pressure']['factory_max_children_same_parent'] = 142
        self.assertIn('PROCESS_STORM_OR_IO_WAIT_UNVERIFIED_OR_HIGH', mod.evaluate(s, NOW)['blockers'])

    def test_missing_process_evidence_fails_closed(self):
        s = snapshot()
        s.pop('process_pressure')
        self.assertIn('PROCESS_STORM_OR_IO_WAIT_UNVERIFIED_OR_HIGH', mod.evaluate(s, NOW)['blockers'])

    def test_memory_starvation_fails_closed(self):
        s = snapshot()
        s['guest']['memory']['MemAvailable_kib'] = 128 * 1024
        self.assertIn('GUEST_AVAILABLE_MEMORY_UNVERIFIED_OR_LOW', mod.evaluate(s, NOW)['blockers'])

    def test_capacity_pass_is_not_deployment_approval(self):
        s = snapshot()
        s['offhost_backup_restored'] = 'VERIFIED'
        s['worker_running_verified'] = True
        result = mod.evaluate(s, NOW)
        self.assertEqual(result['guest_capacity_screen'], 'PASS')
        self.assertFalse(result['production_deployment_authorized'])


if __name__ == '__main__':
    unittest.main()
