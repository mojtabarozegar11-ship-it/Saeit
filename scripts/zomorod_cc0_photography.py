"""Curate *different* CC0 photographic examples for 17 duplicate Zomorod slots.

Owner-original photos and public URLs are preserved. This only changes an
unmerged corporate-design branch, never the live server. Source origin is
recorded; photos are examples, NOT documentation of company projects.

Modes:
  python scripts/zomorod_cc0_photography.py --preview
  python scripts/zomorod_cc0_photography.py --apply
Requires Pillow and outbound HTTPS to Openverse and photo hosts.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from html import escape
from io import BytesIO
import hashlib
import json
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from PIL import Image, ImageOps, UnidentifiedImageError

ROOT = Path(__file__).resolve().parents[1]
PHOTO_DIR = ROOT / "core/static/site/editorial"
CREDITS = ROOT / "docs/zomorod-cc0-editorial-photographs.json"
PREVIEW = ROOT / "zomorod-cc0-contact-sheet.jpg"
PAGES = [ROOT / "content/zomorod-new-home/index.html"] + [
    ROOT / f"content/zomorod-nova-pages/{name}.html"
    for name in ("about", "company", "services", "industry", "research", "knowledge")
]
# Order is the order in which repeated editorial images occur when scanning
# the homepage followed by the six specialist pages.
SLOTS = [
    ("farm-machinery", ("tractor", "farm"), "نمونه تصویری ماشین‌آلات و مدیریت مزرعه"),
    ("crop-economics", ("wheat", "agriculture"), "نمونه تصویری کشت و اقتصاد تولید محصولات"),
    ("water-soil", ("irrigation", "water"), "نمونه تصویری آبیاری، آب و خاک"),
    ("plant-genetics", ("microscope", "laboratory"), "نمونه تصویری پژوهش گیاهی و ژنتیک"),
    ("smart-systems", ("technology", "computer"), "نمونه تصویری فناوری و سامانه‌های هوشمند"),
    ("livestock", ("cattle", "dairy"), "نمونه تصویری مدیریت گله و دامپروری"),
    ("food-processing", ("vegetables", "factory"), "نمونه تصویری فرآوری و کنترل کیفیت خوراک"),
    ("digital-research", ("computer", "technology"), "نمونه تصویری فناوری اطلاعات و پژوهش"),
    ("economic-analysis", ("business", "finance"), "نمونه تصویری تحلیل اقتصادی و تصمیم‌سازی"),
    ("company-landscape", ("farm", "agriculture"), "نمونه تصویری منظر تولید و کشاورزی"),
    ("protected-cultivation", ("greenhouse", "plant"), "نمونه تصویری گلخانه و کشت کنترل‌شده"),
    ("professional-services", ("agriculture", "farm"), "نمونه تصویری خدمات تخصصی کشاورزی"),
    ("field-consulting", ("tractor", "field"), "نمونه تصویری عملیات و مشاوره مزرعه"),
    ("industrial-technology", ("factory", "industry"), "نمونه تصویری صنعت، ماشین‌آلات و تولید"),
    ("scientific-research", ("laboratory", "science"), "نمونه تصویری فعالیت علمی و آزمایشگاه"),
    ("microbiology", ("microscope", "science"), "نمونه تصویری ابزارهای بررسی علمی"),
    ("learning-resources", ("books", "library"), "نمونه تصویری کتابخانه و منابع آموزشی"),
]
IMG = re.compile(r"<img\b[^>]*>", re.IGNORECASE | re.DOTALL)
SRC = re.compile(r'\bsrc="([^"]+)"')
ALT = re.compile(r'\balt="([^"]*)"')
HEADERS = {
    "User-Agent": "ZomorodMelal/1.0 (non-commercial image discovery for a test branch; https://zomorodmelal.ir/)",
    "Accept": "application/json",
}
MAX_DOWNLOAD = 7 * 1024 * 1024


def get_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def search(query):
    params = urllib.parse.urlencode({
        "q": query, "license": "cc0", "category": "photograph", "page_size": 30,
        "mature": "false", "filter_dead": "true",
    })
    for attempt in range(2):
        try:
            data = get_json("https://api.openverse.org/v1/images/?" + params)
            return [
                entry for entry in data.get("results", [])
                if entry.get("license") == "cc0"
                and not entry.get("mature")
                and entry.get("url", "").startswith("https://")
                and isinstance(entry.get("width"), int)
                and isinstance(entry.get("height"), int)
                and entry["width"] >= 720 and entry["height"] >= 490
                and 1.10 < entry["width"] / entry["height"] < 2.7
                and entry.get("category") == "photograph"
            ]
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            print("CC0_SEARCH_RETRY", query, type(exc).__name__, flush=True)
            time.sleep(1.5 + attempt)
    return []


def get_photo(url):
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; ZomorodMelal/1.0)",
        "Accept": "image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8",
    })
    with urllib.request.urlopen(request, timeout=17) as resp:
        if urllib.parse.urlparse(resp.geturl()).scheme != "https":
            raise ValueError("Non-HTTPS image redirect")
        blob = resp.read(MAX_DOWNLOAD + 1)
        if len(blob) > MAX_DOWNLOAD:
            raise ValueError("Oversized source image")
    image = Image.open(BytesIO(blob))
    image.load()
    if image.width < 720 or image.height < 490:
        raise ValueError("Source dimensions too small")
    if image.width * image.height > 60_000_000:
        raise ValueError("Source pixels exceed safety limit")
    image = ImageOps.exif_transpose(image).convert("RGB")
    return ImageOps.fit(image, (960, 640), method=Image.Resampling.LANCZOS)


def dhash(img):
    grayscale = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(grayscale.getdata())
    acc = 0
    for y in range(8):
        for x in range(8):
            acc = (acc << 1) | (pixels[y * 9 + x] > pixels[y * 9 + x + 1])
    return acc


def safe_slug(text):
    return re.sub(r"[^a-z0-9-]+", "-", text.lower())[:90]


def inspect_duplicates():
    used = set()
    repeated = []
    for page in PAGES:
        markup = page.read_text(encoding="utf-8")
        for match in IMG.finditer(markup):
            tag = match.group()
            m = SRC.search(tag)
            if not m or "company-logo" in m.group(1):
                continue
            src = m.group(1)
            if src in used:
                repeated.append((page, src))
            else:
                used.add(src)
    return repeated


def collect():
    picked = []
    hashes = []
    occupied_urls = set()
    for idx, (slug, subjects, label) in enumerate(SLOTS, 1):
        selected = None
        for query in subjects:
            results = search(query)
            # StockSnap often provides well-lit horizontal editorial photography.
            # All chosen files must still pass independent pixel and license tests.
            results.sort(key=lambda x: (
                x.get("provider") != "stocksnap",
                query.lower() not in (
                    str(x.get("title", "")).lower() + " " +
                    " ".join(t.get("name", "") for t in x.get("tags", []))
                ),
                -(x.get("width", 0) * x.get("height", 0)),
            ))
            for entry in results[:18]:
                url = entry["url"]
                if url in occupied_urls:
                    continue
                try:
                    image = get_photo(url)
                except (urllib.error.URLError, TimeoutError, ValueError,
                        UnidentifiedImageError, OSError) as exc:
                    continue
                fingerprint = dhash(image)
                if any((fingerprint ^ old).bit_count() < 11 for old in hashes):
                    continue
                selected = (entry, image, fingerprint)
                break
            if selected:
                break
        if not selected:
            raise RuntimeError(f"Not enough distinct verified CC0 photos for {slug}")
        entry, image, fingerprint = selected
        occupied_urls.add(entry["url"])
        hashes.append(fingerprint)
        dest = PHOTO_DIR / f"{idx:02d}-{safe_slug(slug)}.webp"
        buffer = BytesIO()
        image.save(buffer, format="WEBP", quality=84, method=6)
        payload = buffer.getvalue()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)
        manifest_record = {
            "file": str(dest.relative_to(ROOT)),
            "url": "/static/site/editorial/" + dest.name,
            "label": label,
            "title": entry.get("title"),
            "creator": entry.get("creator"),
            "origin": entry.get("foreign_landing_url"),
            "source_url": entry["url"],
            "provider": entry.get("provider"),
            "license": entry.get("license"),
            "license_url": entry.get("license_url"),
            "original_id": entry.get("id"),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size": len(payload),
            "width": image.width,
            "height": image.height,
            "is_company_project_photo": False,
        }
        picked.append(manifest_record)
        print("CC0_SELECTED", f"{idx:02d}", slug, str(entry.get("title"))[:70],
              entry.get("provider"), len(payload), flush=True)
    return picked


def contact_sheet(picked):
    from PIL import ImageDraw
    w, h = 1440, ((len(picked) + 3) // 4) * 255
    canvas = Image.new("RGB", (w, h), (15, 34, 27))
    pen = ImageDraw.Draw(canvas)
    for i, item in enumerate(picked):
        x = (i % 4) * 360
        y = (i // 4) * 255
        with Image.open(ROOT / item["file"]) as image:
            thumb = ImageOps.fit(image, (344, 220))
            canvas.paste(thumb, (x + 8, y + 8))
        pen.text((x + 12, y + 232), f"{i+1:02d} {SLOTS[i][0]}", fill=(229, 206, 157))
    canvas.save(PREVIEW, "JPEG", quality=89)


def apply(picked):
    repeated = inspect_duplicates()
    if len(repeated) != len(SLOTS):
        raise RuntimeError(f"Expected {len(SLOTS)} duplicate placements, found {len(repeated)}")
    counts = defaultdict(int)
    kept = set()
    replacements = iter(picked)
    for page in PAGES:
        markup = page.read_text(encoding="utf-8")
        def replace(match):
            tag = match.group()
            src_match = SRC.search(tag)
            if not src_match or "company-logo" in src_match.group(1):
                return tag
            old = src_match.group(1)
            if old not in kept:
                kept.add(old)
                return tag
            item = next(replacements)
            counts[item["file"]] += 1
            tag = tag[:src_match.start(1)] + item["url"] + tag[src_match.end(1):]
            alt = ALT.search(tag)
            if alt:
                tag = tag[:alt.start(1)] + escape(item["label"], quote=True) + tag[alt.end(1):]
            return tag
        updated = IMG.sub(replace, markup)
        if len(updated) < len(markup) * 0.84:
            raise RuntimeError(f"Page was unexpectedly shortened: {page}")
        if updated != markup:
            page.write_text(updated, encoding="utf-8")
    if len(counts) != len(SLOTS) or not all(v == 1 for v in counts.values()):
        raise RuntimeError("Not all photo slots replaced exactly once")
    # Confirm all editorial photo references are now unique across all seven pages.
    if inspect_duplicates():
        raise RuntimeError("Repeated image URL remains")
    CREDITS.parent.mkdir(parents=True, exist_ok=True)
    CREDITS.write_text(
        json.dumps({
            "purpose": "Independent illustrative site imagery; not company project documentation",
            "license_policy": "Creative Commons CC0 only, metadata captured from Openverse",
            "photos": picked,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print("CC0_PHOTOS_IN_REPOSITORY", len(picked), "DUPLICATES_REMAINING", 0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.preview == args.apply:
        raise SystemExit("Choose --preview or --apply")
    found = inspect_duplicates()
    if len(found) != len(SLOTS):
        raise SystemExit(f"Expected {len(SLOTS)} duplicate placements, found {len(found)}; abort")
    picked = collect()
    contact_sheet(picked)
    if args.apply:
        apply(picked)
    else:
        print("PREVIEW_ONLY=YES; no HTML changed, no live site touched", flush=True)


if __name__ == "__main__":
    main()
