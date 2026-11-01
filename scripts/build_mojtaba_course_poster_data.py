"""Package ten owner-identity course posters into the existing Python-only deploy flow.

The current cPanel updater rejects non-Python files inside social_hub. This
reproducible packager exports optimized WebP and a bounded embedded-data module
without weakening that update allowlist.
"""
from __future__ import annotations

import base64
import hashlib
import io
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "mojtaba_course_posters_20261031"
DEST = ROOT / "social_hub" / "course_image_data.py"
NAMES = (
    ("business", "01-business"),
    ("agriculture", "02-agriculture"),
    ("online-income", "03-online-income"),
    ("chatgpt", "04-chatgpt"),
    ("research-methods", "05-research-methods"),
    ("feasibility", "06-feasibility"),
    ("digital-marketing", "07-digital-marketing"),
    ("business-finance", "08-business-finance"),
    ("food-quality", "09-food-quality"),
    ("ai-automation", "10-ai-automation"),
)


def build() -> None:
    output = [
        '"""Generated, owner-reference, full-scene 2026-10-31 course imagery. Do not hand-edit."""',
        "BASE64_POSTERS = {",
    ]
    hashes = {}
    for slug, name in NAMES:
        source = ASSETS / f"{name}.png"
        with Image.open(source) as im:
            if im.size != (1122, 1402):
                raise RuntimeError(f"Unexpected poster size: {source}: {im.size}")
            rgb = im.convert("RGB")
            rgb = rgb.resize((900, 1125), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        rgb.save(buf, "WEBP", quality=79, method=6)
        raw = buf.getvalue()
        if not 30_000 < len(raw) < 280_000:
            raise RuntimeError(f"Unexpected WebP size: {name}: {len(raw)}")
        (ASSETS / f"{name}.webp").write_bytes(raw)
        hashes[slug] = hashlib.sha256(raw).hexdigest()
        text = base64.b64encode(raw).decode("ascii")
        output.append(f"    {slug!r}: (")
        for i in range(0, len(text), 112):
            output.append(f"        {text[i:i+112]!r}")
        output.append("    ),")
    output.append("}")
    output.append("SHA256_POSTERS = {")
    for slug, _ in NAMES:
        output.append(f"    {slug!r}: {hashes[slug]!r},")
    output.extend(["}", ""])
    DEST.write_text("\n".join(output), encoding="ascii")


if __name__ == "__main__":
    build()
