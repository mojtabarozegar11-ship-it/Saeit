import pathlib
import subprocess
import sys
import tempfile
import unittest

from scripts.f01_factory_dispatch_guard_20261030 import assess, inspect

ROOT = pathlib.Path(__file__).resolve().parents[1]

class FactoryDispatchGuardTests(unittest.TestCase):
    def test_overload_fails_closed(self):
        d = assess(3, 128.06, 2 * 1024**3, 12000)
        self.assertEqual(d["decision"], "SKIP")
        self.assertIn("ONE_MINUTE_LOAD_OVER_LIMIT", d["reasons"])

    def test_zero_writable_space_skips(self):
        d = assess(3, 1.0, 0, 50000)
        self.assertEqual(d["decision"], "SKIP")
        self.assertIn("UNPRIVILEGED_DISK_HEADROOM_LOW", d["reasons"])

    def test_out_of_inodes_skips(self):
        self.assertIn("UNPRIVILEGED_INODES_LOW", assess(4, 1.0, 2**31, 0)["reasons"])

    def test_normal_capacity_admits(self):
        d = assess(4, 2.0, 2**31, 100000)
        self.assertEqual(d["decision"], "ADMIT")
        self.assertTrue(d["no_process_signals"])
        self.assertTrue(d["no_files_modified"])

    def test_unknown_evidence_fails_closed(self):
        self.assertEqual(assess(None, float("nan"), None, None)["decision"], "SKIP")

    def test_symlinked_ops_is_not_followed(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "real").mkdir()
            (root / "link").symlink_to(root / "real", target_is_directory=True)
            d = inspect(root / "link")
            self.assertEqual(d["decision"], "SKIP")
            self.assertEqual(d["reasons"], ["HOST_EVIDENCE_UNAVAILABLE"])

    def test_nonexistent_ops_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            d = inspect(pathlib.Path(td) / "missing")
            self.assertEqual(d["decision"], "SKIP")

    def test_installer_guard_before_lock_and_worker_after_lock(self):
        data = (ROOT / "deploy" / "install_factory_40_execution_controller.sh").read_text()
        self.assertIn('f01_factory_dispatch_guard_20261030.py', data)
        self.assertIn('exec /usr/bin/flock -n -E 0 -o ', data)
        block = data[data.index('cat > "$target/periodic-dispatch.sh" <<SH'):]
        self.assertLess(block.index('f01_factory_dispatch_guard_20261030.py'),
                        block.index('flock -n -E 0 -o'))
        worker = block[block.index('cat > "$target/periodic-dispatch-worker.sh" <<SH'):]
        self.assertLess(worker.index('f01_factory_dispatch_guard_20261030.py'),
                        worker.index('forty-execution.log'))
        self.assertNotIn('exec 9>"$ops/.forty-execution-scheduler.lock"', data)

    def test_flock_closes_lock_descriptor_in_worker(self):
        with tempfile.TemporaryDirectory() as td:
            lock = str(pathlib.Path(td) / "single-flight.lock")
            code = """
import os, subprocess
p=os.environ['F01_LOCK']
for fd in os.listdir('/proc/self/fd'):
    try: target=os.readlink('/proc/self/fd/'+fd)
    except OSError: continue
    if target==p: raise SystemExit('LOCK_DESCRIPTOR_LEAK')
r=subprocess.run(['/usr/bin/flock','-n','-E','99',p,'/bin/true'])
if r.returncode!=99: raise SystemExit('LOCK_NOT_HELD_BY_PARENT')
"""
            p=subprocess.run(['/usr/bin/flock','-n','-E','0','-o',lock,sys.executable,'-c',code],
                             env={**__import__('os').environ,'F01_LOCK':lock},
                             stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=6)
            self.assertEqual(p.returncode,0,p.stderr)

if __name__ == "__main__":
    unittest.main()
