from pathlib import Path

import pytest

from scripts.deploy_mojplaywin_studio_raha import PUBLIC_HTACCESS, verify_public_route


OWNED_HTML = (
    '<!doctype html><html><head><title>Studio Raham — Play, Learn & Create</title>'
    '<link rel="canonical" href="https://mojplaywin.com/studio.Roham/">'
    '<meta name="studio-raha-catalog" content="20 games, 20 digital products">'
    '</head><body>Games</body></html>'
)


def test_missing_route_is_safe_to_install(tmp_path):
    verify_public_route(tmp_path / "studio.Roham")


def test_owned_regular_route_is_safe_to_upgrade(tmp_path):
    route = tmp_path / "studio.Roham"
    route.mkdir()
    (route / "index.html").write_text(OWNED_HTML, encoding="utf-8")
    (route / ".htaccess").write_text(PUBLIC_HTACCESS, encoding="utf-8")
    verify_public_route(route)


@pytest.mark.parametrize("tamper", ["wrong-index", "wrong-htaccess", "missing-htaccess"])
def test_unknown_or_incomplete_route_is_rejected(tmp_path, tamper):
    route = tmp_path / "studio.Roham"
    route.mkdir()
    (route / "index.html").write_text(
        "<h1>Other site</h1>" if tamper == "wrong-index" else OWNED_HTML,
        encoding="utf-8",
    )
    if tamper != "missing-htaccess":
        (route / ".htaccess").write_text(
            "Options +Indexes\n" if tamper == "wrong-htaccess" else PUBLIC_HTACCESS,
            encoding="utf-8",
        )
    with pytest.raises(RuntimeError):
        verify_public_route(route)


def test_symlinked_route_is_rejected(tmp_path):
    actual = tmp_path / "unrelated"
    actual.mkdir()
    route = tmp_path / "studio.Roham"
    route.symlink_to(actual, target_is_directory=True)
    with pytest.raises(RuntimeError):
        verify_public_route(route)
