#!/usr/bin/env python3
"""Build offline, read-only viewport previews of existing MojPlayWin main pages.

Runs on GitHub CI with a test-only Django client. Never calls the production
website, mutates the database, logs into admin, or visits any independent subsite.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import unquote

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.test import Client, override_settings  # noqa: E402


ROUTES = {
    "home": "/",
    "store": "/store/",
    "research": "/research/",
    "agents": "/agents/",
    "restaurant": "/ventures/cafe-restaurant/",
    "ai": "/ai/",
    "blockchain": "/blockchain/",
    "support": "/support/",
}
MAIN_HOST = "mojplaywin.com"
OUTPUT = Path("mojplaywin-v4-visual-preview")
FILE_PATH_RE = re.compile(r'(["\'])/static/([^"\']+)\1')


def rewrite_local_static(html: str, copied: set[str], static_root: Path) -> str:
    def replace(match):
        relative = unquote(match.group(2)).split('?', 1)[0].split('#', 1)[0]
        if relative.startswith("/") or ".." in Path(relative).parts or "\\" in relative:
            raise ValueError("unsafe static asset path")
        src = static_root / relative
        if not src.is_file():
            raise FileNotFoundError(f"uncollected static asset: {relative}")
        dest = OUTPUT / "static" / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        if relative not in copied:
            shutil.copyfile(src, dest)
            copied.add(relative)
        return match.group(1) + "static/" + relative + match.group(1)
    return FILE_PATH_RE.sub(replace, html)


def make_html_snapshots():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    static_root = Path(settings.STATIC_ROOT).resolve()
    if not static_root.is_dir():
        raise RuntimeError("collectstatic must run first")
    copied: set[str] = set()
    manifest = {}
    # This URLConf exists for previews only. Production route configuration is unchanged.
    with override_settings(ROOT_URLCONF="core.mojplaywin_atelier_preview_urls"):
        client = Client()
        for key, route in ROUTES.items():
            response = client.get(route, HTTP_HOST=MAIN_HOST)
            if response.status_code != 200:
                raise RuntimeError(f"{route} unexpectedly returned {response.status_code}")
            html = response.content.decode("utf-8")
            expected_canonical = f'<link rel="canonical" href="https://{MAIN_HOST}{route}">'
            if expected_canonical not in html:
                raise RuntimeError(f"unexpected canonical for {route}")
            if "mojplaywin-atelier-v4" not in html:
                raise RuntimeError(f"new template missing from {route}")
            document = rewrite_local_static(html, copied, static_root).replace('loading="lazy"', 'loading="eager"')
            (OUTPUT / f"{key}.html").write_text(document, encoding="utf-8")
            manifest[key] = {
                "path": route,
                "filename": f"{key}.html",
                "bytes": len(document),
                "source": "representative_preview_not_live"
                    if key in ("ai", "blockchain", "support") else "version_controlled_route",
            }
    (OUTPUT / "manifest.json").write_text(
        json.dumps({
            "host": MAIN_HOST,
            "preview_only": True,
            "production_routes_unchanged": True,
            "unversioned_live_routes": ["/ai/", "/blockchain/", "/support/"],
            "routes": manifest,
            "local_assets": len(copied)
        }, indent=2), encoding="utf-8",
    )
    return manifest

def capture_viewports(manifest):
    from playwright.sync_api import sync_playwright

    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            for key, detail in manifest.items():
                for mode, width, height in [("desktop", 1440, 900), ("mobile", 390, 844)]:
                    page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
                    page.goto((OUTPUT / detail["filename"]).resolve().as_uri(), wait_until="load")
                    page.wait_for_function(
                        "() => [...document.images].every(i => i.complete)",
                        timeout=15000,
                    )
                    page.screenshot(path=str(OUTPUT / f"{key}-{mode}.png"), full_page=True, animations="disabled")
                    stats = page.evaluate("""() => ({
                        title: document.title,
                        h1Count: document.querySelectorAll('main h1').length,
                        imageCount: document.querySelectorAll('main img').length,
                        brokenImages: [...document.querySelectorAll('img')]
                           .filter(img => !img.complete || !img.naturalWidth)
                           .map(img => img.getAttribute('src')).slice(0, 10),
                        overflow: document.documentElement.scrollWidth > innerWidth + 5,
                        scrollWidth: document.documentElement.scrollWidth
                    })""")
                    if key == "home":
                        nav = page.locator("#mw-all-pages-menu")
                        nav.locator("summary").click()
                        if not nav.locator(".mw-nav-panel").is_visible():
                            raise RuntimeError(f"{key}-{mode}: Explore all menu did not open")
                        menu_width = page.evaluate("document.documentElement.scrollWidth")
                        if menu_width > width + 5:
                            raise RuntimeError(f"{key}-{mode}: menu causes horizontal overflow")
                    results[f"{key}-{mode}"] = stats
                    page.close()
        finally:
            browser.close()
    (OUTPUT / "visual-qa.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    for name, stats in results.items():
        if stats["brokenImages"]:
            raise RuntimeError(f"{name}: broken images: {stats['brokenImages']}")
        if stats["overflow"]:
            raise RuntimeError(f"{name}: horizontal overflow ({stats['scrollWidth']})")
        if stats["h1Count"] != 1:
            raise RuntimeError(f"{name}: unexpected H1 count: {stats['h1Count']}")
    return results


if __name__ == "__main__":
    manifest = make_html_snapshots()
    result = capture_viewports(manifest)
    print(f"MOJPLAYWIN_VISUAL_QA routes={len(manifest)} viewports={len(result)}")
