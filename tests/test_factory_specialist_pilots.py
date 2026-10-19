"""Private specialist pilot regressions: no false completion, safe retries and hashing."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "factory_specialist_pilots", str(ROOT / "scripts/factory_specialist_pilots.py"))
pilots = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilots)


class SpecialistPilotTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.output = self.root / "private"
        self.manifest = self.root / "build-toolchain" / "toolchain-manifest.json"
        self.version = self.manifest.parent / "versions" / ("a" * 40)
        (self.version / "venv" / "bin").mkdir(parents=True)
        (self.version / "venv" / "bin" / "python").write_bytes(b"fake-bin")
        (self.version / "proof.json").write_text("{}")
        self.manifest.write_text(json.dumps({
            "schema": "saeit.factory.toolchain.v1", "root": str(self.version),
            "python": str(self.version / "venv/bin/python"),
            "checks": {name: {"passed": True} for name in pilots.REQUIRED}}))

    def test_bad_or_absent_proofs_block_execution(self):
        data = json.loads(self.manifest.read_text())
        data["checks"]["documents"]["passed"] = False
        self.manifest.write_text(json.dumps(data))
        with mock.patch.object(pilots.subprocess, "run") as run:
            state = pilots.cycle(self.output, self.manifest)
            self.assertEqual(state["status"], "awaiting_verified_toolchain")
            run.assert_not_called()
        self.assertFalse(list((self.output / "family-pilots").glob("*/technical-receipt.json")))

    def test_verified_venv_python_symlink_is_allowed(self):
        # Standard venv/bin/python is commonly a symlink to its interpreter.
        local_interpreter = self.root / "trusted-interpreter"
        local_interpreter.write_bytes(b"trusted-binary")
        link = self.version / "venv" / "bin" / "python"
        link.unlink()
        link.symlink_to(local_interpreter)
        version, executable = pilots.toolchain(self.manifest)
        self.assertEqual(version, self.version)
        self.assertEqual(executable, link)

    def test_manifest_cannot_run_unpinned_python(self):
        data = json.loads(self.manifest.read_text())
        data["python"] = "/tmp/untrusted-python"
        self.manifest.write_text(json.dumps(data))
        with self.assertRaises(RuntimeError):
            pilots.toolchain(self.manifest)

    def _write_generated(self, args, **kwargs):
        self.assertEqual(args[3:4], ["--render"])
        family = args[4]
        stage = Path(args[6])
        output = {}
        for name in pilots.FAMILIES[family]:
            path = stage / name
            path.write_bytes((family + name).encode() * 30)
            output[name] = pilots.sha(path)
        return type("Result", (), {"returncode": 0,
                                    "stdout": json.dumps(output), "stderr": ""})()

    def test_one_new_family_per_tick_then_idempotent(self):
        with mock.patch.object(pilots.subprocess, "run", side_effect=self._write_generated) as run:
            names = []
            for n in range(4):
                status = pilots.cycle(self.output, self.manifest)
                self.assertEqual(status["status"], "pilot_built")
                names.append(status["family"])
                self.assertEqual(run.call_count, n + 1)
            self.assertEqual(set(names), set(pilots.FAMILIES))
            same = pilots.cycle(self.output, self.manifest)
            self.assertEqual(same["status"], "technical_pilots_verified")
            self.assertEqual(run.call_count, 4)
            self.assertEqual(same["fully_verified_families"], 0)

    def test_corrupt_previous_product_is_retained_and_rebuilt(self):
        with mock.patch.object(pilots.subprocess, "run", side_effect=self._write_generated) as run:
            initial = pilots.cycle(self.output, self.manifest)
            version = self.output / "family-pilots" / "F27" / initial["source_key"]
            expected = json.loads((version / "technical-receipt.json").read_text())["files"]["budget.xlsx"]
            (version / "budget.xlsx").write_bytes(b"corrupt")
            second = pilots.cycle(self.output, self.manifest)
            self.assertEqual(second["family"], "F27")
            self.assertEqual(run.call_count, 2)
            self.assertEqual(pilots.sha(version / "budget.xlsx"), expected)
            preserved = list(version.parent.glob("retained-damaged-*"))
            self.assertEqual(len(preserved), 1)
            self.assertEqual((preserved[0] / "budget.xlsx").read_bytes(), b"corrupt")
            self.assertTrue(pilots.verified_receipt(version, "F27", initial["source_key"]))

    def test_failed_pilot_is_never_auto_approved_and_retries(self):
        def fail(*args, **kwargs):
            return type("Result", (), {"returncode": 1,
                                        "stdout": "", "stderr": "simulated generator error"})()
        with mock.patch.object(pilots.subprocess, "run", side_effect=fail) as run:
            first = pilots.cycle(self.output, self.manifest)
            second = pilots.cycle(self.output, self.manifest)
        self.assertEqual(first["status"], "needs_rework")
        self.assertEqual(second["status"], "needs_rework")
        self.assertEqual(run.call_count, 2)
        self.assertTrue(list((self.output / "family-pilots/F27").glob("rework.json")))
        self.assertFalse(list((self.output / "family-pilots/F27").glob("*/technical-receipt.json")))


if __name__ == "__main__":
    unittest.main()
