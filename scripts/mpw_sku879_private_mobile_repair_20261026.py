#!/usr/bin/env python3
"""Private, hash-bound candidate repair for SKU879 mobile overflow. No live release."""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import zipfile

SOURCE_SHA = "20894f2de0228318c0e96ba407c2bd4aa98b62ba2f3f2f2fbca53987c9276783"
ROOT = Path("/home/githubops/factory-runtime/private/autonomous-product-cycle/design-intake/mpw-live-three-sku-qa")
SKU = 879


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def safe_extract(*args):
    from mpw_sku879_private_browser_qa_20261026 import safe_extract as impl
    return impl(*args)


def browser_views(*args):
    from mpw_sku879_private_browser_qa_20261026 import browser_views as impl
    return impl(*args)

MARKER = "mpw-private-responsive-repair-20261026"
MAX_STREAM = 200 * 1024 * 1024
BASE_STYLE = r"""
@media (max-width: 767px) {
  :where(h1,h2,h3,h4,h5,h6,p,a,span,strong,em,button,li) {
    overflow-wrap: anywhere;
  }
  :where(main,section,article,header,footer,nav,div,figure) {
    min-width: 0;
  }
  :where(img,video,svg,canvas) { max-width: 100%; }
}
"""
ADDITIONAL_STYLE = r"""
@media (max-width: 767px) {
  :where(main,section,article,header,footer,nav,div,figure) {
    max-width: 100%;
  }
}
"""
NARROW_SPAN_STYLE = r"""
@media (max-width: 359px) {
  span {
    white-space: normal !important;
    overflow-wrap: anywhere;
  }
}
"""
THIRD_STYLE = r"""
@media (max-width: 767px) {
  :where(main,section,article,header,footer,nav,div,figure) {
    flex-shrink: 1;
  }
  :where(main,section,article,header,footer,nav,div,figure,p) {
    word-break: normal;
    hyphens: auto;
  }
}
"""
VARIANTS = [
    ("intrinsic-text-and-flex-shrink", BASE_STYLE),
    ("contain-layout-blocks", BASE_STYLE + ADDITIONAL_STYLE),
    ("contain-and-unwrap-small-mobile-caption", BASE_STYLE + ADDITIONAL_STYLE + NARROW_SPAN_STYLE),
    ("contain-and-hyphenate", BASE_STYLE + ADDITIONAL_STYLE + NARROW_SPAN_STYLE + THIRD_STYLE),
]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def inject(html, css):
    marker = '<style id="' + MARKER + '">' + css + "</style>"
    hits = list(re.finditer(r"</head\s*>", html, flags=re.IGNORECASE))
    if len(hits) != 1 or MARKER in html:
        raise RuntimeError("CANDIDATE_HTML_HEAD_INVALID")
    hit = hits[0]
    return html[:hit.start()] + marker + "\n" + html[hit.start():]


def passes(views):
    if len(views) != 2:
        return False
    for view in views:
        physical = view["requested_viewport"][0]
        if (not view["ready"] or not view["title_present"] or
                view["body_char_count"] < 30 or
                view["broken_images"] != 0 or
                not view["screenshot_valid"] or
                view["horizontal_overflow_px"] > 2 or
                view["viewport_height"] != view["requested_viewport"][1]):
            return False
        if physical < 500:
            if (view["device_screen_width"] != physical or
                    abs(view["visual_viewport_width"] - physical) > 1):
                return False
        elif view["viewport_width"] != physical:
            return False
    return True


def repackage(original, output, entry, amended):
    with zipfile.ZipFile(original, "r") as source:
        with zipfile.ZipFile(output, "x") as target:
            for member in source.infolist():
                data = amended if member.filename == entry else source.read(member.filename)
                target.writestr(member, data)
    with zipfile.ZipFile(output) as candidate, zipfile.ZipFile(original) as source:
        a = candidate.namelist()
        b = source.namelist()
        if a != b:
            raise RuntimeError("CANDIDATE_MEMBER_LIST_CHANGED")
        for name in b:
            if name != entry and digest(candidate.read(name)) != digest(source.read(name)):
                raise RuntimeError("CANDIDATE_ORIGINAL_ASSET_MUTATED")
    return sha256_file(output)


def repair(archive, output, receipt_file, expected=SOURCE_SHA):
    archive, output, receipt_file = Path(archive), Path(output), Path(receipt_file)
    if expected != SOURCE_SHA or sha256_file(archive) != SOURCE_SHA:
        raise RuntimeError("CANDIDATE_SOURCE_HASH_MISMATCH")
    attempts = []
    with tempfile.TemporaryDirectory(prefix="mpw879-private-mobile-repair-") as tmp:
        working = Path(tmp)
        entry = safe_extract(archive, working)
        source = (working / entry).read_text(encoding="utf-8-sig")
        from mpw_sku879_private_candidate_12view_qa_20261026 import VIEWPORTS, evaluate_rows
        for name, style in VARIANTS:
            amended = inject(source, style)
            (working / entry).write_text(amended, encoding="utf-8")
            try:
                views = browser_views(working, entry, VIEWPORTS)
                checks = evaluate_rows(views)
                valid = bool(checks) and all(checks.values())
                attempts.append({
                    "variant": name,
                    "passes": valid,
                    "max_visual_overflow_px": max(v["horizontal_overflow_px"] for v in views),
                    "mobile_screen_width": views[0]["device_screen_width"],
                    "mobile_visual_width": views[0]["visual_viewport_width"],
                    "mobile_layout_width": views[0]["viewport_width"],
                    "broken_images": sum(v["broken_images"] for v in views),
                })
                if valid:
                    candidate_sha = repackage(archive, output, entry, amended.encode("utf-8"))
                    manifest = {
                        "schema": "saeit.mpw.sku879.private-responsive-candidate.v1",
                        "source_sha256": SOURCE_SHA,
                        "candidate_sha256": candidate_sha,
                        "variant": name,
                        "entrypoint_sha256": digest(entry.encode("utf-8")),
                        "qa": attempts,
                        "browser_smoke_passed": True,
                        "professional_visual_reviewed": False,
                        "quality1000_verified": False,
                        "commercial_release_allowed": False,
                        "live_product_modified": False,
                    }
                    receipt_file.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
                    os.chmod(receipt_file, 0o600)
                    print("MPW879_PRIVATE_RESPONSIVE_REPAIR=" + json.dumps({
                        "source_sha256": SOURCE_SHA,
                        "candidate_sha256": candidate_sha,
                        "chosen_variant": name,
                        "attempts": attempts,
                        "commercial_release_allowed": False,
                        "quality1000_verified": False
                    }, sort_keys=True))
                    return manifest
            finally:
                (working / entry).write_text(source, encoding="utf-8")
    print("MPW879_PRIVATE_RESPONSIVE_REPAIR=" + json.dumps({
        "source_sha256": SOURCE_SHA, "candidate_sha256": None,
        "attempts": attempts, "commercial_release_allowed": False,
        "quality1000_verified": False
    }, sort_keys=True))
    raise RuntimeError("NO_PRIVATE_RESPONSIVE_CANDIDATE_PASSED")


def ingest(source=sys.stdin.buffer, root=ROOT):
    original = root / "copies" / str(SKU) / (SOURCE_SHA + ".bin")
    if original.is_symlink() or not original.is_file() or sha256_file(original) != SOURCE_SHA:
        raise RuntimeError("PRIVATE_RESPONSIVE_SOURCE_UNVERIFIED")
    folder = root / "quality1000-rework" / str(SKU) / SOURCE_SHA / "mobile-candidates"
    if folder.is_symlink():
        raise RuntimeError("PRIVATE_RESPONSIVE_CANDIDATE_DIR_SYMLINK")
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(folder, 0o700)
    bytes_read = 0
    hasher = hashlib.sha256()
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".responsive-candidate-")
    try:
        with os.fdopen(fd, "wb") as dest:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                bytes_read += len(chunk)
                if bytes_read > MAX_STREAM:
                    raise RuntimeError("PRIVATE_RESPONSIVE_CANDIDATE_TOO_LARGE")
                hasher.update(chunk)
                dest.write(chunk)
            dest.flush()
            os.fsync(dest.fileno())
        if bytes_read == 0 or not zipfile.is_zipfile(tmp):
            raise RuntimeError("PRIVATE_RESPONSIVE_CANDIDATE_NOT_ZIP")
        with zipfile.ZipFile(tmp) as package:
            names = package.namelist()
            indexes = [n for n in names if Path(n).name.lower() == "index.html"]
            if len(indexes) < 1 or not any(MARKER.encode() in package.read(name) for name in indexes):
                raise RuntimeError("PRIVATE_RESPONSIVE_CANDIDATE_MARKER_MISSING")
        result_sha = hasher.hexdigest()
        final = folder / (result_sha + ".zip")
        if final.is_symlink():
            raise RuntimeError("PRIVATE_RESPONSIVE_CANDIDATE_SYMLINK")
        try:
            os.link(tmp, final)
            created = True
        except FileExistsError:
            if sha256_file(final) != result_sha:
                raise RuntimeError("PRIVATE_RESPONSIVE_CANDIDATE_CONFLICT")
            created = False
        print("MPW879_PRIVATE_RESPONSIVE_CANDIDATE_STORED=" + json.dumps({
            "source_sha256": SOURCE_SHA,
            "candidate_sha256": result_sha,
            "created": created,
            "quality1000_verified": False,
            "commercial_release_allowed": False,
            "live_product_modified": False
        }, sort_keys=True))
        return result_sha
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "ingest":
        ingest()
    elif len(sys.argv) == 5 and sys.argv[1] == "repair":
        repair(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        raise SystemExit("USAGE_ERROR")
