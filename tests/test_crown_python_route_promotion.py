"""Offline irreversible-mutation guards for Crown's scoped cPanel route promotion."""
from pathlib import Path
import hashlib
import pytest

from scripts import mpw_crown_python_route_safe_publish as release


def sha(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def mock_release(tmp_path, monkeypatch):
    src = tmp_path / "Saeit"
    stage = tmp_path / "Saeit-staging"
    for root in (src, stage):
        (root / "core").mkdir(parents=True)
        (root / "config").mkdir()
    old_fleet = b"STAGE_FLEET = 1\n"
    old_urls = b"from django.urls import path\nurlpatterns = []\n"
    source = {
        "core/crown_checkout.py": b"CHECKOUT = 2\n",
        "core/crown_fleet.py": b"FLEET = 2\n",
        "core/crown_tron_receipts.py": b"RECEIPTS = 2\n",
    }
    for name, payload in source.items():
        (src / name).write_bytes(payload)
    (stage / "core/crown_fleet.py").write_bytes(old_fleet)
    (stage / "config/urls.py").write_bytes(old_urls)
    monkeypatch.setattr(release, "SOURCE", src)
    monkeypatch.setattr(release, "STAGE", stage)
    monkeypatch.setattr(release, "BACKUPS", tmp_path / "private")
    monkeypatch.setattr(release, "LOCKFILE", tmp_path / "lockfile")
    monkeypatch.setattr(release, "OLD_STAGE", {
        "core/crown_fleet.py": sha(old_fleet),
        "config/urls.py": sha(old_urls),
    })
    monkeypatch.setattr(release, "PROMOTED", {name: sha(value) for name, value in source.items()})
    return src, stage, old_fleet, old_urls, source


def test_exact_install_status_rollback_and_idempotency(mock_release):
    _, stage, old_fleet, old_urls, source = mock_release
    release.install("12345678")
    release.state("12345678")
    for name, payload in source.items():
        assert (stage / name).read_bytes() == payload
    urls = (stage / "config/urls.py").read_text()
    assert urls.count("crown_cosmetic_checkout") == 3
    assert "store/crown/<int:product_id>/checkout/" in urls
    assert (stage / "tmp/restart.txt").exists()
    with pytest.raises(RuntimeError, match="already used"):
        release.install("12345678")
    release.rollback("12345678")
    assert (stage / "core/crown_fleet.py").read_bytes() == old_fleet
    assert (stage / "config/urls.py").read_bytes() == old_urls
    assert not (stage / "core/crown_checkout.py").exists()
    assert not (stage / "core/crown_tron_receipts.py").exists()


def test_changed_staging_aborts_without_writing(mock_release):
    _, stage, _, _, _ = mock_release
    (stage / "core/crown_fleet.py").write_text("SOMEONE_ELSE = 1\n")
    with pytest.raises(RuntimeError, match="Staging file changed"):
        release.install("12345679")
    assert not (stage / "core/crown_checkout.py").exists()
    assert not (stage / "core/crown_tron_receipts.py").exists()


def test_changed_promoted_module_cannot_be_overwritten_by_rollback(mock_release):
    _, stage, _, _, _ = mock_release
    release.install("12345680")
    (stage / "core/crown_fleet.py").write_text("IMPORTANT_USER_EDIT = 1\n")
    with pytest.raises(RuntimeError, match="Refusing to overwrite"):
        release.rollback("12345680")
    assert (stage / "core/crown_fleet.py").read_text() == "IMPORTANT_USER_EDIT = 1\n"


def test_unexpected_extra_existing_checkout_refuses_promotion(mock_release):
    _, stage, _, _, _ = mock_release
    (stage / "core/crown_checkout.py").write_text("EXISTING = 1\n")
    with pytest.raises(RuntimeError, match="Expected new module absent"):
        release.install("12345681")
    assert (stage / "core/crown_checkout.py").read_text() == "EXISTING = 1\n"


def test_symlink_target_refuses_promotion(mock_release):
    src, stage, _, _, _ = mock_release
    (stage / "core/crown_checkout.py").symlink_to(src / "core/crown_checkout.py")
    with pytest.raises(RuntimeError, match="Unsafe symlink"):
        release.install("12345682")
