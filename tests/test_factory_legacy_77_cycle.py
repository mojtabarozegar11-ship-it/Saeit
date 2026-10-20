import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("factory_legacy_77_cycle",ROOT/"scripts/factory_legacy_77_cycle.py")
module=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

class PrivateHeritageCycleTests(unittest.TestCase):
    def test_actual_77_safe_functions_and_exact_role_sources(self):
        result=module.evaluate(ROOT)
        self.assertTrue(result["vps_local_evaluation_success"])
        self.assertEqual(result["real_read_only_imports"],77)
        self.assertGreaterEqual(result["real_pure_function_probes"],14)
        self.assertEqual(result["robot_source_roles_verified"],11)
        self.assertEqual(result["separate_agents_executed"],0)
        self.assertFalse(result["customer_product_published"])
        self.assertFalse(result["agent_generation_auto_promoted"])

    def test_private_atomic_report_only(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/"reports"/"last.json"
            module.safe_write(out,{"schema":module.SCHEMA,"verified":True})
            self.assertTrue(json.loads(out.read_text())["verified"])
            self.assertEqual(out.stat().st_mode & 0o077,0)
            self.assertEqual(out.parent.stat().st_mode & 0o077,0)

    def test_symlinked_output_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            dest=Path(td)/"target.json"
            dest.write_text("{}")
            path=Path(td)/"symlink.json"
            path.symlink_to(dest)
            with self.assertRaisesRegex(RuntimeError,"HERITAGE_INVALID_OUTPUT"):
                module.safe_write(path,{"schema":module.SCHEMA})

if __name__=="__main__":
    unittest.main()
