#!/usr/bin/env python3
"""Fail-closed Moj Prop catalog, samples and Starter30 free education release.

Source changes never directly modify the live site. A separately approved
manual workflow must install the secured backend before this static release.
All existing files are compared with the source-controlled approved baseline.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import pwd
import re
import stat
import sys
import tempfile
from pathlib import Path

HOME = Path("/home/zomorod2")
DOCROOT = HOME / "mojplaywin.com"
ROUTE = DOCROOT / "moj-prop"
BACKUPS = HOME / ".mojplaywin-backups"
HTML_FILES = (
    Path("index.html"),
    Path("samples/prop-blueprint/index.html"),
    Path("samples/gold-market-brief/index.html"),
    Path("samples/educational-signal/index.html"),
    Path("samples/commercial-gate-audit/index.html"),
    Path("catalog/index.html"),
    Path("signals/index.html"),
    Path("starter-30-trx/index.html"),
    Path("contact/index.html"),
)
# These two FREE educational files are part of the same reversible static
# release. A sales link must never be published without its actual content.
STARTER30_FILES = (
    Path("starter-30-trx/journal-template.csv"),
    Path("starter-30-trx/journal-guide.txt"),
)
# A real owner-edited Signal Desk was observed on cPanel (unknown hash).
# Starter30 release is strictly *not* authorized to rewrite that separate page.
PRESERVED_LIVE_FILES = (Path("signals/index.html"),)
FILES = tuple(x for x in HTML_FILES if x not in PRESERVED_LIVE_FILES) + STARTER30_FILES
MANIFEST_SCHEMA = "mojprop.static.plan1-c153.v4-contact-rollback"
BASELINE_CATALOG = Path("baselines/catalog-index-v4.html")
BASELINE_HOME = Path("baselines/index-v4.html")
# Exact Git blob of main's current pre-Plan1 homepage, not an arbitrary
# operator-supplied baseline; preserved separately from the historical v4.
BASELINE_MAIN_HOME = Path("baselines/index-main-before-plan1-c153.html")
BASELINE_MAIN_HOME_GIT_BLOB = "30b7fe4400f88252f3b71a581f96a796ca853b6c"
BASELINE_CONTACT = Path("baselines/contact-index-pre-plan1.html")
BASELINE_SIGNAL = Path("baselines/signals-index-before-free.html")
# Exact #2407 one-off public research preview (before double opt-in #2428).
BASELINE_SIGNAL_FREE_PREVIEW = Path("baselines/signals-index-after-free-preview.html")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_id(value: str) -> str:
    if not re.fullmatch(r"[0-9]{1,20}", value):
        raise ValueError("Invalid deployment run ID")
    return value


def assert_file(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("Expected a regular file: " + str(path))


def assert_safe_destination(path: Path) -> None:
    if ROUTE.is_symlink() or not ROUTE.is_dir():
        raise RuntimeError("Moj Prop route is missing or is a symlink")
    current = path.parent
    while current != ROUTE.parent:
        if current.is_symlink():
            raise RuntimeError("Symlink parent refused: " + str(current))
        if current == ROUTE:
            return
        current = current.parent
    raise RuntimeError("Destination is outside the Moj Prop route")


def atomic_write(path: Path, data: bytes, mode: int = 0o644) -> None:
    assert_safe_destination(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    fd, name = tempfile.mkstemp(prefix="." + path.name + ".mojprop-", dir=str(path.parent))
    temp = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def source_root(run_id: str) -> Path:
    path = HOME / (".mojplaywin-moj-prop-catalog-" + safe_id(run_id)) / "templates/moj-prop-v4"
    if path.is_symlink() or not path.is_dir():
        raise RuntimeError("Invalid staged Moj Prop source")
    for relative in FILES + PRESERVED_LIVE_FILES + (BASELINE_CATALOG, BASELINE_HOME, BASELINE_MAIN_HOME, BASELINE_CONTACT, BASELINE_SIGNAL, BASELINE_SIGNAL_FREE_PREVIEW):
        assert_file(path / relative)
    # Pin the newly added migration baseline to the exact public-repo Git
    # blob of main (679d2fefd349f580e765fee1a5fc823c48e01851). A
    # manipulated staged baseline must NEVER authorize rewriting owner edits.
    reviewed = (path / BASELINE_MAIN_HOME).read_bytes()
    blob = b"blob " + str(len(reviewed)).encode("ascii") + b"\0" + reviewed
    if hashlib.sha1(blob).hexdigest() != BASELINE_MAIN_HOME_GIT_BLOB:
        raise RuntimeError("Unreviewed current-main homepage baseline denied")
    html = {str(relative): (path / relative).read_text("utf-8") for relative in HTML_FILES}
    if ("const endpoint='/moj-prop-intake/';" not in html["index.html"]
            or '<option value="week">This week</option>' not in html["index.html"]
            or "href=\"/moj-prop/catalog/\"" not in html["index.html"]):
        raise RuntimeError("Staged homepage lacks working intake contract")
    catalog = html["catalog/index.html"]
    if ("/moj-prop/samples/prop-blueprint/" not in catalog
            or "/moj-prop/samples/gold-market-brief/" not in catalog
            or "/moj-prop/samples/educational-signal/" not in catalog
            or "/moj-prop/samples/commercial-gate-audit/" not in catalog):
        raise RuntimeError("Staged catalog sample links missing")
    signal_page = html["signals/index.html"]
    if ('id="free-education-membership"' not in signal_page
            or "/moj-signal-free-subscribe/" not in signal_page
            or 'id="free-preview"' not in signal_page
            or "no paid" in signal_page.lower() and "no payment" not in signal_page.lower()):
        raise RuntimeError("Signal Desk free educational opt-in contract is missing")
    for sample in HTML_FILES[1:5]:
        doc = html[str(sample)]
        if "<title>" not in doc or "Sample" not in doc:
            raise RuntimeError("Staged commercial sample invalid: " + str(sample))
    # Product content is deliberately open and FREE to inspect. This is
    # NOT a checkout, invoice, broker account or guarantee of paid delivery.
    starter = html["starter-30-trx/index.html"]
    if (not all(mark in starter for mark in (
            "MOJPROP-STARTER30", "Payment not enabled",
            "./journal-template.csv", "./journal-guide.txt",
            "30 TRX", "not a funded account"))):
        raise RuntimeError("Starter30 page is missing its ethical sales and delivery boundary")
    guide = (path / STARTER30_FILES[1]).read_text(encoding="utf-8")
    if not all(mark in guide for mark in (
            "Ten-session educational journal", "Exactly 10 valid sessions",
            "not funded and not withdrawable", "Payment is not available")):
        raise RuntimeError("Starter30 journal guide is incomplete or unsafe")
    raw_csv = (path / STARTER30_FILES[0]).read_bytes()
    if len(raw_csv) > 2048 or b"\x00" in raw_csv:
        raise RuntimeError("Starter30 template exceeds safe public journal boundary")
    try:
        rows = list(csv.reader(io.StringIO(raw_csv.decode("utf-8"))))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise RuntimeError("Starter30 CSV is not a readable educational template") from exc
    if (len(rows) != 11
            or rows[0] != ["session", "closing_equity_usd",
                           "risk_plan_recorded", "reflection_recorded"]
            or any(row != [str(i), "", "", ""] for i, row in enumerate(rows[1:], 1))):
        raise RuntimeError("Starter30 CSV must contain exactly 10 EMPTY simulated sessions")
    # Starter30 educational files remain individually inspectable in their
    # catalog and atomically backed up, but they are NOT the funded Plan1 hero.
    # This split must never weaken the prior byte-exact rollback protections.
    if "/moj-prop/starter-30-trx/" not in catalog:
        raise RuntimeError("Starter30 educational package missing from catalog")
    home = html["index.html"]
    required_plan1 = (
        "SOLE CURRENT PRODUCT", "MOJ-PROP-01",
        "Prelaunch only:", "30,000,000 SUN",
        'href="/moj-prop/contact/"',
        "Support contact is NOT an accepted Plan 1 CRM lead",
    )
    if not all(mark in home for mark in required_plan1):
        raise RuntimeError("Plan1 prelaunch homepage source is not approved")
    # The dedicated consent-only Django form is NOT on main/production today.
    # Do not publish a clickable 404 and imply that a lead was recorded.
    if ('href="/moj-prop-interest/form/' in home
            or "/moj-prop/starter-30-trx/" in home):
        raise RuntimeError("Plan1 home links to an unavailable form or old educational SKU")
    contact = html["contact/index.html"]
    # This is a prelaunch support route, never a CRM form or a payment route.
    if (not all(mark in contact for mark in (
            "MOJ-PROP-01", "prelaunch",
            "mailto:support@mojplaywin.com?subject=MOJ-PROP-01",
            "Dedicated Plan 1 form not live"))
            or 'href="/moj-prop-interest/form/' in contact
            or "<form" in contact.lower()):
        raise RuntimeError("Prelaunch contact is not the approved voluntary support page")
    return path


def validate_host() -> None:
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("Wrong cPanel account")
    if DOCROOT.is_symlink() or not DOCROOT.is_dir():
        raise RuntimeError("MojPlayWin document root invalid")
    for relative in ("passenger_wsgi.py", ".htaccess"):
        assert_file(DOCROOT / relative)


def verify_private_backup_root(*, create: bool) -> None:
    """Refuse symlinked, world-writable or foreign-owned backup parents.

    Never chmod existing host directories: this publisher has no authority
    to repair the private data of unrelated tenants or workflows.
    """
    parent = BACKUPS.parent
    if parent.is_symlink() or not parent.is_dir():
        raise RuntimeError("Untrusted Moj Prop backup parent")
    parent_stat = parent.lstat()
    if (not stat.S_ISDIR(parent_stat.st_mode)
            or parent_stat.st_uid != os.geteuid()
            or parent_stat.st_mode & stat.S_IWOTH):
        raise RuntimeError("Untrusted Moj Prop backup parent owner or mode")
    if BACKUPS.is_symlink():
        raise RuntimeError("Symlinked Moj Prop backup root refused")
    if BACKUPS.exists():
        info = BACKUPS.lstat()
        if (not stat.S_ISDIR(info.st_mode)
                or info.st_uid != os.geteuid()
                or info.st_mode & 0o077):
            raise RuntimeError("Untrusted Moj Prop backup root owner or mode")
    elif create:
        BACKUPS.mkdir(mode=0o700)
        verify_private_backup_root(create=False)
    else:
        raise RuntimeError("Moj Prop private backup root is missing")


def plan(root: Path) -> list[dict]:
    old_catalog = (root / BASELINE_CATALOG).read_bytes()
    old_home = (root / BASELINE_HOME).read_bytes()
    exact_pre_plan1_home = (root / BASELINE_MAIN_HOME).read_bytes()
    old_contact = (root / BASELINE_CONTACT).read_bytes()
    old_signal = (root / BASELINE_SIGNAL).read_bytes()
    free_preview_signal = (root / BASELINE_SIGNAL_FREE_PREVIEW).read_bytes()
    marker = b"<!-- MOJ_PROP_CATALOG_RELEASE_V4 -->\n"
    old_home_without_marker = old_home.replace(marker, b"", 1)
    # The Signal Desk is independent of this product. Preserve even unreviewed
    # owner edits byte-for-byte: neither plan, deploy, nor rollback lists it.
    for preserved in PRESERVED_LIVE_FILES:
        target = ROUTE / preserved
        assert_safe_destination(target)
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise RuntimeError("Unsafe Signal Desk path; preserve and refuse unrelated release")
    intended = []
    for relative in FILES:
        target = ROUTE / relative
        assert_safe_destination(target)
        exists = target.exists() or target.is_symlink()
        if exists:
            assert_file(target)
        before = target.read_bytes() if exists else None
        after = (root / relative).read_bytes()
        if relative == Path("index.html"):
            if not exists or before not in (after, old_home, old_home_without_marker, exact_pre_plan1_home):
                raise RuntimeError("Live home differs from approved baseline; refusing replacement")
        elif relative == Path("contact/index.html") and exists:
            if before not in (after, old_contact):
                raise RuntimeError("Live Plan1 contact differs from approved baseline; refusing replacement")
        elif relative == Path("catalog/index.html") and exists:
            if before != after and before != old_catalog:
                raise RuntimeError("Live catalog differs from both approved baseline and release; refusing replacement")
        elif exists and before != after:
            raise RuntimeError("A public Moj Prop asset exists with unexpected content; refusing replacement")
        intended.append({
            "path": str(relative), "existed": exists,
            "before_sha": digest(before) if exists else None,
            "after_sha": digest(after), "changed": before != after,
            "mode": (target.stat().st_mode & 0o777) if exists else 0o644,
        })
    return intended


def verified_manifest(path: Path) -> dict:
    """Treat even a local backup manifest as untrusted rollback instructions."""
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise RuntimeError("Symlinked or missing rollback directory")
    assert_file(path)
    value = json.loads(path.read_text("utf-8"))
    if type(value) is not dict or value.get("schema") != MANIFEST_SCHEMA:
        raise RuntimeError("Legacy or unrecognized static backup manifest; use the pinned prior rollback version")
    expected = [str(item) for item in FILES]
    if type(value) is not dict or type(value.get("files")) is not list:
        raise RuntimeError("Unrecognized Moj Prop rollback manifest")
    entries = value["files"]
    if len(entries) != len(expected) or [item.get("path") for item in entries if type(item) is dict] != expected:
        raise RuntimeError("Rollback manifest file list is incomplete or out of order")
    if value.get("rolled_back") not in (True, False):
        raise RuntimeError("Rollback status is invalid")
    if not isinstance(value.get("run_id"), str):
        raise RuntimeError("Missing rollback run ID")
    safe_id(value["run_id"])
    if path.parent.name != "moj-prop-catalog-" + value["run_id"]:
        raise RuntimeError("Rollback run ID and backup directory disagree")
    if not re.fullmatch(r"[0-9a-f]{40}", str(value.get("commit_sha", ""))):
        raise RuntimeError("Rollback commit identity is invalid")
    for item in entries:
        if type(item.get("existed")) is not bool or type(item.get("changed")) is not bool:
            raise RuntimeError("Invalid before/after backup flags")
        if type(item.get("mode")) is not int or not 0 <= item["mode"] <= 0o777 or item["mode"] & (0o111 | 0o002):
            raise RuntimeError("Unsafe rollback file mode")
        before = item.get("before_sha")
        if (item["existed"] and not isinstance(before, str)) or (not item["existed"] and before is not None):
            raise RuntimeError("Invalid previous-file digest")
        if before is not None and not re.fullmatch(r"[0-9a-f]{64}", before):
            raise RuntimeError("Previous-file digest malformed")
        if not isinstance(item.get("after_sha"), str) or not re.fullmatch(r"[0-9a-f]{64}", item["after_sha"]):
            raise RuntimeError("Deployed-file digest malformed")
    return value


def verified_saved_bytes(backup: Path, manifest: dict) -> dict[str, bytes]:
    """Verify the COMPLETE backup inventory before the first live file write.

    In particular, a corrupt index.html must not be discovered *after* a
    catalog.html restore was performed. Keep reviewed bytes in memory so a
    post-check symlink swap or mutation cannot feed an automated rollback.
    This is file-level integrity only; it does not attest a database restore.
    """
    if backup.parent != BACKUPS or backup.is_symlink() or not backup.is_dir():
        raise RuntimeError("Untrusted Moj Prop catalog backup scope")
    records: dict[str, bytes] = {}
    for item in manifest["files"]:
        if not item["existed"]:
            continue
        saved = backup / "files" / item["path"]
        ancestor = saved.parent
        while ancestor != backup:
            if ancestor.is_symlink() or not ancestor.is_dir():
                raise RuntimeError("Unsafe backup directory ancestry: " + item["path"])
            ancestor = ancestor.parent
        assert_file(saved)
        metadata = saved.lstat()
        if (metadata.st_uid != os.geteuid()
                or metadata.st_mode & 0o077
                or not stat.S_ISREG(metadata.st_mode)):
            raise RuntimeError("Unsafe saved backup owner or permissions: " + item["path"])
        raw = saved.read_bytes()
        if digest(raw) != item["before_sha"]:
            raise RuntimeError("Backup checksum mismatch before any live change: " + item["path"])
        records[item["path"]] = raw
    return records


def restore(backup: Path, *, automated: bool = False) -> None:
    verify_private_backup_root(create=False)
    if backup.parent != BACKUPS or backup.is_symlink():
        raise RuntimeError("Symlinked or out-of-scope Moj Prop rollback path refused")
    manifest = verified_manifest(backup / "manifest.json")
    if manifest.get("rolled_back") is True:
        print("MOJ_PROP_ALREADY_ROLLED_BACK")
        return
    # Check every changed file before modifying any, preventing rollback over
    # another operator's edits.
    for item in manifest["files"]:
        target = ROUTE / item["path"]
        assert_safe_destination(target)
        if not item["changed"]:
            continue
        assert_file(target)
        if digest(target.read_bytes()) != item["after_sha"]:
            raise RuntimeError("Refusing to roll back a subsequently modified file: " + item["path"])
    # Verify EVERY original backup before touching ANY live file.
    # A later corrupt entry must never create a half-rolled-back website.
    saved_bytes = verified_saved_bytes(backup, manifest)
    for item in reversed(manifest["files"]):
        if not item["changed"]:
            continue
        target = ROUTE / item["path"]
        if item["existed"]:
            atomic_write(target, saved_bytes[item["path"]], int(item["mode"]))
        else:
            target.unlink()
        if item["existed"] and digest(target.read_bytes()) != item["before_sha"]:
            raise RuntimeError("Rollback verification failed: " + item["path"])
    manifest["rolled_back"] = True
    (backup / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("MOJ_PROP_CATALOG_ROLLBACK_COMPLETE")


def preflight(run_id: str) -> None:
    """Host-only, read-only exact release compatibility check.

    Must run before backend schema migrations; a successful source CI is
    insufficient proof of a compatible live Signal Desk or restorable DB.
    """
    safe_id(run_id)
    validate_host()
    root = source_root(run_id)
    proposed = plan(root)  # refuses unknown customer-edited live content
    print("MOJ_PROP_STATIC_PREFLIGHT=PASS")
    print("MOJ_PROP_STATIC_PREFLIGHT_PATHS=" + str(len(proposed)))
    print("MOJ_PROP_STATIC_PREFLIGHT_CHANGES=" + str(
        sum(1 for item in proposed if item["changed"])
    ))
    print("MOJ_PROP_STATIC_PREFLIGHT_NO_WRITES=true")


def deploy(run_id: str, commit: str) -> None:
    safe_id(run_id)
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Unverified release commit")
    validate_host()
    root = source_root(run_id)
    changes = plan(root)
    if not any(item["changed"] for item in changes):
        print("MOJ_PROP_SAMPLES_AND_CATALOG_ALREADY_LIVE")
        return
    verify_private_backup_root(create=True)
    backup = BACKUPS / ("moj-prop-catalog-" + run_id)
    if backup.exists() or backup.is_symlink():
        raise RuntimeError("Backup ID already used")
    backup.mkdir(parents=True, mode=0o700)
    manifest = {"schema": MANIFEST_SCHEMA, "run_id": run_id, "commit_sha": commit, "files": changes, "rolled_back": False}
    for item in changes:
        if item["existed"]:
            previous = ROUTE / item["path"]
            saved = backup / "files" / item["path"]
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_bytes(previous.read_bytes())
            os.chmod(saved, 0o600)
    (backup / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    # Verify all saved source bytes before the first publish write. The same
    # immutable, verified snapshot is used for any in-process rollback.
    saved_bytes = verified_saved_bytes(backup, manifest)
    applied = []
    try:
        for item in changes:
            if not item["changed"]:
                continue
            target = ROUTE / item["path"]
            # Double-check source and destination after backup before writes.
            if item["existed"] and digest(target.read_bytes()) != item["before_sha"]:
                raise RuntimeError("Live content changed after backup: " + item["path"])
            data = (root / item["path"]).read_bytes()
            if digest(data) != item["after_sha"]:
                raise RuntimeError("Staged content changed after validation")
            atomic_write(target, data, int(item["mode"]))
            applied.append(item)
            if digest(target.read_bytes()) != item["after_sha"]:
                raise RuntimeError("Post-install hash mismatch: " + item["path"])
    except Exception:
        # Roll back only files this run actually installed, not untouched files.
        for item in reversed(applied):
            target = ROUTE / item["path"]
            if not target.is_symlink() and target.is_file() and digest(target.read_bytes()) == item["after_sha"]:
                if item["existed"]:
                    atomic_write(target, saved_bytes[item["path"]], int(item["mode"]))
                else:
                    target.unlink()
        raise
    print("MOJ_PROP_CATALOG_SAMPLES_DEPLOYED commit=" + commit)
    print("MOJ_PROP_CATALOG_BACKUP=" + str(backup))


def main() -> None:
    if len(sys.argv) == 4 and sys.argv[1] == "deploy":
        deploy(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3 and sys.argv[1] == "preflight":
        preflight(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "rollback":
        validate_host()
        restore(BACKUPS / ("moj-prop-catalog-" + safe_id(sys.argv[2])))
    else:
        raise SystemExit("Usage: catalog.py preflight RUN_ID | deploy RUN_ID SHA | rollback RUN_ID")


if __name__ == "__main__":
    main()
