#!/usr/bin/env python3
"""Build a static, additive MojPlayWin About page; no production server writes.

Reads the three editorial sources from the draft PR, preserves the entire
existing live About HTML, and injects static text-only company dossiers.
"""
import argparse
import hashlib
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

ABOUT_URL = "https://mojplaywin.com/about/"
EXPECTED_SECTION_TITLES = ("The complementary 20%", "Research-grade company dossier",
                           "Mojtaba Roozegar", "Food science, processing and functional nutrition")


def load_text(path):
    return Path(path).read_text(encoding="utf-8")


def strip_template_comments(data):
    return re.sub(r"\{#.*?#\}", "", data, flags=re.S)


def check_static(data, label):
    if re.search(r"\{%|\{\{|\{#", data):
        raise RuntimeError(f"{label}: unrendered Django template token")
    if "<script" in data.lower() or "<iframe" in data.lower():
        raise RuntimeError(f"{label}: executable/embedded HTML unsupported in static content")
    return data


def inject_about(original, about, research, complementary, theme):
    if "<!doctype" not in original.lower() or "Original by Default" not in original:
        raise RuntimeError("Public About content changed; original live HTML signature mismatch")
    if len(original) < 1000 or len(original) > 1_500_000:
        raise RuntimeError("Public About HTML unexpected length")
    if original.lower().count("<main") != 1 or original.lower().count("</main>") != 1:
        raise RuntimeError("About has no single accessible main element")
    if re.search(r"<form\b", original, flags=re.I):
        raise RuntimeError("Existing About has a form; static capture might break interactive behavior")
    if 'COMPLEMENTARY SPECIALISM 30' in original:
        raise RuntimeError("Live About already appears to contain this edition")

    start = about.index('<div class="mw-shell">')
    first_end = about.index('{% include "mojplaywin/about_research_dossier.html" %}', start)
    part = about[start:first_end]
    if '{% include' in part:
        raise RuntimeError("Unexpected nested Django includes within About body")
    # The Django template's final wrapper closes immediately after its includes.
    end_fragment = strip_template_comments(research) + "\n" + strip_template_comments(complementary) + "\n</div>"
    editorial = check_static(part + end_fragment, "editorial content")
    editorial = editorial.replace('<div class="mw-shell">', '<div class="mpw-company-about mw-shell">', 1)
    # The preserved original public About page already has a document H1.
    editorial = editorial.replace("<h1>About MojPlayWin</h1>", "<h2>Our complete company profile</h2>", 1)

    style_match = re.search(r"<style>(.*?)</style>", about, flags=re.S | re.I)
    if style_match is None:
        raise RuntimeError("Missing About-specific styling")
    about_style = style_match.group(1)
    theme_match = re.search(r'(<style id="mojplaywin-matte-gold-theme">.*?</style>)', theme, flags=re.S | re.I)
    if theme_match is None:
        raise RuntimeError("Missing known MojPlayWin theme stylesheet")
    # The old page's original navbar/footer retain their functionality. The
    # new copy receives namespace-scoped additions; existing pages are unchanged.
    about_style = about_style.replace("body.mojplaywin-about", ".mpw-company-about")
    advanced_styles = f"\n<style id='mpw-about-advanced-style'>{about_style}\n"
    advanced_styles += ".mpw-company-about .mw-page-hero>h2{max-width:24ch;font-size:clamp(2rem,4vw,4rem);color:var(--mw-cream)}\n"
    advanced_styles += ".mpw-company-about .mw-shell{max-width:1240px}\n"
    advanced_styles += "</style>\n"
    extra = theme_match.group(1) + advanced_styles
    # Never change original main semantics or navigation; insert only append-only
    # editorial content, including links to existing pages.
    main_open = re.search(r"<main\b[^>]*>", original, flags=re.I)
    if not main_open:
        raise RuntimeError("Original About main disappeared")
    assembled = original[:main_open.end()] + "\n<!-- MPW_ABOUT_RESEARCH_80_20_V1 -->\n" + editorial + "\n" + original[main_open.end():]
    assembled = re.sub(r"</head\s*>", extra + "\n</head>", assembled, count=1, flags=re.I)
    assembled, title_count = re.subn(
        r"<title>[^<]*</title>",
        "<title>About MojPlayWin | Scientific, Digital &amp; Complementary Business Profile</title>",
        assembled, count=1, flags=re.I)
    if title_count != 1:
        raise RuntimeError("Cannot update SEO title")
    assembled = re.sub(
        r'(<meta\s+name=["\x27]description["\x27]\s+content=["\x27])[^"\x27]*(["\x27]\s*/?>)',
        r"\g<1>MojPlayWin comprehensive research-grade About profile: AI, software, games, education, founder Mojtaba Roozegar and 10 complementary economic sectors.\g<2>",
        assembled, count=1, flags=re.I)
    # Add one primary canonical if live markup already has one (retain it).
    if 'https://mojplaywin.com/about/' not in assembled:
        raise RuntimeError("Original About canonical reference missing")
    check_terms = ["SPECIALISM 28", "COMPLEMENTARY SPECIALISM 30",
                   "STRATEGIC 20%", "about_research_dossier"]
    for term in check_terms:
        if term == "about_research_dossier":
            if term in assembled:
                raise RuntimeError("A Django include escaped into static page")
        elif term not in assembled:
            raise RuntimeError(f"Missing expected sector evidence: {term}")
    for term in EXPECTED_SECTION_TITLES:
        if term not in assembled:
            raise RuntimeError("Missing edited article content: " + term)
    if assembled.count("<main") != 1 or assembled.count("</main>") != 1:
        raise RuntimeError("Main landmarks changed")
    if "<% " in assembled or "{% " in assembled:
        raise RuntimeError("Template syntax escaped")
    if len(assembled) < 50_000 or len(assembled) > 700_000:
        raise RuntimeError("Generated static page length outside expected safety envelope")
    return assembled


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--output", required=True)
    a = parser.parse_args()
    source = Path(a.source_dir)
    req = urllib.request.Request(ABOUT_URL + "?__mpw_about_snapshot=20261018", headers={
        "Cache-Control": "no-cache", "User-Agent": "MojPlayWinIsolatedAboutRelease/1.0"})
    with urllib.request.urlopen(req, timeout=20) as response:
        if response.status != 200 or "text/html" not in response.headers.get("Content-Type",""):
            raise RuntimeError("Public About returned an unexpected response")
        original = response.read(1_500_001).decode("utf-8", "replace")
    page = inject_about(
        original,
        load_text(source / "about.html"),
        load_text(source / "about_research_dossier.html"),
        load_text(source / "about_complementary_portfolio.html"),
        load_text(source / "theme.html"),
    )
    target = Path(a.output)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(page,encoding="utf-8")
    print(json.dumps({
        "classification":"MPW_ABOUT_STATIC_BUILD_READY",
        "output_bytes":target.stat().st_size,
        "output_sha256":hashlib.sha256(target.read_bytes()).hexdigest(),
        "original_bytes":len(original.encode("utf-8")),
        "preserved_original_content":True,
        "research_sections":28,
        "complementary_sections":30,
        "no_payments_or_database_mutation":True,
    }))

if __name__ == "__main__":
    main()
