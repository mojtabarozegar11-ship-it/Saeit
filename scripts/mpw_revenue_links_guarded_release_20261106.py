#!/usr/bin/env python3
"""One-file, fail-closed MojPlayWin revenue-hub navigation repair.

Adds direct entry points to twelve already deployed, working browser utilities.
Does not alter checkout, payment, inquiry forms, email, or buyer data.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import pwd
import re
import stat
import sys
import tempfile


OWNER = "zomorod2"
ROOT = Path("/home/zomorod2/mojplaywin.com/mpw-editorial/revenue")
TARGET = ROOT / "index.html"
BACKUPS = Path("/home/zomorod2/.local/share/mpw-revenue-links-backups")
EXPECTED_SHA256 = "6d588b04f1f39f520ad01a9e3220ed9bd826cbe04d110e95218fe42069f359c9"
SLUGS = (
    "website-doctor", "landing-page-studio", "ai-automation",
    "business-spreadsheets", "website-templates", "social-media-kits",
    "resume-builder", "logo-studio", "browser-games", "marketing-ai",
    "business-calculators", "website-care",
)
CARD = re.compile(
    r'(<article class="card">(?:(?!</article>).)*?'
    r'<a href="/mpw-editorial/revenue/(?P<slug>[a-z-]+)/index\.html"'
    r'[^>]*>Details, terms &amp; next steps →</a>)(</article>)', re.S,
)
SUMMARY = (
    "Free tools create draft outputs locally in your browser. "
    "Bespoke services require a written quotation; no payment is collected on these pages."
)
SUMMARY_LINK = (
    '<p class="mpw-free-tool-entry"><a '
    'href="/mpw-editorial/revenue/website-doctor/index.html#mpw-functional-tool">'
    'Open a free browser tool now →</a></p>'
)


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def transform(source: bytes) -> bytes:
    """Require the current twelve-card layout; never overwrite unknown content."""
    html = source.decode("utf-8", "strict")
    if (len(source) > 250_000 or "12 working free browser utilities" not in html
            or html.count(SUMMARY) != 1 or "mpw-free-tool-entry" in html
            or "mpw-direct-free-tool" in html):
        raise RuntimeError("Unknown or already modified revenue hub")
    found = []

    def add_link(match: re.Match[str]) -> str:
        slug = match.group("slug")
        if slug not in SLUGS or slug in found:
            raise RuntimeError("Unexpected or duplicate service card")
        found.append(slug)
        tool = (
            '<p class="mpw-direct-free-tool"><a '
            f'href="/mpw-editorial/revenue/{slug}/index.html#mpw-functional-tool" '
            f'aria-label="Open free {slug.replace("-", " ")} browser tool">'
            'Try the free browser tool →</a></p>'
        )
        return match.group(1) + tool + match.group(3)

    changed = CARD.sub(add_link, html)
    if len(found) != len(SLUGS) or set(found) != set(SLUGS):
        raise RuntimeError(f"Expected exactly twelve cards; found {found}")
    changed = changed.replace(SUMMARY, SUMMARY + SUMMARY_LINK)
    if (changed.count('class="mpw-direct-free-tool"') != 12
            or changed.count('id="offers"') != 1
            or changed.count('href="/mpw-editorial/revenue/website-doctor/index.html#mpw-functional-tool"') != 2):
        raise RuntimeError("Post-transform invariant failed")
    return changed.encode("utf-8")


def owner_guard() -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != OWNER:
        raise RuntimeError("Wrong hosting user")
    if ROOT.is_symlink() or ROOT.resolve() != ROOT or not ROOT.is_dir():
        raise RuntimeError("Unexpected site directory")
    if TARGET.is_symlink():
        raise RuntimeError("Symlinked target")
    info = TARGET.stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) & 0o022):
        raise RuntimeError("Unexpected index ownership or permissions")
    if BACKUPS.is_symlink() or BACKUPS.parent.is_symlink():
        raise RuntimeError("Unsafe backup location")


def atomic_write(path: Path, data: bytes, mode: int = 0o644) -> None:
    fd, name = tempfile.mkstemp(prefix=".mpw-revenue-links-", dir=str(path.parent))
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
        dfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def paths(run_id: str) -> tuple[Path, Path]:
    if not re.fullmatch(r"[0-9]{8,20}", run_id):
        raise RuntimeError("Invalid release identifier")
    return BACKUPS / f"{run_id}.original", BACKUPS / f"{run_id}.published.sha256"


def run(operation: str, run_id: str = "") -> None:
    if operation == "selftest":
        fixture = (
            '<section id="offers"><h2>12 working free browser utilities</h2>'
            f'<p>{SUMMARY}</p>' + "".join(
                f'<article class="card"><a href="/mpw-editorial/revenue/{slug}/index.html" '
                f'aria-label="Details for {slug}">Details, terms &amp; next steps →</a></article>'
                for slug in SLUGS
            ) + '</section>'
        ).encode()
        result = transform(fixture)
        assert result.count(b'mpw-direct-free-tool') == 12
        try:
            transform(result)
        except RuntimeError:
            pass
        else:
            raise AssertionError("Must reject repeat installation")
        print("MPW_DIRECT_TOOL_LINKS_SELFTEST=PASS")
        return

    owner_guard()
    old = TARGET.read_bytes()
    if operation in ("preflight", "publish") and digest(old) != EXPECTED_SHA256:
        raise RuntimeError("Live revenue-hub version differs from independently observed source")
    if operation == "preflight":
        new = transform(old)
        print(f"MPW_DIRECT_TOOL_LINKS_PREFLIGHT=PASS old_sha256={digest(old)} new_sha256={digest(new)}")
        return
    backup, marker = paths(run_id)
    if operation == "publish":
        new = transform(old)
        BACKUPS.mkdir(mode=0o700, parents=True, exist_ok=True)
        if stat.S_IMODE(BACKUPS.stat().st_mode) != 0o700:
            raise RuntimeError("Backup directory not private")
        if backup.exists() or backup.is_symlink() or marker.exists() or marker.is_symlink():
            raise RuntimeError("Release identifier already used")
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(old)
            handle.flush()
            os.fsync(handle.fileno())
        atomic_write(marker, digest(new).encode("ascii") + b"\n", 0o600)
        if TARGET.read_bytes() != old:
            raise RuntimeError("Live source changed during guarded release")
        try:
            atomic_write(TARGET, new)
            if TARGET.read_bytes() != new:
                raise RuntimeError("Published bytes failed verification")
        except BaseException:
            if TARGET.read_bytes() == new:
                atomic_write(TARGET, old)
            raise
        print(f"MPW_DIRECT_TOOL_LINKS_PUBLISHED=PASS new_sha256={digest(new)} cards=12")
        return
    if operation == "rollback":
        if not backup.is_file() or not marker.is_file():
            raise RuntimeError("Missing owned release backup")
        if digest(old) != marker.read_text().strip():
            raise RuntimeError("Live file changed after release; refusing rollback")
        restored = backup.read_bytes()
        transform(restored)  # Require the original template shape, not arbitrary bytes.
        atomic_write(TARGET, restored)
        if TARGET.read_bytes() != restored:
            raise RuntimeError("Rollback verification failed")
        print("MPW_DIRECT_TOOL_LINKS_ROLLBACK=PASS")
        return
    raise RuntimeError("Supported operations: selftest, preflight, publish, rollback")


if __name__ == "__main__":
    run(*sys.argv[1:])
