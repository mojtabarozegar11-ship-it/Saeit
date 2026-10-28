#!/usr/bin/env python3
"""One-route Zomorod Persian author restoration, with exact-byte rollback.

Called only on the verified cPanel account by the guarded GitHub workflow.
Never modifies the site homepage, Django app, or any unrelated redirect.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from xml.etree import ElementTree


HOME = Path("/home/zomorod2")
WEB = HOME / "public_html"
APP = HOME / "Saeit"
HTACCESS = WEB / ".htaccess"
SITEMAP = WEB / "sitemap.xml"
TARGET = WEB / "authors/mojtaba-rozegar/index.html"
APP_TARGET = APP / "public/authors/mojtaba-rozegar/index.html"
URLS = APP / "config/urls.py"
SEO = APP / "core/seo_views.py"
RESTART = APP / "tmp/restart.txt"
PHOTO = WEB / "static/site/zomorod-about/ceo-mojtaba-rozegar.webp"
STAGE_ROOT = HOME / ".private-zm-author-route"
REDIRECT = (
    b"RedirectMatch 301 ^/authors/mojtaba-rozegar/?$ "
    b"https://zomorodmelal.ir/en/authors/mojtaba-rozegar/"
)
OLD_SOURCE_SHA256 = (
    "6fc1f571f9bb27bf314b3d6804d39f029fcaca228f724e40652e13e705fbbd10"
)
CURRENT_SOURCE_SHA256 = (
    "4af0dde1a62dc24b52b899b44d1858d7ca04bced49286008492c35b365f49c19"
)
PASSENGER_ANCHOR = b'PassengerAppRoot "/home/zomorod2/Saeit"'
PROFILE_MARKER = b'id="profile-name"'
PERSIAN_URL = "https://zomorodmelal.ir/authors/mojtaba-rozegar/"
OLD_ROUTE = (
    'path("authors/mojtaba-rozegar/", RedirectView.as_view('
    'url="/en/authors/mojtaba-rozegar/", permanent=True), '
    'name="mojtaba_roozegar_author_profile"),'
)
NEW_ROUTE = (
    'path("authors/mojtaba-rozegar/", persian_author_profile, '
    'name="mojtaba_roozegar_author_profile"),'
)
OLD_IMPORT = 'from core.seo_views import site_search, robots_txt, sitemap_xml'
NEW_IMPORT = OLD_IMPORT + ', persian_author_profile'
OLD_SITEMAP_ITEM = '"/en/authors/mojtaba-rozegar/"]'
NEW_SITEMAP_ITEM = (
    '"/en/authors/mojtaba-rozegar/", "/authors/mojtaba-rozegar/"]'
)
SEO_VIEW_MARKER = "# zm-author-persian-view-20261023"
SEO_VIEW_APPEND = '''

# zm-author-persian-view-20261023: a real 200 HTML response, not a canonical-damaging 301.
@require_GET
def persian_author_profile(request):
    from pathlib import Path
    from django.conf import settings

    page = Path(settings.BASE_DIR) / "public/authors/mojtaba-rozegar/index.html"
    if page.is_symlink() or not page.is_file():
        return HttpResponse(status=404)
    return HttpResponse(page.read_bytes(), content_type="text/html; charset=utf-8")
'''


def with_django_author_route(raw: bytes) -> bytes:
    source = raw.decode("utf-8")
    if NEW_ROUTE in source and NEW_IMPORT in source:
        return raw
    if source.count(OLD_ROUTE) != 1 or source.count(OLD_IMPORT) != 1:
        raise ValueError("PRODUCTION_DJANGO_ROUTE_SOURCE_DRIFT")
    result = source.replace(OLD_IMPORT, NEW_IMPORT, 1)
    result = result.replace(OLD_ROUTE, NEW_ROUTE, 1)
    compile(result, str(URLS), "exec")
    return result.encode("utf-8")


def with_django_author_view_and_sitemap(raw: bytes) -> bytes:
    source = raw.decode("utf-8")
    if NEW_SITEMAP_ITEM in source and SEO_VIEW_MARKER in source:
        return raw
    if source.count(OLD_SITEMAP_ITEM) != 1 or SEO_VIEW_MARKER in source:
        raise ValueError("PRODUCTION_DJANGO_SEO_SOURCE_DRIFT")
    result = source.replace(OLD_SITEMAP_ITEM, NEW_SITEMAP_ITEM, 1)
    result = result + SEO_VIEW_APPEND + "\n"
    compile(result, str(SEO), "exec")
    return result.encode("utf-8")


def digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def without_exact_redirect(blob: bytes) -> bytes:
    """Remove one verified mod_alias rule, keeping every other byte."""
    lines = blob.splitlines(keepends=True)
    matches = [i for i, line in enumerate(lines) if line.rstrip(b"\r\n") == REDIRECT]
    if len(matches) != 1:
        raise ValueError("EXPECTED_ONE_EXISTING_AUTHOR_REDIRECT")
    # The original release prepended this rule. Require identical placement.
    if matches[0] != 0:
        raise ValueError("AUTHOR_REDIRECT_MOVED_FROM_ORIGINAL_POSITION")
    return b"".join(lines[:matches[0]] + lines[matches[0] + 1:])


def verified_author_redirect_state(blob: bytes) -> bytes:
    """Remove the obsolete exact redirect once, or preserve an already-live route."""
    if REDIRECT in blob:
        return without_exact_redirect(blob)
    if b"/authors/mojtaba-rozegar" in blob:
        raise ValueError("UNKNOWN_AUTHOR_REDIRECT_OR_REWRITE")
    return blob


def with_persian_sitemap_entry(blob: bytes) -> bytes:
    """Append one actual, canonical, crawlable author URL without reformatting."""
    root = ElementTree.fromstring(blob)
    if not root.tag.endswith("urlset"):
        raise ValueError("NOT_A_URLSET_SITEMAP")
    urls = [
        (node.text or "").strip()
        for node in root.iter() if node.tag.endswith("loc")
    ]
    if PERSIAN_URL in urls:
        if urls.count(PERSIAN_URL) != 1:
            raise ValueError("DUPLICATE_PERSIAN_AUTHOR_URL")
        return blob
    closings = list(re.finditer(rb"</(?:[\w.-]+:)?urlset\s*>", blob))
    if len(closings) != 1:
        raise ValueError("SITEMAP_CLOSING_TAG_CONFLICT")
    entry = (
        b"<url><loc>" + PERSIAN_URL.encode("ascii")
        + b"</loc><lastmod>2026-10-23</lastmod></url>\n"
    )
    result = blob[:closings[0].start()] + entry + blob[closings[0].start():]
    check = ElementTree.fromstring(result)
    found = [
        (node.text or "").strip()
        for node in check.iter() if node.tag.endswith("loc")
    ]
    if found.count(PERSIAN_URL) != 1:
        raise ValueError("SITEMAP_INSERT_VERIFY_FAILED")
    return result


def safe_paths(run: str) -> Path:
    if not re.fullmatch(r"[0-9]{6,24}", run):
        raise ValueError("INVALID_RUN_ID")
    if Path.home() != HOME:
        raise ValueError("CPANEL_ACCOUNT_MISMATCH")
    stage = STAGE_ROOT / run
    for path in (
        HOME, WEB, APP, HTACCESS, SITEMAP, TARGET.parent, TARGET, PHOTO,
        URLS, SEO, APP_TARGET.parent, APP_TARGET, RESTART,
        STAGE_ROOT, stage,
    ):
        if path.is_symlink():
            raise ValueError("SYMLINK_BLOCKED:" + str(path))
    if not (
        WEB.is_dir() and APP.is_dir()
        and HTACCESS.is_file() and SITEMAP.is_file() and PHOTO.is_file()
        and URLS.is_file() and SEO.is_file() and RESTART.parent.is_dir()
    ):
        raise ValueError("SITE_OR_REAL_PORTRAIT_MISSING")
    if not stage.is_dir():
        raise ValueError("STAGING_DIRECTORY_MISSING")
    return stage


def atomic_write(path: Path, blob: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".author-atomic-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(blob)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.lexists(tmp):
            os.unlink(tmp)


def install(run: str, want: str) -> None:
    stage = safe_paths(run)
    if not re.fullmatch(r"[0-9a-f]{64}", want):
        raise ValueError("INVALID_EXPECTED_SHA")
    candidate = stage / "source.html"
    manifest = stage / "profile-route-manifest.json"
    if not candidate.is_file() or candidate.is_symlink() or manifest.exists():
        raise ValueError("SOURCE_OR_MANIFEST_CONFLICT")
    new_page = candidate.read_bytes()
    if digest(new_page) != want or PROFILE_MARKER not in new_page:
        raise ValueError("CANDIDATE_HASH_OR_IDENTITY_MISMATCH")
    if not new_page.strip().endswith(b"</html>"):
        raise ValueError("CANDIDATE_INCOMPLETE")

    original_ht = HTACCESS.read_bytes()
    original_sitemap = SITEMAP.read_bytes()
    original_urls = URLS.read_bytes()
    original_seo = SEO.read_bytes()
    if PASSENGER_ANCHOR not in original_ht:
        raise ValueError("HOST_APP_MAPPING_DRIFT")
    new_ht = verified_author_redirect_state(original_ht)
    new_sitemap = with_persian_sitemap_entry(original_sitemap)
    new_urls = with_django_author_route(original_urls)
    new_seo = with_django_author_view_and_sitemap(original_seo)
    existing_page = TARGET.read_bytes() if TARGET.is_file() else None
    existing_app_page = APP_TARGET.read_bytes() if APP_TARGET.is_file() else None
    if TARGET.exists() and existing_page is None:
        raise ValueError("AUTHOR_DEST_NOT_A_REGULAR_FILE")
    if existing_page is not None and digest(existing_page) not in (want, OLD_SOURCE_SHA256, CURRENT_SOURCE_SHA256):
        raise ValueError("AUTHOR_DEST_UNKNOWN_CONTENT")
    if APP_TARGET.exists() and existing_app_page is None:
        raise ValueError("DJANGO_AUTHOR_DEST_NOT_A_REGULAR_FILE")
    if existing_app_page is not None and digest(existing_app_page) not in (want, OLD_SOURCE_SHA256, CURRENT_SOURCE_SHA256):
        raise ValueError("DJANGO_AUTHOR_DEST_UNKNOWN_CONTENT")
    if digest(HTACCESS.read_bytes()) != digest(original_ht):
        raise ValueError("CONCURRENT_HTACCESS_CHANGE")

    atomic_write(stage / "htaccess.before", original_ht, 0o600)
    atomic_write(stage / "sitemap.before", original_sitemap, 0o600)
    atomic_write(stage / "urls.before", original_urls, 0o600)
    atomic_write(stage / "seo.before", original_seo, 0o600)
    if existing_page is not None:
        atomic_write(stage / "profile.before", existing_page, 0o600)
    if existing_app_page is not None:
        atomic_write(stage / "django-profile.before", existing_app_page, 0o600)
    record = {
        "run": run, "had_page": existing_page is not None,
        "had_app_page": existing_app_page is not None,
        "ht_before": digest(original_ht), "ht_after": digest(new_ht),
        "sitemap_before": digest(original_sitemap),
        "sitemap_after": digest(new_sitemap),
        "urls_before": digest(original_urls), "urls_after": digest(new_urls),
        "seo_before": digest(original_seo), "seo_after": digest(new_seo),
        "page_before": digest(existing_page) if existing_page is not None else None,
        "app_page_before": digest(existing_app_page) if existing_app_page is not None else None,
        "page_after": want,
    }
    atomic_write(
        manifest, json.dumps(record, sort_keys=True).encode("ascii"), 0o600
    )
    try:
        if (existing_page is None or digest(existing_page) != want):
            atomic_write(TARGET, new_page, 0o644)
        if digest(TARGET.read_bytes()) != want:
            raise ValueError("PROFILE_WRITE_FAILED")
        if existing_app_page is None or digest(existing_app_page) != want:
            atomic_write(APP_TARGET, new_page, 0o644)
        if digest(APP_TARGET.read_bytes()) != want:
            raise ValueError("DJANGO_PROFILE_WRITE_FAILED")
        if digest(URLS.read_bytes()) != digest(original_urls) or digest(SEO.read_bytes()) != digest(original_seo):
            raise ValueError("CONCURRENT_DJANGO_SOURCE_CHANGE")
        atomic_write(SEO, new_seo, SEO.stat().st_mode & 0o777)
        atomic_write(URLS, new_urls, URLS.stat().st_mode & 0o777)
        if digest(URLS.read_bytes()) != digest(new_urls) or digest(SEO.read_bytes()) != digest(new_seo):
            raise ValueError("DJANGO_ROUTE_WRITE_FAILED")
        if digest(SITEMAP.read_bytes()) != digest(original_sitemap):
            raise ValueError("CONCURRENT_SITEMAP_CHANGE_BEFORE_COMMIT")
        if new_sitemap != original_sitemap:
            atomic_write(SITEMAP, new_sitemap, SITEMAP.stat().st_mode & 0o777)
        if digest(SITEMAP.read_bytes()) != digest(new_sitemap):
            raise ValueError("SITEMAP_WRITE_FAILED")
        if digest(HTACCESS.read_bytes()) != digest(original_ht):
            raise ValueError("CONCURRENT_HTACCESS_CHANGE_BEFORE_COMMIT")
        atomic_write(HTACCESS, new_ht, HTACCESS.stat().st_mode & 0o777)
        if digest(HTACCESS.read_bytes()) != digest(new_ht):
            raise ValueError("REDIRECT_REMOVAL_FAILED")
        RESTART.touch()
        print("ZM_PERSIAN_AUTHOR_CONTENT_AND_REDIRECT_FIXED=PASS")
        print("ZM_PERSIAN_AUTHOR_ROLLBACK_MANIFEST=" + str(manifest))
    except Exception:
        rollback(run)
        raise


def rollback(run: str) -> None:
    stage = safe_paths(run)
    manifest = stage / "profile-route-manifest.json"
    if not manifest.is_file() or manifest.is_symlink():
        raise ValueError("ROLLBACK_MANIFEST_MISSING")
    record = json.loads(manifest.read_text(encoding="ascii"))
    if record["run"] != run:
        raise ValueError("ROLLBACK_RUN_MISMATCH")
    saved_ht = (stage / "htaccess.before").read_bytes()
    saved_sitemap = (stage / "sitemap.before").read_bytes()
    saved_urls = (stage / "urls.before").read_bytes()
    saved_seo = (stage / "seo.before").read_bytes()
    if digest(saved_ht) != record["ht_before"]:
        raise ValueError("ROLLBACK_BACKUP_MISMATCH")
    if digest(saved_sitemap) != record["sitemap_before"]:
        raise ValueError("ROLLBACK_SITEMAP_BACKUP_MISMATCH")
    if digest(saved_urls) != record["urls_before"] or digest(saved_seo) != record["seo_before"]:
        raise ValueError("ROLLBACK_DJANGO_BACKUP_MISMATCH")
    current_ht = HTACCESS.read_bytes()
    current_sitemap = SITEMAP.read_bytes()
    current_urls = URLS.read_bytes()
    current_seo = SEO.read_bytes()
    if digest(current_ht) not in (record["ht_before"], record["ht_after"]):
        raise ValueError("ROLLBACK_CONCURRENT_HTACCESS_CHANGE")
    if digest(current_sitemap) not in (record["sitemap_before"], record["sitemap_after"]):
        raise ValueError("ROLLBACK_CONCURRENT_SITEMAP_CHANGE")
    if digest(current_urls) not in (record["urls_before"], record["urls_after"]):
        raise ValueError("ROLLBACK_CONCURRENT_URLS_CHANGE")
    if digest(current_seo) not in (record["seo_before"], record["seo_after"]):
        raise ValueError("ROLLBACK_CONCURRENT_SEO_CHANGE")
    if TARGET.is_symlink():
        raise ValueError("ROLLBACK_PROFILE_SYMLINK")
    current_page = TARGET.read_bytes() if TARGET.is_file() else None
    if current_page is None and record["had_page"]:
        raise ValueError("ROLLBACK_ORIGINAL_PROFILE_MISSING")
    if current_page is not None and digest(current_page) not in (
        record["page_after"], record["page_before"]
    ):
        raise ValueError("ROLLBACK_CONCURRENT_PROFILE_CHANGE")
    if APP_TARGET.is_symlink():
        raise ValueError("ROLLBACK_DJANGO_PROFILE_SYMLINK")
    current_app_page = APP_TARGET.read_bytes() if APP_TARGET.is_file() else None
    if current_app_page is None and record["had_app_page"]:
        raise ValueError("ROLLBACK_ORIGINAL_DJANGO_PROFILE_MISSING")
    if current_app_page is not None and digest(current_app_page) not in (
        record["page_after"], record["app_page_before"]
    ):
        raise ValueError("ROLLBACK_CONCURRENT_DJANGO_PROFILE_CHANGE")
    if record["had_page"]:
        saved_page = (stage / "profile.before").read_bytes()
        if digest(saved_page) != record["page_before"]:
            raise ValueError("ROLLBACK_PROFILE_BACKUP_MISMATCH")
        if digest(current_page) != record["page_before"]:
            atomic_write(TARGET, saved_page, 0o644)
    elif current_page is not None and digest(current_page) == record["page_after"]:
        TARGET.unlink()
    if record["had_app_page"]:
        saved_app_page = (stage / "django-profile.before").read_bytes()
        if digest(saved_app_page) != record["app_page_before"]:
            raise ValueError("ROLLBACK_DJANGO_PROFILE_BACKUP_MISMATCH")
        if digest(current_app_page) != record["app_page_before"]:
            atomic_write(APP_TARGET, saved_app_page, 0o644)
    elif current_app_page is not None and digest(current_app_page) == record["page_after"]:
        APP_TARGET.unlink()
    if digest(current_urls) != record["urls_before"]:
        atomic_write(URLS, saved_urls, URLS.stat().st_mode & 0o777)
    if digest(current_seo) != record["seo_before"]:
        atomic_write(SEO, saved_seo, SEO.stat().st_mode & 0o777)
    if digest(current_sitemap) != record["sitemap_before"]:
        atomic_write(SITEMAP, saved_sitemap, SITEMAP.stat().st_mode & 0o777)
    if digest(current_ht) != record["ht_before"]:
        atomic_write(HTACCESS, saved_ht, HTACCESS.stat().st_mode & 0o777)
    if HTACCESS.read_bytes() != saved_ht:
        raise ValueError("ROLLBACK_HTACCESS_VERIFY_FAILED")
    if SITEMAP.read_bytes() != saved_sitemap:
        raise ValueError("ROLLBACK_SITEMAP_VERIFY_FAILED")
    if URLS.read_bytes() != saved_urls or SEO.read_bytes() != saved_seo:
        raise ValueError("ROLLBACK_DJANGO_SOURCE_VERIFY_FAILED")
    RESTART.touch()
    print("ZM_PERSIAN_AUTHOR_SCOPE_ROLLBACK=PASS")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "install":
        install(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3 and sys.argv[1] == "rollback":
        rollback(sys.argv[2])
    else:
        raise SystemExit("Usage: release.py install RUN_ID SHA | rollback RUN_ID")
