"""No production access; source transformation and safety regressions."""
import hashlib, unittest
from scripts.mpw_store_source_repair_20261107 import OLD, NEW, transformed

class LiveStoreRepairTests(unittest.TestCase):
    def test_exact_one_function_patch_and_preservation(self):
        original = ("# retained\n"+OLD+"\n# other code remains\n").encode()
        data = transformed(original, expected_size=len(original), expected_prefix=hashlib.sha256(original).hexdigest())
        self.assertIn(NEW.encode(), data)
        self.assertIn(b"# other code remains", data)
        self.assertNotIn(OLD.encode(), data)
        compile(data, "synthetic-mpw-store", "exec")

    def test_refuse_modified_or_ambiguous_source(self):
        original = (OLD+"\n"+OLD).encode()
        with self.assertRaisesRegex(RuntimeError, "AMBIGUOUS"):
            transformed(original, expected_size=len(original), expected_prefix=hashlib.sha256(original).hexdigest())
        with self.assertRaisesRegex(RuntimeError, "DRIFT"):
            transformed(b"other", expected_size=5, expected_prefix="0000000000000000")

if __name__ == "__main__":
    unittest.main()
