import tempfile
import unittest
from pathlib import Path
from scripts.mojplaywin_backup_vps_failure_readonly import inspect


class VpsBackupFailureReadonlyTests(unittest.TestCase):
    def test_absent_files_cannot_be_called_verified(self):
        with tempfile.TemporaryDirectory() as td:
            r = inspect(Path(td))
            self.assertFalse(r["mysql_complete"]["exists"])
            self.assertFalse(r["files_complete"]["exists"])
            self.assertFalse(r["isolated_restore_verified"])
            self.assertFalse(r["release_permitted"])
            self.assertNotIn(td, str(r))


if __name__ == "__main__":
    unittest.main()
