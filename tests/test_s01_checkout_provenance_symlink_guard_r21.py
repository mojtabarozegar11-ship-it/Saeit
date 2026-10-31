"""S-01 checkout provenance: pure local no-host source path safety checks."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/s01_checkout_cpanel_provenance_readonly_20261030.py"
SPEC = importlib.util.spec_from_file_location("s01_checkout_provenance_guard", SCRIPT)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class CheckoutProvenanceReadOnlyGuardTests(unittest.TestCase):
    def test_regular_owned_source_is_readable(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            file = root / "source.py"
            file.write_bytes(b"safe fixture")
            self.assertEqual(probe.regular_bytes(file, os.getuid()), b"safe fixture")

    def test_intermediate_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            real = root / "real"
            real.mkdir()
            (real / "source.py").write_bytes(b"should not follow")
            (root / "linked").symlink_to(real, target_is_directory=True)
            self.assertIsNone(probe.regular_bytes(root / "linked/source.py", os.getuid()))

    def test_owner_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            file = Path(d) / "source.py"
            file.write_bytes(b"safe fixture")
            self.assertIsNone(probe.regular_bytes(file, os.getuid() + 1))

    def test_private_file_requires_exact_0600(self):
        with tempfile.TemporaryDirectory() as d:
            file = Path(d) / "private.bak"
            file.write_bytes(b"safe fixture")
            file.chmod(0o640)
            self.assertIsNone(probe.regular_bytes(file, os.getuid(), private=True))
            file.chmod(0o600)
            self.assertEqual(probe.regular_bytes(file, os.getuid(), private=True), b"safe fixture")

    def test_hardlinked_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            file = root / "source.py"
            file.write_bytes(b"safe fixture")
            os.link(file, root / "hardlink.py")
            self.assertIsNone(probe.regular_bytes(file, os.getuid()))


if __name__ == "__main__":
    unittest.main()
