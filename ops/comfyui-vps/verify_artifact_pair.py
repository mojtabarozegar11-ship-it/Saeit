#!/usr/bin/env python3
"""Fail-closed provenance verification for public demo ComfyUI PNG artifacts.

Every Image Studio artifact pair must contain a decodable preview PNG and
matching quality_report.json with commercial release disabled. An artifact
passing this check is *not* a commercial approval.
No external services, tokens, approvals, or upload privileges required.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

EXPECTED_SCHEMA = "saeit.comfyui.preview.qa.v1"
ENGINES = {"github-runner-cpu", "vps-comfyui-sse2"}
PRESETS = {"orchard", "greenhouse", "product", "abstract"}
MAX_BYTES = 12_000_000
MAX_PIXELS = 8_000_000


class ArtifactIntegrityError(ValueError):
    pass


def verify_pair(image: Path, report_path: Path, *, expected_engine: str | None = None) -> dict:
    if image.is_symlink() or report_path.is_symlink():
        raise ArtifactIntegrityError("SYMLINK_NOT_ACCEPTED")
    if not image.is_file() or not report_path.is_file():
        raise ArtifactIntegrityError("MISSING_IMAGE_OR_REPORT")
    if image.stat().st_size > MAX_BYTES or report_path.stat().st_size > 200_000:
        raise ArtifactIntegrityError("FILE_SIZE_EXCEEDS_LIMIT")
    png = image.read_bytes()
    if len(png) < 1000 or png[:8] != bytes.fromhex("89504e470d0a1a0a"):
        raise ArtifactIntegrityError("INVALID_PNG_SIGNATURE_OR_SIZE")
    if png[12:16] != b"IHDR" or len(png) < 33:
        raise ArtifactIntegrityError("INVALID_PNG_IHDR")
    width, height = struct.unpack(">II", png[16:24])
    if not 32 <= width <= 8_000 or not 32 <= height <= 8_000 or width * height > MAX_PIXELS:
        raise ArtifactIntegrityError("INVALID_PNG_DIMENSIONS")
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ArtifactIntegrityError("INVALID_JSON_REPORT") from exc
    if not isinstance(payload, dict) or payload.get("schema") != EXPECTED_SCHEMA:
        raise ArtifactIntegrityError("UNKNOWN_REPORT_SCHEMA")
    source = payload.get("source")
    if not isinstance(source, dict):
        raise ArtifactIntegrityError("MISSING_PROVENANCE")
    if source.get("engine") not in ENGINES or (expected_engine is not None and source.get("engine") != expected_engine):
        raise ArtifactIntegrityError("UNTRUSTED_ENGINE")
    if source.get("preset") not in PRESETS or type(source.get("steps")) is not int or not (1 <= source["steps"] <= 30):
        raise ArtifactIntegrityError("INVALID_PRESET_OR_STEPS")
    if payload.get("technical_png_valid") is not True:
        raise ArtifactIntegrityError("IMAGE_TECHNICAL_VALIDATION_NOT_CONFIRMED")
    if payload.get("quality_state") != "EXPERIMENTAL_PREVIEW":
        raise ArtifactIntegrityError("UNRECOGNIZED_QUALITY_STATE")
    for field in ("publish_allowed", "commercial_ready", "auto_store_upload_allowed"):
        if payload.get(field) is not False:
            raise ArtifactIntegrityError("UNSAFE_COMMERCIAL_RELEASE_FLAG:" + field)
    if payload.get("manual_review_required") is not True:
        raise ArtifactIntegrityError("HUMAN_REVIEW_REQUIRED")
    if payload.get("file_bytes") != len(png):
        raise ArtifactIntegrityError("IMAGE_BYTE_COUNT_MISMATCH")
    if payload.get("dimensions") != {"width": width, "height": height}:
        raise ArtifactIntegrityError("IMAGE_DIMENSIONS_MISMATCH")
    digest = hashlib.sha256(png).hexdigest()
    if payload.get("sha256") != digest:
        raise ArtifactIntegrityError("PNG_SHA256_MISMATCH")
    reasons = payload.get("block_reasons")
    if not isinstance(reasons, list) or not reasons or not all(isinstance(r, str) for r in reasons):
        raise ArtifactIntegrityError("COMMERCIAL_BLOCK_REASON_MISSING")
    return {
        "source": source,
        "dimensions": {"width": width, "height": height},
        "sha256": digest,
        "publish_allowed": False,
        "commercial_ready": False,
        "preview_valid": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--engine", choices=sorted(ENGINES), required=True)
    args = parser.parse_args()
    verified = verify_pair(args.image, args.report, expected_engine=args.engine)
    print("COMFY_ARTIFACT_IMAGE_AND_QA_PAIR_VERIFIED")
    print("COMFY_ARTIFACT_SHA256=" + verified["sha256"])
    print("COMFY_ARTIFACT_PUBLIC_DEMO_ONLY")
    print("COMFY_ARTIFACT_STORE_RELEASE_BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
