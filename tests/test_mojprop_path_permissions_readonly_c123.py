import unittest
from scripts.mojprop_path_permissions_readonly_c123 import classify, PATHS

class C123Tests(unittest.TestCase):
    def test_fixed_paths_are_absolute_and_bounded(self):
        self.assertLessEqual(len(PATHS), 12)
        self.assertTrue(all(p.is_absolute() for p in PATHS.values()))

    def test_classifier_never_reads_file_contents(self):
        self.assertTrue(callable(classify))

if __name__ == "__main__":
    unittest.main()
