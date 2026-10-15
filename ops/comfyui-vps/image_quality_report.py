#!/usr/bin/env python3
"""Deterministic QA and release-blocking report for CPU Studio PNG previews.

An image passing technical validation MUST NOT be interpreted as commercial-quality
approval. All Tiny-SD 256/512px previews are blocked from automatic publication.
Uses Pillow only for image decoding; no APIs, shell commands, networks, or secrets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageStat, UnidentifiedImageError

MAX_FILE_BYTES = 12_000_000
MAX_IMAGE_PIXELS = 8_000_000
MIN_COMMERCIAL_DIMENSION = 1024
VALID_PRESETS = frozenset(("orchard", "greenhouse", "product", "abstract"))
VALID_ENGINES = frozenset(("github-runner-cpu", "vps-comfyui-sse2"))


def _image_metrics(image: Image.Image) -> dict:
    """Diagnostic signals, deliberately NOT sale-approval scores."""
    gray = image.convert("L")
    hist = gray.histogram()
    total = sum(hist)
    entropy = -sum((n / total) * math.log2(n / total) for n in hist if n > 0)
    # A simple mean absolute neighbour-gradient; style-dependent and not a
    # substitute for evaluating composition, legibility, or subject fidelity.
    sample = gray.resize((min(256, gray.width), min(256, gray.height)))
    w, h = sample.size
    pixels = sample.load()
    total_diff = 0
    pair_count = 0
    for y in range(0, h - 1, 2):
        for x in range(0, w - 1, 2):
            v = pixels[x, y]
            total_diff += abs(v - pixels[x + 1, y])
            total_diff += abs(v - pixels[x, y + 1])
            pair_count += 2
    rgb = image.convert("RGB")
    means = [round(x, 2) for x in ImageStat.Stat(rgb).mean]
    return {
        "luma_entropy_bits": round(entropy, 3),
        "neighbor_gradient": round(total_diff / max(1, pair_count), 3),
        "mean_rgb": means,
    }


def report(
    png_path: Path,
    *,
    engine: str,
    preset: str,
    steps: int,
    run_id: str = "",
) -> dict:
    if engine not in VALID_ENGINES:
        raise ValueError("INVALID_ENGINE")
    if preset not in VALID_PRESETS:
        raise ValueError("INVALID_PRESET")
    if not isinstance(steps, int) or not (1 <= steps <= 30):
        raise ValueError("INVALID_STEPS")
    if png_path.is_symlink() or not png_path.is_file():
        raise ValueError("PNG_MISSING_OR_SYMLINK")
    size = png_path.stat().st_size
    if size < 1000 or size > MAX_FILE_BYTES:
        raise ValueError("PNG_SIZE_INVALID")
    data = png_path.read_bytes()
    if not data.startswith(bytes.fromhex("89504e470d0a1a0a")):
        raise ValueError("PNG_SIGNATURE_INVALID")
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    try:
        with Image.open(png_path) as im:
            if im.format != "PNG":
                raise ValueError("IMAGE_FORMAT_NOT_PNG")
            w, h = im.size
            if w < 32 or h < 32 or w * h > MAX_IMAGE_PIXELS:
                raise ValueError("IMAGE_DIMENSIONS_INVALID")
            im.load()
            metrics = _image_metrics(im)
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ValueError("PNG_DECODE_FAILED") from exc

    reasons = [
        "preview_checkpoint_not_approved_for_commercial_production",
        "manual_visual_review_not_performed",
        "copyright_and_source_license_review_not_completed",
        "human_factual_and_subject_review_not_completed",
    ]
    if min(w, h) < MIN_COMMERCIAL_DIMENSION:
        reasons.append("resolution_below_commercial_minimum")
    if steps < 15:
        reasons.append("few_diffusion_sampling_steps")
    if metrics["neighbor_gradient"] < 5.0:
        reasons.append("low_local_detail_signal_style_dependent")

    return {
        "schema": "saeit.comfyui.preview.qa.v1",
        "sha256": hashlib.sha256(data).hexdigest(),
        "file_bytes": size,
        "dimensions": {"width": w, "height": h},
        "source": {"engine": engine, "preset": preset, "steps": steps, "run_id": run_id},
        "technical_png_valid": True,
        "diagnostic_metrics": metrics,
        "quality_state": "EXPERIMENTAL_PREVIEW",
        "commercial_ready": False,
        "manual_review_required": True,
        "publish_allowed": False,
        "auto_store_upload_allowed": False,
        "block_reasons": reasons,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--engine", choices=sorted(VALID_ENGINES), required=True)
    parser.add_argument("--preset", choices=sorted(VALID_PRESETS), required=True)
    parser.add_argument("--steps", type=int, required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = report(args.image, engine=args.engine, preset=args.preset,
                    steps=args.steps, run_id=args.run_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("COMFY_QA_TECHNICAL_PNG_VERIFIED")
    print("COMFY_QA_SHA256=" + result["sha256"])
    print("COMFY_QA_QUALITY_STATE=" + result["quality_state"])
    print("COMFY_QA_PUBLISH_ALLOWED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
