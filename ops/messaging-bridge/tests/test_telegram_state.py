import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import telegram


class StateSecurityTests(unittest.TestCase):
    def test_private_dir_atomic_status_without_messages(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'secret-state'
            with patch.dict(os.environ, {'MOJMSG_STATE_DIR': str(root)}):
                self.assertEqual(telegram.state_root(), root)
                telegram.status_write(root, 'CONNECTED')
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
            status_file = root / 'telegram-status.json'
            self.assertEqual(stat.S_IMODE(status_file.stat().st_mode), 0o600)
            status = json.loads(status_file.read_text())
            self.assertEqual(status['service'], 'telegram')
            self.assertEqual(status['status'], 'CONNECTED')
            self.assertEqual(set(status.keys()), {'service', 'status', 'timestamp'})


if __name__ == '__main__':
    unittest.main()