"""No-network proof that PICM cPanel release only changes three pinned private files."""
import hashlib
from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest

from scripts import picm_private_capacity_release as release


def _sha(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def workspace():
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        app = home / "Saeit-staging"
        app.mkdir()
        site = home / "mojplaywin.com"
        site.mkdir()
        back = home / ".mojplaywin-backups"
        run = "12345678"
        stage = home / (".picm-independent-stage-" + run)
        base = []
        new = []
        before = {}
        for index, name in enumerate(release.FILES):
            target = app / name
            target.parent.mkdir(parents=True, exist_ok=True)
            old = ("original-private-picm-%d-" % index).encode() * 110
            changed = ("updated-private-picm-%d-" % index).encode() * 110
            target.write_bytes(old)
            before[name] = old
            base.append(release.blob(old))
            new.append(changed)
            candidate = stage / name
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_bytes(changed)
        unrelated = app / "core/unrelated.py"
        unrelated.write_text("unchanged")
        with patch.multiple(release, HOME=home, APP=app, SITE=site,
                            BACKUPS=back, BASE_BLOBS=tuple(base)), \
             patch.object(release, "guard"), \
             patch.object(release, "restart") as restart:
            yield app, stage, before, new, unrelated, restart, run


def test_scoped_deploy_and_rollback_preserve_other_files(workspace):
    app, stage, before, new, unrelated, restart, run = workspace
    release.deploy(run, [_sha(raw) for raw in new])
    assert [(app / name).read_bytes() for name in release.FILES] == new
    assert unrelated.read_text() == "unchanged"
    release.restore(run)
    assert [(app / name).read_bytes() for name in release.FILES] == [before[n] for n in release.FILES]
    assert unrelated.read_text() == "unchanged"
    assert restart.call_count == 2


def test_changed_live_file_blocks_all_writes(workspace):
    app, stage, before, new, unrelated, restart, run = workspace
    changed = app / release.FILES[1]
    changed.write_text("concurrent change")
    with pytest.raises(RuntimeError, match="PICM_LIVE_FILE_SHA_MISMATCH_REFUSE"):
        release.deploy(run, [_sha(raw) for raw in new])
    assert (app / release.FILES[0]).read_bytes() == before[release.FILES[0]]
    assert unrelated.read_text() == "unchanged"
    restart.assert_not_called()


def test_bad_candidate_sha_blocks_all_writes(workspace):
    app, stage, before, new, unrelated, restart, run = workspace
    hashes = [_sha(raw) for raw in new]
    hashes[2] = "0" * 64
    with pytest.raises(RuntimeError, match="PICM_CANDIDATE_INTEGRITY_FAILURE"):
        release.deploy(run, hashes)
    assert (app / release.FILES[0]).read_bytes() == before[release.FILES[0]]
    restart.assert_not_called()
