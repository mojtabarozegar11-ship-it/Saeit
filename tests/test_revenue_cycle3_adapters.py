"""End-to-end validation that all four existing revenue CLIs use the same safe IO."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
EXAMPLES = ROOT / "docs/revenue-p0"
SOURCES = {
    "central": "mojtaba_revenue_cli.py",
    "quotes": "revenue_cycle2_quote.py",
    "dual": "revenue_dual_offer_qualifier.py",
    "farm": "revenue_cycle2_farm_preview.py",
}
INPUTS = {
    "central": (EXAMPLES / "cycle2/examples/website_diagnosis.synthetic.json"),
    "quotes": (EXAMPLES / "cycle2/examples/website_diagnosis.synthetic.json"),
    "dual": (EXAMPLES / "example-checkout-intake.synthetic.json"),
    "farm": (EXAMPLES / "example-farm-model.synthetic.json"),
}


def run(name, input_path, *, output=None):
    script = SCRIPTS / SOURCES[name]
    cmd = [sys.executable, str(script)]
    if name == "central":
        cmd += ["--qualify", str(input_path)]
    else:
        cmd.append(str(input_path))
    if output is not None:
        cmd += ["--output", str(output)]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=12)


class FourAdapterContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def copied(self, name):
        target = self.root / (name + ".json")
        target.write_bytes(INPUTS[name].read_bytes())
        return target

    def test_01_all_four_accept_known_synthetic_inputs(self):
        for name in SOURCES:
            with self.subTest(name=name):
                r = run(name, self.copied(name))
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(json.loads(r.stdout)["canonical_bot"], "mojtaba.bot.ai")

    def test_02_all_four_reject_symlink_input(self):
        for name in SOURCES:
            with self.subTest(name=name):
                actual = self.copied(name)
                link = self.root / (name + "-link.json")
                link.symlink_to(actual)
                self.assertEqual(run(name, link).returncode, 2)

    def test_03_all_four_reject_duplicate_json_keys(self):
        for name in SOURCES:
            with self.subTest(name=name):
                path = self.copied(name)
                path.write_text('{"x":1,"x":2}')
                self.assertEqual(run(name, path).returncode, 2)

    def test_04_all_four_reject_oversize(self):
        for name in SOURCES:
            with self.subTest(name=name):
                path = self.copied(name)
                path.write_text('{"x":"' + "A"*70000 + '"}')
                self.assertEqual(run(name, path).returncode, 2)

    def test_05_all_four_reject_file_input_directory(self):
        for name in SOURCES:
            with self.subTest(name=name):
                self.assertEqual(run(name, self.root).returncode, 2)

    def test_06_all_four_reject_broken_utf8(self):
        for name in SOURCES:
            with self.subTest(name=name):
                path = self.copied(name)
                path.write_bytes(b'{"x":"\xff"}')
                self.assertEqual(run(name, path).returncode, 2)

    def test_07_all_four_do_not_echo_invalid_personal_value(self):
        for name in SOURCES:
            with self.subTest(name=name):
                path = self.copied(name)
                path.write_bytes(b'{"email":"SECRET_NOT_PUBLIC","email":"OTHER_SECRET"}')
                result = run(name, path)
                self.assertEqual(result.returncode, 2)
                self.assertNotIn("SECRET_NOT_PUBLIC", result.stdout + result.stderr)
                self.assertNotIn("OTHER_SECRET", result.stdout + result.stderr)

    def test_08_three_writing_adapters_create_mode_0600(self):
        for name in ("central", "quotes", "dual"):
            with self.subTest(name=name):
                source = self.copied(name)
                target = self.root / (name + "-result.json")
                result = run(name, source, output=target)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
                self.assertEqual(json.loads(target.read_text())["canonical_bot"],
                                 "mojtaba.bot.ai")

    def test_09_existing_output_is_never_clobbered(self):
        for name in ("central", "quotes", "dual"):
            with self.subTest(name=name):
                src = self.copied(name)
                output = self.root / (name + "-result.json")
                output.write_text("PRESERVE")
                result = run(name, src, output=output)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(output.read_text(), "PRESERVE")

    def test_10_input_output_same_file_refused(self):
        for name in ("central", "quotes", "dual"):
            with self.subTest(name=name):
                src = self.copied(name)
                before = src.read_bytes()
                self.assertEqual(run(name, src, output=src).returncode, 2)
                self.assertEqual(src.read_bytes(), before)

    def test_11_output_symlink_does_not_modify_target(self):
        for name in ("central", "quotes", "dual"):
            with self.subTest(name=name):
                src = self.copied(name)
                alias = self.root / (name + "-output.json")
                alias.symlink_to(src)
                before = src.read_bytes()
                self.assertEqual(run(name, src, output=alias).returncode, 2)
                self.assertEqual(src.read_bytes(), before)

    def test_12_all_three_writers_deny_ancestor_symlink(self):
        aliasdir = self.root / "symlink_parent"
        aliasdir.symlink_to(self.root, target_is_directory=True)
        for name in ("central", "quotes", "dual"):
            with self.subTest(name=name):
                src = self.copied(name)
                self.assertEqual(run(name, src, output=aliasdir/(name + "-result.json")).returncode, 2)

    def test_13_quote_output_preserves_no_revenue_claim(self):
        src = self.copied("quotes")
        target = self.root / "quote.json"
        self.assertEqual(run("quotes", src, output=target).returncode, 0)
        q = json.loads(target.read_text())
        self.assertFalse(q["payment_verified"])
        self.assertFalse(q["quote_sent"])
        self.assertIsNone(q["collected_revenue"])

    def test_14_dual_output_is_inquiry_only(self):
        src = self.copied("dual")
        target = self.root / "dual.json"
        self.assertEqual(run("dual", src, output=target).returncode, 0)
        q = json.loads(target.read_text())
        self.assertEqual(q["order_state"], "inquiry_only")
        self.assertEqual(q["payment_state"], "not_requested")

    def test_15_farm_sample_never_claims_actual_revenue(self):
        res = run("farm", self.copied("farm"))
        self.assertEqual(res.returncode, 0)
        val = json.loads(res.stdout)
        self.assertTrue(val["sample_only"])
        self.assertIsNone(val["actual_revenue"])

    def test_16_adapter_imports_no_second_bot(self):
        for name, script in SOURCES.items():
            with self.subTest(name=name):
                text = (SCRIPTS/script).read_text()
                self.assertNotIn("another.bot", text)

    def test_17_all_four_use_bounded_read(self):
        for name in SOURCES:
            with self.subTest(name=name):
                text = (SCRIPTS / SOURCES[name]).read_text()
                self.assertIn("read_json", text)

    def test_18_all_three_use_safe_output(self):
        for name in ("central", "quotes", "dual"):
            with self.subTest(name=name):
                text = (SCRIPTS / SOURCES[name]).read_text()
                self.assertIn("create_private_json", text)


if __name__ == "__main__":
    unittest.main()
