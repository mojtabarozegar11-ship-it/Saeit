"""Safely publish exactly one canonical game file; never overwrite drift."""
import hashlib
from pathlib import Path

import pytest

from scripts import mpw_crown_canonical_safe_publish as publish


@pytest.fixture
def release(tmp_path, monkeypatch):
    home = tmp_path / "owner"
    game = home / "mojplaywin.com/design-preview-20261017/mpw-crown-defender-20261019"
    game.mkdir(parents=True)
    target = game / "index.html"
    old = b"<title>Air Supremacy</title><p>100 / 100</p>store\\/product\\/\n"
    new = old.replace(b"store\\/product\\/", b"store\\/crown\\/")
    target.write_bytes(old)
    run = "1234567890"
    stage = home / (".mpw-crown-canonical-stage-" + run)
    stage.mkdir()
    (stage / "index.html").write_bytes(new)
    monkeypatch.setattr(publish, "HOME", home)
    monkeypatch.setattr(publish, "GAME", game)
    monkeypatch.setattr(publish, "TARGET", target)
    monkeypatch.setattr(publish, "RECEIPTS", home / ".mpw-crown-canonical-receipts")
    sha = lambda b: hashlib.sha256(b).hexdigest()
    return run, target, old, new, sha(old), sha(new)


def test_publish_status_and_recover_exact_backup(release):
    run, target, old, new, old_hash, new_hash = release
    publish.install(run, old_hash, new_hash)
    assert target.read_bytes() == new
    publish.status(run, old_hash, new_hash)
    receipt = publish.RECEIPTS / ("release-" + run)
    assert (receipt / "original.html").read_bytes() == old
    publish.rollback(run, old_hash, new_hash)
    assert target.read_bytes() == old
    publish.rollback(run, old_hash, new_hash)


def test_reject_unrecognized_existing_game_without_overwrite(release):
    run, target, old, new, old_hash, new_hash = release
    target.write_bytes(b"someone else's more recent game")
    with pytest.raises(RuntimeError, match="expected|differ"):
        publish.install(run, old_hash, new_hash)
    assert target.read_bytes() == b"someone else's more recent game"


def test_reject_changed_staging_bytes(release):
    run, target, old, new, old_hash, new_hash = release
    stage = publish.HOME / (".mpw-crown-canonical-stage-" + run)
    (stage / "index.html").write_bytes(b"unverified payload")
    with pytest.raises(RuntimeError):
        publish.install(run, old_hash, new_hash)
    assert target.read_bytes() == old


def test_rollback_refuses_changed_canonical(release):
    run, target, old, new, old_hash, new_hash = release
    publish.install(run, old_hash, new_hash)
    target.write_bytes(b"another author changed the canonical page")
    with pytest.raises(RuntimeError, match="changed after install"):
        publish.rollback(run, old_hash, new_hash)
    assert target.read_bytes() == b"another author changed the canonical page"


def test_target_symlink_is_forbidden(release):
    run, target, old, new, old_hash, new_hash = release
    actual = target.parent / "real-index.html"
    actual.write_bytes(old)
    target.unlink()
    target.symlink_to(actual)
    with pytest.raises(RuntimeError, match="symlink"):
        publish.install(run, old_hash, new_hash)
    assert actual.read_bytes() == old
