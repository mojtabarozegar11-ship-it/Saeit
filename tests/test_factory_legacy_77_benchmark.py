import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/"scripts/factory_legacy_77_benchmark.py"
spec=importlib.util.spec_from_file_location("factory_legacy_benchmark",SCRIPT)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class LegacyIsolation(unittest.TestCase):
    def test_77_sha_verified_sources_and_eleven_actual_robot_names(self):
        r=m.benchmark(run_child=False)
        self.assertEqual(r["historical_hash_verified"],77)
        self.assertEqual(r["historical_robot_roles"],11)
        self.assertEqual(r["historical_module_imports_tested"],0)
        self.assertFalse(r["factory_service_activated"])
        self.assertFalse(r["cpanel_runtime_hashes_verified"])
        self.assertFalse(r["site_publication_authorized"])

    def test_no_masquerading_quarantined_imports_as_live_factory(self):
        r=m.benchmark(run_child=True)
        self.assertEqual(r["historical_module_imports_tested"],77)
        self.assertGreaterEqual(r["historical_functional_probes_tested"],14)
        self.assertFalse(r["live_vps_worker_verified"])
        self.assertFalse(r["auto_promote_gen64_or_gen65"])
        self.assertFalse(r["site_site_worker_replaced"])

    def test_missing_source_directory_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(RuntimeError,"HISTORICAL_ORIGIN_NOT_VERIFIED"):
                m.benchmark(td,run_child=False)


if __name__=="__main__":
    unittest.main()
