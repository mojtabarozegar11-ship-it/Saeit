#!/usr/bin/env python3
"""Install/remove static English game entry pages in the MojPlayWin document root."""
from pathlib import Path
import html
import sys

DOCROOT = Path("/home/zomorod2/mojplaywin.com")
BRANDS = [
    ("saman", "SAMAN"), ("zahra", "ZAHRA"), ("zhila", "ZHILA"),
    ("marzieh", "MARZIEH"), ("maryam", "MARYAM"), ("marjan", "MARJAN"),
    ("faremah", "FAREMAH"), ("farnaz", "FARNAZ"), ("taniya", "TANIYA"),
    ("raham", "RAHAM"), ("mojtaba", "MOJTABA"), ("mohammad", "MOHAMMAD"),
    ("mostafa", "MOSTAFA"), ("17", "17"), ("21", "21"), ("206", "206"),
    ("108", "108"),
]
MARKER = "data-mojplaywin-game-subsite"

def page(slug, name):
    safe = html.escape(name)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{safe} game subsite by MojPlayWin">
<title>{safe} · Game world · MojPlayWin</title>
<style>body{{margin:0;background:#101b1d;color:#f7f0e5;font-family:Arial,sans-serif}}main{{max-width:980px;margin:auto;padding:12vh 8vw}}.eyebrow{{color:#d9bd78;letter-spacing:.16em;text-transform:uppercase}}h1{{font:700 clamp(2.8rem,8vw,6rem) Georgia,serif;margin:22px 0}}p{{font-size:1.15rem;line-height:1.8;max-width:650px}}a{{display:inline-block;margin-top:22px;background:#d9bd78;color:#101b1d;padding:14px 22px;border-radius:999px;text-decoration:none;font-weight:700}}</style>
</head><body><main {MARKER}="true"><div class="eyebrow">MojPlayWin · Game world</div><h1>{safe}</h1><p>A dedicated game subsite for play, learning, and interaction. No financial asset or in-game purchase is presented until officially activated.</p><a href="/game-factory/">Explore MojPlayWin games ↗</a></main></body></html>
"""

def install():
    for slug, name in BRANDS:
        target = DOCROOT / slug / "game" / "index.html"
        if target.exists() and MARKER not in target.read_text(encoding="utf-8", errors="ignore"):
            raise RuntimeError(f"Refusing to replace existing non-game path: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page(slug, name), encoding="utf-8")
    print("MOJPLAYWIN_GAME_STATIC_INSTALLED=17")

def remove():
    removed = 0
    for slug, _ in BRANDS:
        target = DOCROOT / slug / "game" / "index.html"
        if target.is_file() and MARKER in target.read_text(encoding="utf-8", errors="ignore"):
            target.unlink()
            removed += 1
            try:
                target.parent.rmdir()
                target.parent.parent.rmdir()
            except OSError:
                pass
    print(f"MOJPLAYWIN_GAME_STATIC_REMOVED={removed}")

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"install", "remove"}:
        raise SystemExit("usage: install_game_static_pages.py install|remove")
    install() if sys.argv[1] == "install" else remove()
