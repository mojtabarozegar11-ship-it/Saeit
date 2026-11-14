"""Offline security regression tests for pre-sale intake file handling."""
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "revenue_intake_io.py"
spec = importlib.util.spec_from_file_location("revenue_intake_io", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class IntakeIOTests(unittest.TestCase):
    def test_regular_json_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"input.json";p.write_text('{"scope_items":1}')
            self.assertEqual(mod.read_strict_json(p), {"scope_items":1})

    def test_reject_duplicate_consent_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"input.json";p.write_text('{"consent":false,"consent":true}')
            with self.assertRaisesRegex(ValueError, "ambiguous"):
                mod.read_strict_json(p)

    def test_nested_duplicate_key_is_also_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"input.json";p.write_text('{"x":{"x":1,"x":2}}')
            with self.assertRaises(ValueError):mod.read_strict_json(p)

    def test_reject_nonfinite(self):
        for v in ("NaN","Infinity","-Infinity"):
            with tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp)/"input.json";p.write_text('{"x":'+v+'}')
                with self.assertRaises(ValueError):mod.read_strict_json(p)

    def test_reject_input_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"input.json";p.write_text('{}')
            link=Path(tmp)/"link";link.symlink_to(p)
            with self.assertRaises(ValueError):mod.read_strict_json(link)

    def test_reject_fifo_nonblocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"fifo";os.mkfifo(p)
            with self.assertRaises(ValueError):mod.read_strict_json(p)

    def test_reject_oversize(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"input.json";p.write_bytes(b" "*(mod.MAX_BYTES+1))
            with self.assertRaises(ValueError):mod.read_strict_json(p)

    def test_reject_non_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"input.json";p.write_bytes(b'\xff')
            with self.assertRaises(ValueError):mod.read_strict_json(p)

    def test_reject_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"input.json";p.write_text('{"incomplete":')
            with self.assertRaises(ValueError):mod.read_strict_json(p)

    def test_new_sanitized_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"out.json";mod.write_new_anonymized_json(p, '{"status":"inquiry_only"}\n')
            self.assertEqual(json.loads(p.read_text()),{"status":"inquiry_only"})

    def test_output_is_private_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"out.json";mod.write_new_anonymized_json(p,'{}')
            self.assertEqual(stat.S_IMODE(p.stat().st_mode)&0o077,0)

    def test_existing_output_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"out.json";p.write_text('ORIGINAL')
            with self.assertRaisesRegex(ValueError,'overwrite'):
                mod.write_new_anonymized_json(p,'REPLACEMENT')
            self.assertEqual(p.read_text(),'ORIGINAL')

    def test_output_symlink_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"real";p.write_text('SAFE')
            q=Path(tmp)/"link";q.symlink_to(p)
            with self.assertRaises(ValueError):mod.write_new_anonymized_json(q,'WRONG')
            self.assertEqual(p.read_text(),'SAFE')

    def test_oversized_output_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"out"
            with self.assertRaises(ValueError):mod.write_new_anonymized_json(p,'x'*(mod.MAX_BYTES+1))
            self.assertFalse(p.exists())

    def test_nonstring_output_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"out"
            with self.assertRaises(ValueError):mod.write_new_anonymized_json(p,{'x':1})
            self.assertFalse(p.exists())


    def test_smaller_input_policy_blocks_same_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "input.json"
            p.write_text('{"scope_items":1}', encoding="utf-8")
            with self.assertRaises(ValueError):
                mod.read_strict_json(p, max_bytes=5)
            self.assertEqual(mod.read_strict_json(p, max_bytes=50), {"scope_items": 1})

    def test_reject_invalid_limit_booleans_and_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "input.json"
            p.write_text("{}", encoding="utf-8")
            for bad in (True, False, 0, -1, "100", mod.MAX_BYTES + 1):
                with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "size policy"):
                    mod.read_strict_json(p, max_bytes=bad)

    def test_very_deep_json_is_controlled_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "deep.json"
            p.write_text("[" * 1500 + "0" + "]" * 1500, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid or ambiguous"):
                mod.read_strict_json(p)

    def test_invalid_input_size_limit_cannot_bypass_maximum(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "input.json"
            p.write_bytes(b" " * (mod.MAX_BYTES + 1))
            with self.assertRaises(ValueError):
                mod.read_strict_json(p, max_bytes=mod.MAX_BYTES + 1)

    def test_mid_read_file_change_cannot_be_accepted(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "input.json"
            p.write_text('{"consent":true}', encoding="utf-8")
            original = mod.os.fstat
            calls = [0]
            def modified_stat(fd):
                result = original(fd)
                calls[0] += 1
                if calls[0] == 2:
                    values = list(result)
                    # st_size is field 6 in an os.stat_result.
                    values[6] += 1
                    return os.stat_result(values)
                return result
            with patch.object(mod.os, "fstat", side_effect=modified_stat):
                with self.assertRaisesRegex(ValueError, "changed during read"):
                    mod.read_strict_json(p)

    def test_python_loader_errors_do_not_escape_as_recursionerror(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "input.json"
            p.write_text("{}", encoding="utf-8")
            with patch.object(mod.json, "loads", side_effect=RecursionError("secret")):
                with self.assertRaisesRegex(ValueError, "invalid or ambiguous") as caught:
                    mod.read_strict_json(p)
            self.assertNotIn("secret", str(caught.exception))

if __name__=='__main__':unittest.main()
