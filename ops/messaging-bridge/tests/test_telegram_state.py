import asyncio
import contextlib
import io
import importlib.util
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Load by absolute path: repository-wide pytest does not add this sibling directory
# to sys.path, and a different installed "telegram" package must not be imported.
MODULE_PATH = Path(__file__).resolve().parents[1] / 'telegram.py'
MODULE_SPEC = importlib.util.spec_from_file_location('moj_messaging_telegram', MODULE_PATH)
telegram = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(telegram)


class StateSecurityTests(unittest.TestCase):
    def test_status_needs_no_credentials_or_dependencies(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {'MOJMSG_STATE_DIR': folder}, clear=True):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(asyncio.run(telegram.main('status')), 0)
                self.assertEqual(output.getvalue().strip(), 'NOT_STARTED')

    def test_heartbeat_reports_real_health(self):
        class Client:
            def __init__(self):
                self.connected = False
                self.authorized = False

            def is_connected(self):
                return self.connected

            async def is_user_authorized(self):
                return self.authorized

        async def check(root):
            client = Client()
            task = asyncio.create_task(telegram.heartbeat(root, client, interval=0.02))
            try:
                await asyncio.sleep(0.03)
                self.assertEqual(json.loads((root / 'telegram-status.json').read_text())['status'], 'DISCONNECTED')
                client.connected = True
                await asyncio.sleep(0.03)
                self.assertEqual(json.loads((root / 'telegram-status.json').read_text())['status'], 'LOGIN_REQUIRED')
                client.authorized = True
                await asyncio.sleep(0.03)
                self.assertEqual(json.loads((root / 'telegram-status.json').read_text())['status'], 'CONNECTED')
            finally:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

        with tempfile.TemporaryDirectory() as folder:
            asyncio.run(check(Path(folder)))

    def test_daemon_preserves_login_required_on_cleanup(self):
        class FakeClient:
            def __init__(self, *_args, **_kwargs):
                pass
            async def connect(self):
                pass
            async def is_user_authorized(self):
                return False
            async def disconnect(self):
                pass

        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {'MOJMSG_STATE_DIR': folder, 'TG_API_ID': '123', 'TG_API_HASH': 'test'}, clear=True):
                import sys
                from types import ModuleType
                module = ModuleType('telethon')
                module.TelegramClient = FakeClient
                with patch.dict(sys.modules, {'telethon': module}):
                    self.assertEqual(asyncio.run(telegram.main('daemon')), 3)
                result = json.loads((Path(folder) / 'telegram-status.json').read_text())
                self.assertEqual(result['status'], 'LOGIN_REQUIRED')

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