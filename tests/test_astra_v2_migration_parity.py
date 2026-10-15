"""No-DB migration parity protection tests for divergent Saeit branches."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"astra_v2_migration_parity.py"
spec=importlib.util.spec_from_file_location("astra_parity",SCRIPT)
parity=importlib.util.module_from_spec(spec);spec.loader.exec_module(parity)


class MigrationParityTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.base=Path(t.name)
        self.current=self.base/"current"
        self.history=self.base/"history"
        self.current.mkdir();self.history.mkdir()
        for folder in (self.current,self.history):
            (folder/"0039_common.py").write_text("dependencies=[]\n")
        for n in range(40,49):
            (self.history/(f"{n:04d}_historical.py")).write_text(
                f"dependencies=[('core','{n-1:04d}_historical')]\n")

    def test_detect_all_nine_missing_migrations(self):
        data=parity.parity(self.current,self.history)
        self.assertEqual(len(data["missing_current_0040_to_0048"]),9)
        self.assertEqual(data["current_last_migration_number"],39)
        self.assertEqual(data["reference_last_migration_number"],48)
        self.assertTrue(data["common_0039_sha_equal"])
        self.assertFalse(data["automatic_merge_permitted"])
        self.assertFalse(data["production_migration_permitted"])

    def test_complete_parity_never_automatically_activates(self):
        for n in range(40,49):
            p=f"{n:04d}_historical.py"
            (self.current/p).write_bytes((self.history/p).read_bytes())
        data=parity.parity(self.current,self.history)
        self.assertEqual(data["missing_current_0040_to_0048"],[])
        self.assertEqual(data["same_number_divergent_migrations"],[])
        self.assertFalse(data["stage45_cutover_permitted"])

    def test_divergent_0044_detected(self):
        for n in range(40,49):
            p=f"{n:04d}_historical.py"
            (self.current/p).write_bytes((self.history/p).read_bytes())
        (self.current/"0044_historical.py").write_text("operations=[]\n")
        d=parity.parity(self.current,self.history)
        self.assertEqual(d["same_number_divergent_migrations"],[44])

    def test_mismatched_0039_reports_manual_review(self):
        (self.history/"0039_common.py").write_text("dependencies=['other']\n")
        d=parity.parity(self.current,self.history)
        self.assertFalse(d["common_0039_sha_equal"])
        self.assertEqual(d["next_step"],"BLOCKED_REVIEW_MIGRATION_LINEAGE_MANUALLY")

    def test_missing_reference_0048_reports_blocked(self):
        (self.history/"0048_historical.py").unlink()
        d=parity.parity(self.current,self.history)
        self.assertIn(48,d["missing_reference_0040_to_0048"])
        self.assertEqual(d["next_step"],"BLOCKED_REVIEW_MIGRATION_LINEAGE_MANUALLY")

    def test_doubled_number_is_not_accepted(self):
        (self.current/"0039_other.py").write_text("dependencies=[]\n")
        with self.assertRaisesRegex(ValueError,"duplicate"):
            parity.parity(self.current,self.history)

    def test_code_not_executed_during_audit(self):
        target=self.base/"should_not_exist.txt"
        (self.current/"0039_common.py").write_text(
            "from pathlib import Path\nPath("+repr(str(target))+").write_text('BAD')\n")
        parity.parity(self.current,self.history)
        self.assertFalse(target.exists())

    def test_symlink_to_migration_forbidden(self):
        linked=self.current/"0040_link.py"
        linked.symlink_to(self.history/"0040_historical.py")
        with self.assertRaisesRegex(ValueError,"symlink"):
            parity.parity(self.current,self.history)

    def test_invalid_python_fails(self):
        (self.current/"0040_bad.py").write_text("this is not python )(\n")
        with self.assertRaises(SyntaxError):
            parity.parity(self.current,self.history)

if __name__=="__main__":
    unittest.main()
