"""Source backup must preserve bytes and never log user content or names."""

import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "mojplaywin_backup_stream_cpanel.py"
SPEC = importlib.util.spec_from_file_location("mojplaywin_backup_stream_cpanel", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeProcess:
    def __init__(self, content, code=0):
        self.stdout = io.BytesIO(content)
        self.code = code

    def wait(self, timeout=None):
        return self.code

    def poll(self):
        return self.code


class BackupStreamTelemetryTests(TestCase):
    def _stream(self, content, code=0):
        dest = io.BytesIO()
        log = io.StringIO()
        process = FakeProcess(content, code)
        with (
            mock.patch.object(MODULE.subprocess, "Popen", return_value=process),
            mock.patch.object(MODULE.sys, "stdout", SimpleNamespace(buffer=dest)),
            mock.patch.object(MODULE.sys, "stderr", log),
        ):
            if code:
                with self.assertRaises(RuntimeError):
                    MODULE.copy_exact_process_stdout(["synthetic-only"])
            else:
                MODULE.copy_exact_process_stdout(["synthetic-only"])
        return dest.getvalue(), log.getvalue()

    def test_progress_never_contaminates_exact_backup_bytes(self):
        source = b"private-test-fixture-DO-NOT-LOG"
        stream, log = self._stream(source)
        self.assertEqual(stream, source + MODULE.MARKER)
        self.assertIn("BACKUP_SOURCE_STREAM_STARTED", log)
        self.assertIn("BACKUP_SOURCE_STREAM_COMPLETED", log)
        self.assertNotIn(source.decode("ascii"), log)

    def test_failure_never_appends_success_footer(self):
        source = b"private-test-fixture-DO-NOT-LOG"
        stream, log = self._stream(source, code=1)
        self.assertEqual(stream, source)
        self.assertNotIn("BACKUP_SOURCE_STREAM_COMPLETED", log)
        self.assertNotIn(source.decode("ascii"), log)
