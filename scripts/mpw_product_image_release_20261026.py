#!/usr/bin/env python3
"""Narrow, reversible release of two user-provided MojPlayWin product images."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

HOME = Path("/home/zomorod2")
APP = HOME / "Saeit-staging"
SITE = HOME / "mojplaywin.com"
STORE = APP / "core/templates/mojplaywin/store.html"
STAGE = Path(__file__).resolve().parent
BACKUP_ROOT = HOME / ".private_mojplaywin_product_image_backups"
FILES = {
    "chess": "chess-improvement.webp",
    "taniya": "taniya-baker-worms.webp",
}
REPLACEMENTS = [
  [
    "    <div class=\"mpw-shop-art\" role=\"img\" aria-label=\"Typographic previews of the chess-training book and Taniya illustrated story\"><div class=\"mpw-shop-art-book\"><small>Chess · Training Guide</small><strong>The Science and Practice of Chess Improvement</strong><small>Mojtaba Roozegar · 2026</small></div><div class=\"mpw-shop-art-book\"><small>Illustrated Story · Ages 3–8</small><strong>Taniya and the Little Baker Worms</strong><small>English · 40 pages</small></div><p class=\"mpw-shop-art-note\">TITLE ARTWORK PREVIEWS · DIGITAL EDITIONS</p></div>",
    "    <div class=\"mpw-shop-art\" aria-label=\"Featured MojPlayWin product artwork\"><img class=\"mpw-shop-art-image\" src=\"/static/site/mojplaywin-products/chess-improvement.webp?v=20261026\" width=\"1122\" height=\"1402\" alt=\"Chess promotional artwork with a golden king and black knight\" decoding=\"async\"><img class=\"mpw-shop-art-image\" src=\"/static/site/mojplaywin-products/taniya-baker-worms.webp?v=20261026\" width=\"1122\" height=\"1402\" alt=\"Taniya and the Little Baker Worms in a colorful bakery\" decoding=\"async\"><p class=\"mpw-shop-art-note\">FEATURED PRODUCT ARTWORK · MOJPLAYWIN</p></div>"
  ],
  [
    "        <div class=\"mpw-product-visual\" aria-hidden=\"true\"><div class=\"mpw-product-cover\"><small>Chess · Research-informed training</small><strong>The Science and Practice of Chess Improvement</strong><span>MOJTABA ROOZEGAR · 2026</span></div></div>",
    "        <div class=\"mpw-product-visual\"><img class=\"mpw-product-image\" src=\"/static/site/mojplaywin-products/chess-improvement.webp?v=20261026\" alt=\"Chess: golden king, black knight and pawn on a chessboard — promotional artwork\" width=\"1122\" height=\"1402\" loading=\"lazy\" decoding=\"async\"></div>"
  ],
  [
    "        <div class=\"mpw-product-visual\" aria-hidden=\"true\"><div class=\"mpw-product-cover\"><small>Illustrated story · Family reading</small><strong>Taniya and the Little Baker Worms</strong><span>MOJTABA ROOZEGAR</span></div></div>",
    "        <div class=\"mpw-product-visual\"><img class=\"mpw-product-image\" src=\"/static/site/mojplaywin-products/taniya-baker-worms.webp?v=20261026\" alt=\"Taniya baking bread with three cheerful little baker worms — illustrated story poster\" width=\"1122\" height=\"1402\" loading=\"lazy\" decoding=\"async\"></div>"
  ],
  [
    "</style>\n<main class=\"mpw-shop\">",
    ".mpw-product-visual{height:clamp(245px,25vw,330px)}.mpw-product-image{position:relative;z-index:1;display:block;width:100%;height:100%;object-fit:contain;object-position:center;padding:10px}.mpw-shop-art-image{display:block;width:100%;height:255px;object-fit:contain;object-position:center;border-radius:12px;border:1px solid rgba(225,189,99,.35);background:#0c100e;box-shadow:7px 12px 25px #0009}@media(max-width:650px){.mpw-shop-art-image{height:clamp(155px,45vw,235px)}.mpw-product-visual{height:280px}}\n</style>\n<main class=\"mpw-shop\">"
  ]
]
def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def fail(message: str):
    raise RuntimeError("MPW_IMAGES_SAFE_ABORT: " + message)

def validate_run(run: str):
    if not re.fullmatch(r"[0-9]{8,20}", run):
        fail("Invalid run identifier")
    if SITE.is_symlink() or APP.is_symlink() or not SITE.is_dir() or not APP.is_dir():
        fail("Pinned MojPlayWin application identity missing")
    wsgi = SITE / "passenger_wsgi.py"
    if wsgi.is_symlink() or not wsgi.is_file() or "APP='/home/zomorod2/Saeit-staging'" not in wsgi.read_text("utf8", "replace"):
        fail("Passenger mapping changed")
    if not STORE.is_file() or STORE.is_symlink() or STORE.stat().st_size > 2000000:
        fail("MojPlayWin store template is not a safe regular file")

def transform(original: bytes) -> bytes:
    s = original.decode("utf8")
    for before, after in REPLACEMENTS:
        if s.count(before) != 1:
            fail("Expected exact single template fragment missing")
        s = s.replace(before, after, 1)
    if "/store/product/879/" not in s or "/store/product/72/" not in s or "/store/product/225/" not in s:
        fail("Other product listing or purchase links missing")
    return s.encode("utf8")

def selftest():
    path = Path("core/templates/mojplaywin/store.html")
    s = path.read_text("utf8")
    for before, after in reversed(REPLACEMENTS):
        if s.count(after) != 1:
            fail("Checked-in source image replacement not unique")
        s = s.replace(after, before, 1)
    if transform(s.encode("utf8")) != path.read_bytes():
        fail("Source patch not reversible")
    print("MPW_IMAGE_PATCH_SELFTEST=PASS")

def candidates(name: str):
    return [
        APP / "staticfiles/site/mojplaywin-products" / name,
        APP / "core/static/site/mojplaywin-products" / name,
        SITE / "static/site/mojplaywin-products" / name,
    ]

def safe_file(p: Path):
    if not p.is_file() or p.is_symlink() or p.parent.is_symlink() or p.parent.parent.is_symlink():
        fail("Unsafe or missing target: " + str(p))

def atomic_write(p: Path, data: bytes):
    safe_file(p)
    mode = stat.S_IMODE(p.stat().st_mode)
    fd, temp = tempfile.mkstemp(prefix=".mpw-image-atomic-", dir=p.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, p)
    finally:
        if os.path.lexists(temp):
            os.unlink(temp)

def restart():
    folder = SITE / "tmp"
    if folder.is_symlink():
        fail("Unsafe Passenger restart directory")
    folder.mkdir(exist_ok=True)
    marker = folder / "restart.txt"
    if marker.is_symlink():
        fail("Unsafe Passenger restart marker")
    marker.touch()

def backup_folder(run):
    return BACKUP_ROOT / ("release-" + run)

def read_new_images():
    new = {}
    for key, filename in FILES.items():
        f = STAGE / filename
        if not f.is_file() or f.is_symlink():
            fail("Staged image missing: " + key)
        data = f.read_bytes()
        if not (20000 < len(data) < 1000000 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"):
            fail("Invalid staged WebP: " + key)
        new[key] = data
    return new

def install(run, previous_chess_sha, previous_taniya_sha):
    validate_run(run)
    for sha in (previous_chess_sha, previous_taniya_sha):
        if not re.fullmatch(r"[a-f0-9]{64}", sha):
            fail("Invalid public baseline checksum")
    old = STORE.read_bytes()
    patched = transform(old)
    fresh = read_new_images()
    live_hashes = {"chess": previous_chess_sha, "taniya": previous_taniya_sha}
    targets = {"store": (STORE, old, patched)}
    for key, filename in FILES.items():
        found = []
        for p in candidates(filename):
            if p.exists() or p.is_symlink():
                safe_file(p)
                existing = p.read_bytes()
                if digest(existing) == live_hashes[key]:
                    found.append((p, existing, fresh[key]))
        if not found:
            fail("No exact baseline-matching served asset for " + key)
        for i, triple in enumerate(found):
            targets[key + "-" + str(i)] = triple
    if BACKUP_ROOT.is_symlink():
        fail("Backup root is a symlink")
    BACKUP_ROOT.mkdir(mode=0o700, exist_ok=True)
    if stat.S_IMODE(BACKUP_ROOT.stat().st_mode) & 0o077:
        fail("Backup root permissions unsafe")
    folder = backup_folder(run)
    if folder.exists() or folder.is_symlink():
        fail("Run backup already exists")
    folder.mkdir(mode=0o700)
    manifest = {"run": run, "files": {}}
    for label, (p, before, after) in targets.items():
        with (folder / (label + ".bak")).open("xb") as f:
            os.fchmod(f.fileno(), 0o600)
            f.write(before)
            f.flush()
            os.fsync(f.fileno())
        manifest["files"][label] = {
            "path": str(p), "before": digest(before), "after": digest(after),
        }
    with (folder / "manifest.json").open("x") as f:
        os.fchmod(f.fileno(), 0o600)
        json.dump(manifest, f, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    changed = []
    try:
        for label, (p, before, after) in targets.items():
            if digest(p.read_bytes()) != digest(before):
                fail("Concurrent content change: " + label)
            atomic_write(p, after)
            changed.append(label)
            if digest(p.read_bytes()) != digest(after):
                fail("Postwrite digest mismatch: " + label)
        restart()
    except BaseException:
        for label in reversed(changed):
            p, before, after = targets[label]
            if digest(p.read_bytes()) == digest(after):
                atomic_write(p, before)
        restart()
        raise
    print("MPW_IMAGES_INSTALLED=" + json.dumps({
        "labels": list(targets), "asset_sha256": {k:digest(v) for k,v in fresh.items()},
        "product_ids": [72,225], "orders_or_payments_changed": False,
        "backup": str(folder),
    }, sort_keys=True))

def rollback(run):
    validate_run(run)
    folder = backup_folder(run)
    if folder.is_symlink() or not folder.is_dir():
        fail("Rollback backup missing")
    manifest = json.loads((folder / "manifest.json").read_text("utf8"))
    if manifest.get("run") != run:
        fail("Rollback run mismatch")
    for label, meta in reversed(list(manifest["files"].items())):
        p = Path(meta["path"])
        expected = [STORE] + [a for name in FILES.values() for a in candidates(name)]
        if p not in expected:
            fail("Unexpected rollback target")
        safe_file(p)
        saved = (folder / (label + ".bak")).read_bytes()
        if digest(saved) != meta["before"] or digest(p.read_bytes()) != meta["after"]:
            fail("Concurrent modifications prevent rollback: " + label)
        atomic_write(p, saved)
    restart()
    print("MPW_IMAGES_ROLLED_BACK=YES")

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "selftest":
        selftest()
    elif len(sys.argv) == 5 and sys.argv[1] == "install":
        install(sys.argv[2], sys.argv[3], sys.argv[4])
    elif len(sys.argv) == 3 and sys.argv[1] == "rollback":
        rollback(sys.argv[2])
    else:
        raise SystemExit("Usage: script.py selftest|install RUN OLD_CHESS_SHA OLD_TANIYA_SHA|rollback RUN")
