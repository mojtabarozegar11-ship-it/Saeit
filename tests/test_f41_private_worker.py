import os
from pathlib import Path
import tempfile
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import f41_private_worker as worker

REPO = Path(__file__).resolve().parents[1]
SAMPLES = REPO / "examples" / "f41-merchant-audit"


class PrivateWorkerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "runtime"
        self.root.mkdir(mode=0o700)
        os.chmod(self.root, 0o700)
        self.env = mock.patch.dict(os.environ, {"F41_WORKER_ONCHAIN_ENABLED": "0"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def job(self, name, valid=True):
        inbox = self.root / "inbox"
        inbox.mkdir(mode=0o700, exist_ok=True)
        folder = inbox / name
        folder.mkdir(mode=0o700)
        for part in ("invoices.csv", "payments.csv"):
            data = (SAMPLES / part).read_bytes() if valid else b"invalid csv\n"
            p = folder / part
            p.write_bytes(data)
            p.chmod(0o600)
        marker = folder / "READY"
        marker.write_bytes(b"")
        marker.chmod(0o600)
        return folder

    def test_empty_tick_waits_without_fake_transactions(self):
        x = worker.tick(self.root)
        self.assertEqual(x["state"], "WAITING_FOR_INPUT")
        self.assertEqual(x["completed_this_tick"], 0)
        self.assertFalse(x["delivery_authorized"])

    def test_reconciles_once_and_never_delivers(self):
        self.job("job-01")
        first = worker.tick(self.root)
        self.assertEqual(first["completed_this_tick"], 1)
        output = self.root / "outbox" / "job-01"
        record = __import__("json").loads((output / "status.json").read_text())
        self.assertEqual(record["result"], "COMPLETE_READONLY")
        self.assertFalse(record["delivery_authorized"])
        self.assertFalse(record["onchain_check_enabled"])
        self.assertEqual(record["attempted_network_lookups"], 0)
        self.assertTrue((output / "reconciliation" / "integrity.json").is_file())
        self.assertEqual(worker.tick(self.root)["completed_this_tick"], 0)

    def test_three_jobs_per_tick(self):
        for i in range(5):
            self.job("job-" + str(i))
        self.assertEqual(worker.tick(self.root)["completed_this_tick"], 3)
        self.assertEqual(worker.tick(self.root)["completed_this_tick"], 2)

    def test_invalid_record_is_repair_queue_not_success(self):
        self.job("job-bad", valid=False)
        self.assertEqual(worker.tick(self.root)["repair_this_tick"], 1)
        record = __import__("json").loads((self.root / "outbox" / "job-bad" / "status.json").read_text())
        self.assertEqual(record["result"], "REQUIRES_REPAIR")
        self.assertFalse(record["delivery_authorized"])

    def test_symlink_inputs_cannot_be_processed(self):
        source = self.job("job-symlink")
        (source / "payments.csv").unlink()
        (source / "payments.csv").symlink_to(SAMPLES / "payments.csv")
        self.assertEqual(worker.tick(self.root)["repair_this_tick"], 1)
        self.assertFalse((self.root / "outbox" / "job-symlink" / "reconciliation").exists())


if __name__ == "__main__":
    unittest.main()
