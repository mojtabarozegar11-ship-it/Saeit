"""Private PICM release can bootstrap from a stopped worker without touching factory."""
import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import picm_private_worker_release as release


def _files(tmp_path):
    root = tmp_path / "private-picm"
    root.mkdir()
    current = root / "worker.py"
    current.write_text("original private worker", encoding="utf-8")
    candidate = root / "worker.py.candidate.123456"
    candidate.write_text("new private worker", encoding="utf-8")
    (root / "worker-token").write_text("X" * 64, encoding="ascii")
    (root / "worker.log").write_text("PICM_QUEUE_EMPTY\n", encoding="ascii")
    (root / "worker.lock").write_text("", encoding="ascii")
    (root / "worker.pid").write_text("999999\n", encoding="ascii")
    return root, current, candidate


def test_stopped_worker_bootstraps_without_signaling_factory(tmp_path):
    root, current, candidate = _files(tmp_path)
    digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
    def validate_candidate(self, module):
        module.picm_resource_ok = lambda: True
        module.direct_cpu_ready = lambda: True

    with patch.multiple(release, ROOT=root, WORKER=current,
                        TOKEN=root / "worker-token", LOG=root / "worker.log",
                        PIDFILE=root / "worker.pid"), \
         patch.object(release.os, "getuid", return_value=1000), \
         patch.object(release, "process_ours", return_value=False), \
         patch.object(release, "stop_worker") as stop, \
         patch.object(release, "start_worker", return_value=31415) as start, \
         patch("importlib.machinery.SourceFileLoader.exec_module", validate_candidate):
        release.release("123456", digest)
    stop.assert_not_called()
    start.assert_called_once()
    assert current.read_bytes() == b"new private worker"
    assert (root / ".release-backups/worker-before-123456.py").read_bytes() == b"original private worker"


def test_bad_candidate_sha_fails_before_any_execution_or_write(tmp_path):
    root, current, candidate = _files(tmp_path)
    with patch.multiple(release, ROOT=root, WORKER=current,
                        TOKEN=root / "worker-token", LOG=root / "worker.log",
                        PIDFILE=root / "worker.pid"), \
         patch.object(release.os, "getuid", return_value=1000), \
         patch.object(release, "process_ours", return_value=False), \
         patch("importlib.machinery.SourceFileLoader.exec_module") as execute:
        with pytest.raises(RuntimeError, match="PICM_CANDIDATE_HASH_MISMATCH"):
            release.release("123456", "0" * 64)
    execute.assert_not_called()
    assert current.read_bytes() == b"original private worker"
    assert candidate.is_file()
