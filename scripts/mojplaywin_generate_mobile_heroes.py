#!/usr/bin/env python3
"""Create original-photo *responsive copies* for MojPlayWin, without touching originals.

The source photographs are already in core/static/site/heroes/*.webp.
Only smaller 560px WebP derivative assets under MojPlayWin's own static
namespace may be created; no protected sites, DB, products, wallets or routes.
Run at source maintenance time, NOT on production shared Passenger hosts.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
ORIGINALS = ROOT / "core/static/site/heroes"
OUTPUT = ROOT / "core/static/site/mojplaywin-atelier/mobile-heroes"
SOURCE_NAMES = (
    "about", "academy", "agriculture", "ai", "auctions", "blog", "contact",
    "economy", "education-detail", "game-studio", "genetics", "industry",
    "knowledge", "laboratory", "marketplace", "newsletter", "platform-home",
    "research", "services", "smart-agriculture", "store", "weather",
)
MAX_WIDTH = 560
MAX_BYTES = 45000
QUALITY = 67


def convert(name: str, *, persist: bool = True) -> dict:
    if name not in SOURCE_NAMES or "/" in name or "\\" in name:
        raise ValueError("unapproved image basename")
    source = ORIGINALS / (name + ".webp")
    if not source.is_file():
        raise FileNotFoundError(f"Missing original: {source}")
    with Image.open(source) as raw:
        raw.load()
        original_size = raw.size
        if raw.width < 1 or raw.height < 1:
            raise ValueError("invalid original image")
        image = ImageOps.exif_transpose(raw).convert("RGB")
    image.thumbnail((MAX_WIDTH, 500), Image.Resampling.LANCZOS)
    encoded = io.BytesIO()
    image.save(encoded, format="WEBP", quality=QUALITY, method=6)
    data = encoded.getvalue()
    if len(data) > MAX_BYTES:
        raise ValueError(f"mobile image too heavy ({len(data)} bytes): {name}")
    if image.size[0] > MAX_WIDTH:
        raise ValueError("mobile dimensions too large")
    dest = OUTPUT / (name + ".webp")
    if persist:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists() or dest.read_bytes() != data:
            dest.write_bytes(data)
    return {
        "name": name,
        "original_bytes": source.stat().st_size,
        "mobile_bytes": len(data),
        "original_size": original_size,
        "mobile_size": image.size,
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    options = parser.parse_args()
    results = [convert(name, persist=not options.check_only) for name in SOURCE_NAMES]
    if options.check_only:
        for x in results:
            file = OUTPUT / (x["name"] + ".webp")
            if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != x["sha256"]:
                raise SystemExit("Missing or stale mobile image: " + x["name"])
    print(json.dumps({
        "image_count": len(results),
        "originals_unchanged": True,
        "total_original_bytes": sum(x["original_bytes"] for x in results),
        "total_mobile_bytes": sum(x["mobile_bytes"] for x in results),
        "max_mobile_bytes": max(x["mobile_bytes"] for x in results),
    }, indent=2))


if __name__ == "__main__":
    main()
