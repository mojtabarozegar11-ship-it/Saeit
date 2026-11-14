"""Regression evidence for common revenue intake file/PII and overwrite defects."""
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from mojtaba_revenue_safeio import read_json, create_private_json


class SecureFileContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.source = self.directory / "input.json"
        self.source.write_text('{"synthetic_example":true}', encoding="utf8")

    def test_01_small_json_object_reads(self):
        self.assertTrue(read_json(self.source)["synthetic_example"])

    def test_02_rejects_top_level_array(self):
        self.source.write_text("[1]")
        with self.assertRaises(ValueError):
            read_json(self.source)

    def test_03_rejects_empty_file(self):
        self.source.write_text("")
        with self.assertRaises(ValueError):
            read_json(self.source)

    def test_04_rejects_truncated_json(self):
        self.source.write_text('{"x":')
        with self.assertRaises(ValueError):
            read_json(self.source)

    def test_05_rejects_duplicate_root_keys(self):
        self.source.write_text('{"x":1,"x":2}')
        with self.assertRaises(ValueError):
            read_json(self.source)

    def test_06_rejects_nested_duplicate_keys(self):
        self.source.write_text('{"data":{"x":1,"x":3}}')
        with self.assertRaises(ValueError):
            read_json(self.source)

    def test_07_rejects_nonfinite_nan(self):
        self.source.write_text('{"x":NaN}')
        with self.assertRaises(ValueError):
            read_json(self.source)

    def test_08_rejects_nonfinite_infinity(self):
        self.source.write_text('{"x":Infinity}')
        with self.assertRaises(ValueError):
            read_json(self.source)

    def test_09_rejects_broken_utf8(self):
        self.source.write_bytes(b'{"x":"\xff"}')
        with self.assertRaises(ValueError):
            read_json(self.source)

    def test_10_rejects_oversize(self):
        self.source.write_text('{"x":"' + "X" * 65536 + '"}')
        with self.assertRaises(ValueError):
            read_json(self.source)

    def test_11_rejects_bad_limit_bool(self):
        with self.assertRaises(ValueError):
            read_json(self.source, limit=True)

    def test_12_rejects_bad_limit_zero(self):
        with self.assertRaises(ValueError):
            read_json(self.source, limit=0)

    def test_13_rejects_missing_path(self):
        with self.assertRaises(OSError):
            read_json(self.directory / "missing.json")

    def test_14_rejects_final_input_symlink(self):
        alias = self.directory / "alias.json"
        alias.symlink_to(self.source)
        with self.assertRaises(ValueError):
            read_json(alias)

    def test_15_rejects_ancestor_input_symlink(self):
        directory_link = self.directory / "alias-dir"
        directory_link.symlink_to(self.directory, target_is_directory=True)
        with self.assertRaises(ValueError):
            read_json(directory_link / "input.json")

    def test_16_rejects_input_directory(self):
        with self.assertRaises(ValueError):
            read_json(self.directory)

    def test_17_rejects_hardlinked_input(self):
        hard = self.directory / "hard.json"
        os.link(self.source, hard)
        with self.assertRaises(ValueError):
            read_json(hard)

    def test_18_rejects_parent_dot_dot(self):
        with self.assertRaises(ValueError):
            read_json(self.directory / "some" / ".." / "input.json")

    def test_19_private_created_mode(self):
        target = self.directory / "result.json"
        create_private_json(target, {"canonical_bot": "mojtaba.bot.ai"}, input_path=self.source)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)

    def test_20_existing_output_never_overwritten(self):
        target = self.directory / "result.json"
        target.write_text("KEEP")
        with self.assertRaises(OSError):
            create_private_json(target, {"x": 1}, input_path=self.source)
        self.assertEqual(target.read_text(), "KEEP")

    def test_21_input_overwrite_rejected(self):
        original = self.source.read_bytes()
        with self.assertRaises(ValueError):
            create_private_json(self.source, {"x": 1}, input_path=self.source)
        self.assertEqual(self.source.read_bytes(), original)

    def test_22_output_symlink_rejected(self):
        target = self.directory / "alias.json"
        target.symlink_to(self.source)
        with self.assertRaises(ValueError):
            create_private_json(target, {"x": 1}, input_path=self.source)

    def test_23_output_ancestor_symlink_rejected(self):
        directory_link = self.directory / "alias-dir"
        directory_link.symlink_to(self.directory, target_is_directory=True)
        with self.assertRaises(ValueError):
            create_private_json(directory_link / "result.json", {"x": 1})

    def test_24_existing_output_directory_rejected(self):
        with self.assertRaises((ValueError, OSError)):
            create_private_json(self.directory, {"x": 1})

    def test_25_new_output_has_valid_json(self):
        target = self.directory / "result.json"
        create_private_json(target, {"b": 2, "a": 1})
        self.assertEqual(json.loads(target.read_text()), {"a": 1, "b": 2})

    def test_26_outputs_no_nan(self):
        with self.assertRaises(ValueError):
            create_private_json(self.directory / "output.json", {"value": float("nan")})

    def test_27_outputs_bound_size(self):
        with self.assertRaises(ValueError):
            create_private_json(self.directory / "output.json", {"data": "x" * 262145})

    def test_28_rejects_output_array(self):
        with self.assertRaises(ValueError):
            create_private_json(self.directory / "out.json", [1])

    def test_29_rejects_nonexistent_output_parent(self):
        with self.assertRaises(ValueError):
            create_private_json(self.directory / "missing" / "out.json", {"x": 1})

    def test_30_no_spurious_data_on_invalid_output(self):
        target = self.directory / "out.json"
        with self.assertRaises(ValueError):
            create_private_json(target, {"x": object()})
        self.assertFalse(target.exists())

    def test_31_rejects_output_path_traversal(self):
        with self.assertRaises(ValueError):
            create_private_json(self.directory / "nest" / ".." / "out.json", {"x": 1})

    def test_32_rejects_source_path_symlink_for_writer(self):
        alias = self.directory / "alias.json"
        alias.symlink_to(self.source)
        with self.assertRaises(ValueError):
            create_private_json(self.directory / "result.json", {"x": 1}, input_path=alias)
