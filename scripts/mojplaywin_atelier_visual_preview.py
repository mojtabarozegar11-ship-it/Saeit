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
    "web_engineering": "/services/",
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
            document = rewrite_local_static(html, copied, static_root)
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
                    # Only visual QA expands below-fold sections and loads all images
                    # so that full-page screenshots show the COMPLETE preserved content.
                    # Lighthouse separately audits the UNMODIFIED optimized HTML.
                    if key == "home":
                        page.add_style_tag(content="""
                            .mojplaywin-home .mw-shell[data-deferred-legacy="true"] > *,
                            .mojplaywin-home .mpo-orbits > .mpo-ring {
                                content-visibility: visible !important;
                            }
                        """)
                    page.evaluate("() => [...document.images].forEach(img => { img.loading = 'eager'; })")
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
                    if key == "research":
                        active_image = page.locator(".mpx-page-hero-art img").evaluate("(img) => img.currentSrc")
                        if mode == "mobile" and "research-nexus." not in active_image:
                            raise RuntimeError("research-mobile: optimized research image not selected")
                        if mode == "desktop" and "research." not in active_image:
                            raise RuntimeError("research-desktop: original photo not preserved")
                    if key == "home":
                        main_cta_color = page.locator(".mpo-experience .mpo-btn-primary").evaluate(
                            "(button) => getComputedStyle(button).color"
                        )
                        channels = [int(x) for x in re.findall(r"\d+", main_cta_color)[:3]]
                        if len(channels) != 3 or max(channels) > 85:
                            raise RuntimeError(
                                f"{key}-{mode}: low-contrast gold CTA text: {main_cta_color}"
                            )
                        if page.locator("[data-mojplaywin-orbital='v1']").count() != 1:
                            raise RuntimeError(f"{key}-{mode}: approved orbital experience absent")
                        if page.locator(".mpo-ring").count() != 3:
                            raise RuntimeError(f"{key}-{mode}: expected exactly three independent orbits")
                        if page.locator(".mpo-orbit-card").count() != 18:
                            raise RuntimeError(f"{key}-{mode}: all eighteen service cards required")
                        first = page.locator("[data-orbit='web'] .mpo-orbit-track")
                        page.locator("[data-orbit='web'] [data-orbit-next]").click()
                        page.wait_for_function(
                            "() => document.querySelector('[data-orbit=web] .mpo-orbit-track').scrollLeft > 2",
                            timeout=3000,
                        )
                        first.focus()
                        # Accessible keyboard navigation should scroll within the ring.
                        page.locator("[data-orbit='web'] [data-orbit-prev]").click()
                        page.wait_for_function(
                            "() => document.querySelector('[data-orbit=web] .mpo-orbit-track').scrollLeft < 2",
                            timeout=3000,
                        )
                        first.focus()
                        page.keyboard.press("ArrowRight")
                        page.wait_for_function(
                            "() => document.querySelector('[data-orbit=web] .mpo-orbit-track').scrollLeft > 2",
                            timeout=3000,
                        )
                        toggle = page.locator("[data-orbit-toggle]")
                        if toggle.is_enabled():
                            toggle.click()
                            if toggle.get_attribute("aria-pressed") != "true":
                                raise RuntimeError(f"{key}-{mode}: motion control failed to start")
                            toggle.click()
                            if toggle.get_attribute("aria-pressed") != "false":
                                raise RuntimeError(f"{key}-{mode}: motion control failed to pause")
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
