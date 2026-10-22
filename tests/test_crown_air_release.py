import hashlib
import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def release(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("crown_air_release", "scripts/mpw_crown_air_publish.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    home = tmp_path / "host"
    game = home / "mojplaywin.com/design-preview-20261017/mpw-crown-defender-20261019/index.html"
    game.parent.mkdir(parents=True)
    old = b"previous verified game"
    game.write_bytes(old)
    neighbor = game.parent / "protected.txt"
    neighbor.write_bytes(b"leave unchanged")
    run = "123456789012"
    (home / (".mpw-crown-game-stage-" + run + ".html")).write_bytes(Path("games/crown-defender/index.html").read_bytes())
    stage = home / (".mpw-crown-air-assets-stage-" + run)
    stage.mkdir()
    for p in Path("games/crown-defender/assets/air-supremacy").glob("*.webp"):
        (stage / p.name).write_bytes(p.read_bytes())
    monkeypatch.setattr(mod, "HOME", home)
    monkeypatch.setattr(mod, "GAME", game)
    monkeypatch.setattr(mod, "BACKUPS", home / ".private-backups")
    monkeypatch.setattr(mod, "ASSET_DIR", home / "mojplaywin.com/mpw-crown-air-assets-20261022")
    monkeypatch.setattr(mod, "PREVIOUS_SHA", hashlib.sha256(old).hexdigest())
    return mod, run, game, old, neighbor, stage


def test_install_verify_and_rollback_preserve_neighbor(release):
    mod, run, game, old, neighbor, _ = release
    digest = mod.digest(Path("games/crown-defender/index.html").read_bytes())
    mod.install(run, digest)
    mod.status(run)
    assert mod.digest(game.read_bytes()) == digest
    assert len(list(mod.ASSET_DIR.iterdir())) == 9
    assert neighbor.read_bytes() == b"leave unchanged"
    mod.rollback(run)
    assert game.read_bytes() == old
    assert not mod.ASSET_DIR.exists()
    assert neighbor.read_bytes() == b"leave unchanged"


def test_corrupt_asset_aborts_before_any_public_write(release):
    mod, run, game, old, _, stage = release
    (stage / "falcon.webp").write_bytes(b"corrupted")
    with pytest.raises(RuntimeError, match="Asset hash mismatch"):
        mod.install(run, mod.digest(Path("games/crown-defender/index.html").read_bytes()))
    assert game.read_bytes() == old
    assert not mod.ASSET_DIR.exists()


def test_concurrent_game_change_blocks_install(release):
    mod, run, game, _, _, _ = release
    game.write_bytes(b"another approved release")
    with pytest.raises(RuntimeError, match="Unexpected live"):
        mod.install(run, mod.digest(Path("games/crown-defender/index.html").read_bytes()))
    assert game.read_bytes() == b"another approved release"
    assert not mod.ASSET_DIR.exists()
