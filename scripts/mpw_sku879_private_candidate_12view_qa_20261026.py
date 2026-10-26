#!/usr/bin/env python3
"""Bounded private 12-viewport QA for SHA-verified responsive SKU879 derivative."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

SKU = 879
SOURCE_SHA = "20894f2de0228318c0e96ba407c2bd4aa98b62ba2f3f2f2fbca53987c9276783"
CANDIDATE_SHA = "4164e8829dab62a85f7bfee19ddaa47a17b872dcf4f0f07bdbc0d20010534a34"
ROOT = Path("/home/githubops/factory-runtime/private/autonomous-product-cycle/design-intake/mpw-live-three-sku-qa")
SCHEMA = "saeit.mpw.sku879.private-candidate-multiview-qa.v1"
VIEWPORTS = (
    (320, 720), (360, 800), (375, 812), (390, 844),
    (428, 926), (600, 800), (767, 900), (768, 900),
    (820, 1000), (1024, 768), (1440, 900), (1920, 1080),
)


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def checksum(raw):
    return hashlib.sha256(raw).hexdigest()


def evaluate_rows(rows):
    if len(rows) != len(VIEWPORTS):
        return {"all_twelve_real_viewports": False}
    viewport_checks = []
    for expected, v in zip(VIEWPORTS, rows):
        w, h = expected
        width_verified = (
            v["device_screen_width"] == w and
            abs(v["visual_viewport_width"] - w) <= 1
            if w < 500 else v["viewport_width"] == w
        )
        viewport_checks.append({
            "viewport": [w, h],
            "device_metrics_verified": bool(width_verified and v["viewport_height"] == h),
            "dom_ready": v["ready"],
            "has_title": v["title_present"],
            "has_visible_content": v["body_char_count"] >= 30,
            "images_loaded": v["broken_images"] == 0,
            "no_visual_overflow": v["horizontal_overflow_px"] <= 2,
            "screenshot_rendered": v["screenshot_valid"],
            "image_alt_attributes_present": v["images_missing_alt"] == 0,
            "button_labels_present": v["unlabeled_buttons"] == 0,
            "form_control_labels_present": v["unlabeled_form_controls"] == 0,
            "safe_new_tab_link_rel": v["unsafe_blank_links"] == 0,
            "same_page_anchors_resolve": v["broken_same_page_anchors"] == 0,
        })
    keys = tuple(k for k in viewport_checks[0] if k != "viewport")
    checks = {"all_twelve_real_viewports": True}
    for name in keys:
        checks[name] = all(v[name] for v in viewport_checks)
    return checks


def audit(archive, receipt_path):
    archive = Path(archive)
    if sha256_file(archive) != CANDIDATE_SHA:
        raise RuntimeError("MULTIVIEW_CANDIDATE_SHA_MISMATCH")
    from mpw_sku879_private_browser_qa_20261026 import safe_extract, browser_views
    with tempfile.TemporaryDirectory(prefix="mpw879-private-candidate-12view-") as tmp:
        index = safe_extract(archive, Path(tmp))
        views = browser_views(Path(tmp), index, VIEWPORTS)
    checks = evaluate_rows(views)
    passed = bool(checks) and all(checks.values())
    condensed = [{
        "size": v["requested_viewport"],
        "visual_width": v["visual_viewport_width"],
        "inner_width": v["viewport_width"],
        "visual_overflow_px": v["horizontal_overflow_px"],
        "broken_images": v["broken_images"],
        "unlabeled_buttons": v["unlabeled_buttons"],
        "unlabeled_form_controls": v["unlabeled_form_controls"],
        "missing_image_alts": v["images_missing_alt"],
        "unsafe_new_tab_links": v["unsafe_blank_links"],
        "broken_anchors": v["broken_same_page_anchors"],
    } for v in views]
    receipt = {
        "schema": SCHEMA, "sku": SKU,
        "source_sha256": SOURCE_SHA, "candidate_sha256": CANDIDATE_SHA,
        "checks": checks, "viewports": condensed,
        "browser_and_accessibility_smoke_passed": passed,
        "professional_visual_reviewed": False,
        "security_review_completed": False,
        "cross_browser_reviewed": False,
        "quality1000_verified": False,
        "commercial_release_allowed": False,
        "live_product_modified": False,
    }
    raw = (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode("utf-8")
    Path(receipt_path).write_bytes(raw)
    os.chmod(receipt_path, 0o600)
    print("MPW879_CANDIDATE_12VIEW_QA=" + json.dumps({
        "candidate_sha256": CANDIDATE_SHA,
        "total_viewports": len(views),
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
        "failed_checks": [k for k,v in checks.items() if not v],
        "viewports": condensed,
        "quality1000_verified": False,
        "commercial_release_allowed": False,
    }, sort_keys=True))
    return passed


def ingest(source=sys.stdin.buffer, root=ROOT):
    raw = source.read(60001)
    if not raw or len(raw) > 60000:
        raise RuntimeError("MULTIVIEW_RECEIPT_SIZE_INVALID")
    receipt = json.loads(raw)
    if (receipt.get("schema") != SCHEMA or
            receipt.get("source_sha256") != SOURCE_SHA or
            receipt.get("candidate_sha256") != CANDIDATE_SHA or
            receipt.get("quality1000_verified") is not False or
            receipt.get("commercial_release_allowed") is not False or
            receipt.get("live_product_modified") is not False or
            not isinstance(receipt.get("checks"), dict) or
            not isinstance(receipt.get("viewports"), list)):
        raise RuntimeError("MULTIVIEW_RECEIPT_IDENTITY_INVALID")
    candidate = root / "quality1000-rework" / str(SKU) / SOURCE_SHA / "mobile-candidates" / (CANDIDATE_SHA + ".zip")
    if candidate.is_symlink() or not candidate.is_file() or sha256_file(candidate) != CANDIDATE_SHA:
        raise RuntimeError("MULTIVIEW_STORED_PRIVATE_CANDIDATE_UNVERIFIED")
    folder = candidate.parent / "browser-audits" / CANDIDATE_SHA
    if folder.is_symlink():
        raise RuntimeError("MULTIVIEW_AUDIT_FOLDER_SYMLINK")
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(folder, 0o700)
    receipt_hash = checksum(raw)
    target = folder / (receipt_hash + ".json")
    if target.is_symlink():
        raise RuntimeError("MULTIVIEW_AUDIT_TARGET_SYMLINK")
    if target.exists():
        if target.read_bytes() != raw:
            raise RuntimeError("MULTIVIEW_RECEIPT_CONFLICT")
        created = False
    else:
        fd, temp = tempfile.mkstemp(dir=folder, prefix=".private-multiview-")
        try:
            with os.fdopen(fd, "wb") as destination:
                destination.write(raw)
                destination.flush()
                os.fsync(destination.fileno())
            try:
                os.link(temp, target)
                created = True
            except FileExistsError:
                if target.read_bytes() != raw:
                    raise RuntimeError("MULTIVIEW_RECEIPT_CONFLICT")
                created = False
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
    print("MPW879_CANDIDATE_12VIEW_RECEIPT=" + json.dumps({
        "candidate_sha256": CANDIDATE_SHA,
        "receipt_sha256": receipt_hash,
        "created": created,
        "browser_and_accessibility_smoke_passed": receipt.get("browser_and_accessibility_smoke_passed"),
        "quality1000_verified": False,
    }, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "ingest":
        ingest()
    elif len(sys.argv) == 4 and sys.argv[1] == "audit":
        raise SystemExit(0 if audit(sys.argv[2], sys.argv[3]) else 2)
    else:
        raise SystemExit("USAGE_ERROR")
