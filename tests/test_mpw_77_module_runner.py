"""All 77 original modules must be verified, import-exercised and never auto-promoted."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/mpw_77_modules_private_runner.py"
spec=importlib.util.spec_from_file_location("mpw_test_77",SCRIPT)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class Module77Test(unittest.TestCase):
    def test_all_seventy_seven_original_sha_sources_are_present(self):
        names,info=mod.preflight()
        self.assertEqual(len(names),77)
        self.assertEqual(len(info),77)
        self.assertEqual(len(set(names)),77)
        self.assertTrue(all(x["sha256"] for x in info))
        self.assertTrue(all(x.startswith("mpw_v91_port.legacy.") for x in names))

    def test_imports_are_real_in_isolated_readonly_process(self):
        report=mod.execute()
        self.assertEqual(report["modules_hash_verified"],77)
        self.assertEqual(report["modules_import_executed"],77)
        self.assertEqual(report["modules_syntax_checked"],77)
        self.assertIn("gen12_pareto_selection",report["safe_function_probes"])
        self.assertEqual(report["capability_namespaces_active"],77)
        self.assertGreaterEqual(report["functional_probes_executed"],14)
        self.assertEqual(len(report["per_module_capability_registry"]),77)
        self.assertTrue(all(row["loaded"] and row["safe_scope"]=="read_only_private"
                            for row in report["per_module_capability_registry"]))
        self.assertTrue(all(row["exported_callables"] for row in report["per_module_capability_registry"]
                            if row["kind"]=="capability_module"))
        expected={"gen12_deterministic_cache_fingerprint",
                  "gen16_tamper_evident_telemetry",
                  "gen20_semantic_canonicalization",
                  "gen24_executable_contract_guard",
                  "gen28_dependency_budget_planner",
                  "gen32_failure_circuit_guard",
                  "gen40_versioned_state_cas",
                  "gen48_integrity_checked_checkpoint",
                  "gen56_open_recover_circuit",
                  "v91_legacy_clean_text"}
        self.assertTrue(expected.issubset(set(report["safe_function_probes"])))
        self.assertFalse(report["financial_authority"])
        self.assertFalse(report["public_site_modified"])
        self.assertEqual(report["standalone_agent_processes_created"],0)

    def test_malicious_origin_or_changed_sha_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/"mpw_v91_port/legacy").mkdir(parents=True)
            (root/"mpw_v91_port/legacy/module.py").write_text("x=1")
            manifest={"file_count":77,"modules":[{"destination":"mpw_v91_port/legacy/module.py",
                                                  "sha256":"f"*64} for _ in range(77)]}
            (root/"mpw_v91_port/ORIGIN.json").write_text(json.dumps(manifest))
            old=(mod.STAGE,mod.PACKAGE,mod.ORIGIN)
            try:
                mod.STAGE=root
                mod.PACKAGE=root/"mpw_v91_port"
                mod.ORIGIN=mod.PACKAGE/"ORIGIN.json"
                with self.assertRaisesRegex(RuntimeError,"UNSAFE_OR_DUPLICATE_MODULE_PATH|ORIGINAL_CODE_HASH_MISMATCH"):
                    mod.preflight()
            finally:
                mod.STAGE,mod.PACKAGE,mod.ORIGIN=old

    def test_no_legacy_scripts_run_as_main(self):
        self.assertIn('importlib.import_module(name)',mod.CHILD)
        self.assertIn("MODULE_WRITE_REFUSED",mod.CHILD)
        self.assertIn("READ_ONLY_MODULE_AUDIT_BLOCKED",mod.CHILD)
        self.assertNotIn("runpy.run_path",mod.CHILD)

if __name__=="__main__":
    unittest.main()
