#!/usr/bin/env python3
"""Build a local photo bundle for /mohammad/ without modifying any other site.

External Unsplash photos are cached in the deployment checkout, and HTML references
are rewritten only inside public/mohammad. A failed download receives a labelled,
distinct local SVG fallback; a widespread CDN failure aborts before publishing.
"""
from __future__ import annotations

import concurrent.futures
import html
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

PHOTO_URL = re.compile(r"https://images\.unsplash\.com/(photo-\d+-[a-z0-9]+)(?:\?[^\"'<>\s]*)?")
USER_AGENT = "Mozilla/5.0 (compatible; MohammadBuildingClinic/1.0; photo-cache)"
MAX_BYTES = 8_000_000
MIN_PHOTO_RATIO = 0.70


def fetch_jpeg(pid: str) -> tuple[str, bytes | None, str]:
    errors = []
    for width in (1100, 820):
        url = f"https://images.unsplash.com/{pid}?fm=jpg&fit=crop&w={width}&q=73"
        for retry in range(2):
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": USER_AGENT, "Accept": "image/jpeg"}
                )
                with urllib.request.urlopen(req, timeout=18) as response:
                    mime = response.headers.get("Content-Type", "").split(";")[0].lower()
                    data = response.read(MAX_BYTES + 1)
                    if not (mime in ("image/jpeg", "image/jpg")
                            and 3500 < len(data) <= MAX_BYTES
                            and data[:3] == b"\xff\xd8\xff"):
                        raise ValueError(f"Invalid JPEG: {mime}, bytes={len(data)}")
                    return pid, data, ""
            except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
                errors.append(f"{width}:{type(exc).__name__}:{str(exc)[:80]}")
                if retry == 0:
                    time.sleep(0.3)
    return pid, None, " ; ".join(errors[-2:])


def svg_fallback(pid: str) -> str:
    # Different, local, lightweight illustration for offline availability.
    palettes = [
        ("#142a3b", "#a6b6b8", "#d6aa64"),
        ("#263328", "#a7c4ac", "#e9c38c"),
        ("#2c252e", "#b8aab5", "#c69a55"),
        ("#1e3141", "#afbec8", "#e2bc80"),
    ]
    variant = sum(ord(c) for c in pid) % len(palettes)
    dark, light, gold = palettes[variant]
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 760" role="img" '
        'aria-label="تصویر گرافیکی جایگزین ساختمان">'
        f'<rect width="1200" height="760" fill="{dark}"/>'
        f'<circle cx="{860 - variant * 50}" cy="180" r="158" fill="{gold}" opacity=".12"/>'
        '<g fill="none" stroke-width="7">'
        f'<path d="M80 635H1130" stroke="{gold}" opacity=".65"/>'
        f'<path d="M185 635V270L430 135 675 270V635" stroke="{light}"/>'
        f'<path d="M315 635V415H540V635" stroke="{light}"/>'
        f'<path d="M750 635V235H1020V635" stroke="{gold}"/>'
        f'<path d="M820 310H950M820 410H950M820 510H950" stroke="{light}"/>'
        '</g><text x="600" y="708" font-family="sans-serif" font-size="25" '
        f'text-anchor="middle" fill="{light}">BUILDING CLINIC · ILLUSTRATIVE PLACEHOLDER</text>'
        f'<desc>Photo unavailable for media asset {pid}</desc>'
        '</svg>'
    )


def main() -> None:
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "public/mohammad").resolve()
    if root.name != "mohammad" or not (root / ".htaccess").is_file():
        raise SystemExit("Refusing target other than the established Mohammad subsite")
    pages = sorted(root.rglob("*.html"))
    references: dict[pathlib.Path, str] = {}
    photo_ids: set[str] = set()
    for page in pages:
        content = page.read_text(encoding="utf-8")
        references[page] = content
        photo_ids.update(PHOTO_URL.findall(content))
    if not photo_ids:
        raise SystemExit("No remote photos found; refusing unverified image release")
    asset_dir = root / "assets" / "photos"
    asset_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, tuple[bytes | None, str]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for pid, data, error in executor.map(fetch_jpeg, sorted(photo_ids)):
            results[pid] = (data, error)
    photos_ok = sum(data is not None for data, _ in results.values())
    ratio = photos_ok / len(photo_ids)
    print(f"MOHAMMAD_PHOTOS_SOURCE_COUNT={len(photo_ids)}", flush=True)
    print(f"MOHAMMAD_PHOTOS_DOWNLOADED={photos_ok}", flush=True)
    print(f"MOHAMMAD_PHOTOS_FALLBACKS={len(photo_ids) - photos_ok}", flush=True)
    if ratio < MIN_PHOTO_RATIO:
        print("Image CDN failures prevented a safe deployment:", flush=True)
        for pid, (data, err) in results.items():
            if data is None:
                print(f"  {pid}: {err}", flush=True)
        raise SystemExit(f"Insufficient real photos ({ratio:.0%}); keeping existing live page")
    ext: dict[str, str] = {}
    for pid, (data, error) in results.items():
        if data is not None:
            target = asset_dir / f"{pid}.jpg"
            target.write_bytes(data)
            ext[pid] = "jpg"
        else:
            target = asset_dir / f"{pid}.svg"
            target.write_text(svg_fallback(pid), encoding="utf-8")
            ext[pid] = "svg"
            print(f"PHOTO_PLACEHOLDER={pid} reason={error}", flush=True)
    for page, original in references.items():
        updated = PHOTO_URL.sub(
            lambda m: f"/mohammad/assets/photos/{m.group(1)}.{ext[m.group(1)]}", original
        )
        if "https://images.unsplash.com/" in updated:
            raise SystemExit(f"Unrewritten source URL in {page}")
        if updated != original:
            page.write_text(updated, encoding="utf-8")
    assert len(list(asset_dir.iterdir())) == len(photo_ids)
    manifest = {
        "photo_count": photos_ok,
        "fallback_count": len(photo_ids) - photos_ok,
        "files": {pid: f"{pid}.{ext[pid]}" for pid in sorted(photo_ids)},
    }
    (asset_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"MOHAMMAD_PHOTO_BUNDLE=ready; pages={len(pages)}", flush=True)


if __name__ == "__main__":
    main()
