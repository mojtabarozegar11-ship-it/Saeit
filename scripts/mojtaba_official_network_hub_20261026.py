#!/usr/bin/env python3
"""Guarded, reversible home-only integration hub for Mojtaba Roozegar.

The independent personal Django app is the only writable target. Social links
are published only from the deliberately curated, verified-only registry.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from urllib.parse import urlsplit

APP = Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
REL = "templates/personal_site/core/home.html"
ANCHOR = '<nav class="mpw-complete-toc" id="mpw-complete-standard-20261019-toc"'
START = "<!-- MPW_OFFICIAL_HUB_START_20261026 -->"
END = "<!-- MPW_OFFICIAL_HUB_END_20261026 -->"
SOCIAL_HOSTS = {
    "Instagram": {"instagram.com", "www.instagram.com"},
    "YouTube": {"youtube.com", "www.youtube.com", "m.youtube.com"},
    "LinkedIn": {"linkedin.com", "www.linkedin.com"},
    "Facebook": {"facebook.com", "www.facebook.com"},
    "TikTok": {"tiktok.com", "www.tiktok.com"},
    "X": {"x.com", "www.x.com"},
    "Telegram": {"t.me"},
    "Threads": {"threads.net", "www.threads.net"},
    "Pinterest": {"pinterest.com", "www.pinterest.com"},
}
SECTIONS = {
    "personal": ("Personal & Research", "شخصی و علمی", "Biography, original research, writing and professional enquiries.",
                 (("My story", "/mojtaba.roozegar/about/"),
                  ("Research journal", "/mojtaba.roozegar/blog/"),
                  ("Contact Mojtaba", "/mojtaba.roozegar/contact/"))),
    "zomorod": ("Zomorod Melal", "شرکت کشت و صنعت زمرد ملل",
                "Agriculture, scientific research, production knowledge and business collaboration.",
                (("Company website", "https://zomorodmelal.ir/"),
                 ("Research", "https://zomorodmelal.ir/research/"),
                 ("Company enquiries", "https://zomorodmelal.ir/contact/"))),
    "mojplaywin": ("MojPlayWin", "مج پلی وین",
                   "Games, AI, education, digital products and research-led services.",
                   (("Platform website", "https://mojplaywin.com/"),
                    ("Digital store", "https://mojplaywin.com/store/"),
                    ("Games", "https://mojplaywin.com/games/"))),
}
STYLE = r"""<style id="mpw-official-hub-css-20261026">
#mpw-social-central-hub-20261026{box-sizing:border-box;max-width:1200px;margin:26px auto 34px;padding:clamp(24px,4vw,52px);color:#f6ecdc;background:linear-gradient(135deg,#202019,#121814 68%,#1c1712);border:1px solid #a98954;border-radius:22px;box-shadow:0 22px 55px #0005;isolation:isolate}
#mpw-social-central-hub-20261026 *{box-sizing:border-box}
#mpw-social-central-hub-20261026 .hub-eyebrow{font:700 12px/1.5 system-ui,sans-serif;letter-spacing:.18em;text-transform:uppercase;color:#e3bb75}
#mpw-social-central-hub-20261026 h2{font:600 clamp(30px,4vw,48px)/1.18 Georgia,serif;color:#f2d294;margin:10px 0 14px}
#mpw-social-central-hub-20261026 .hub-intro{max-width:800px;font:16px/1.85 system-ui,sans-serif;color:#e8dfd2;margin:0 0 22px}
#mpw-social-central-hub-20261026 .hub-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
#mpw-social-central-hub-20261026 .hub-card{min-width:0;background:linear-gradient(160deg,#29261e,#1b201b);border:1px solid #766448;border-radius:16px;padding:clamp(18px,2.5vw,27px)}
#mpw-social-central-hub-20261026 h3{font:600 24px/1.3 Georgia,serif;color:#f4d394;margin:8px 0}
#mpw-social-central-hub-20261026 .hub-fa{font:14px/1.7 system-ui,sans-serif;color:#e4c88f;direction:rtl;text-align:left}
#mpw-social-central-hub-20261026 .hub-copy{font:14px/1.8 system-ui,sans-serif;color:#e6ded0;min-height:78px}
#mpw-social-central-hub-20261026 .hub-links{display:flex;flex-wrap:wrap;gap:8px;margin:17px 0 22px}
#mpw-social-central-hub-20261026 a{display:inline-flex;align-items:center;justify-content:center;border:1px solid #c4a56d;border-radius:999px;color:#f6dba9!important;padding:9px 13px;font:650 13px/1.45 system-ui,sans-serif;text-decoration:none;transition:background .15s}
#mpw-social-central-hub-20261026 a:hover{background:#6b5530;color:#fff!important}
#mpw-social-central-hub-20261026 a:focus-visible{outline:3px solid #fff;outline-offset:3px}
#mpw-social-central-hub-20261026 h4{font:700 12px/1.6 system-ui,sans-serif;letter-spacing:.07em;text-transform:uppercase;color:#f0d8a9;margin:0 0 8px}
#mpw-social-central-hub-20261026 .hub-social{border-top:1px solid #6a573d;padding-top:16px}
#mpw-social-central-hub-20261026 .hub-status{font:13px/1.65 system-ui,sans-serif;color:#c9bdaa;margin:0}
#mpw-social-central-hub-20261026 .hub-note{font:13px/1.8 system-ui,sans-serif;color:#d5c8b2;margin:20px 0 0}
#mpw-social-central-hub-20261026 .hub-note a{border:0;padding:0;text-decoration:underline}
@media(max-width:900px){#mpw-social-central-hub-20261026 .hub-grid{grid-template-columns:1fr}#mpw-social-central-hub-20261026 .hub-copy{min-height:0}}
@media(max-width:600px){#mpw-social-central-hub-20261026{margin:18px 12px;padding:24px 19px}#mpw-social-central-hub-20261026 .hub-links{gap:7px}}
@media(prefers-reduced-motion:reduce){#mpw-social-central-hub-20261026 a{transition:none}}
</style>"""

def checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def registry(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("schema_version") != 1 or not isinstance(obj.get("channels"), dict):
        raise ValueError("Invalid social registry format")
    if set(obj["channels"]) != set(SECTIONS):
        raise ValueError("Social registry channels must match known destinations")
    seen = set()
    for channel, links in obj["channels"].items():
        if not isinstance(links, list) or len(links) > 12:
            raise ValueError("Invalid social link collection")
        for item in links:
            if not isinstance(item, dict) or set(item) != {"platform", "url", "label"}:
                raise ValueError("Unexpected social link fields")
            platform, address, label = item["platform"], item["url"], item["label"]
            if platform not in SOCIAL_HOSTS or not isinstance(address, str) or not isinstance(label, str):
                raise ValueError("Unknown social platform or invalid fields")
            parsed = urlsplit(address)
            if (parsed.scheme != "https" or parsed.hostname not in SOCIAL_HOSTS[platform]
                    or parsed.username or parsed.password or parsed.port
                    or parsed.query or parsed.fragment or len(parsed.path.strip("/")) < 2):
                raise ValueError("Invalid or unverified-looking social profile URL")
            if "dr.mojtaba.rozegar" in address.lower() or "dr.mojtaba.rozegar" in label.lower():
                raise ValueError("Restricted profile cannot be promoted")
            if not 2 <= len(label.strip()) <= 70 or len(address) > 250:
                raise ValueError("Invalid social link label")
            if address in seen:
                raise ValueError("Duplicate social destination")
            seen.add(address)
    return obj["channels"]

def link(label: str, url: str) -> str:
    attrs = ' target="_blank" rel="noopener noreferrer"' if url.startswith("https://") else ""
    return '<a href="' + html.escape(url, quote=True) + '"' + attrs + '>' + html.escape(label) + '</a>'

def build(channels: dict) -> str:
    blocks = []
    for slug, (title, fa, description, destinations) in SECTIONS.items():
        official = "".join(link(text, url) for text, url in destinations)
        socials = channels[slug]
        linked = "".join(link(item["platform"] + " · " + item["label"], item["url"]) for item in socials)
        social_html = ('<div class="hub-links">' + linked + '</div>' if linked else
                       '<p class="hub-status">Verified public profiles will appear here once their ownership is confirmed.</p>')
        blocks.append(
            '<article class="hub-card" aria-labelledby="hub-' + slug + '-title">'
            '<span class="hub-eyebrow">' + ('01' if slug == 'personal' else '02' if slug == 'zomorod' else '03') + ' / OFFICIAL DESTINATION</span>'
            '<h3 id="hub-' + slug + '-title">' + html.escape(title) + '</h3>'
            '<p class="hub-fa" lang="fa" dir="rtl">' + html.escape(fa) + '</p>'
            '<p class="hub-copy">' + html.escape(description) + '</p>'
            '<nav class="hub-links" aria-label="' + html.escape(title) + ' websites">' + official + '</nav>'
            '<div class="hub-social"><h4>Official social channels</h4>' + social_html + '</div>'
            '</article>'
        )
    return "\n".join((
        START, STYLE,
        '<section id="mpw-social-central-hub-20261026" aria-labelledby="mpw-hub-heading">',
        '<span class="hub-eyebrow">MOJTABA ROOZEGAR · OFFICIAL CONNECTIONS</span>',
        '<h2 id="mpw-hub-heading">One identity. Three connected destinations.</h2>',
        '<p class="hub-intro">The central starting point for my personal research and writing, Zomorod Melal Agro-Industry Company, MojPlayWin, and their verified official communications. Choose the destination that fits your enquiry.</p>',
        '<div class="hub-grid">', *blocks, '</div>',
        '<p class="hub-note">Only verified public accounts are linked. For research, collaboration or a channel verification request, <a href="/mojtaba.roozegar/contact/">contact the central office</a>. An unrelated or unverified social handle does not represent these organizations.</p>',
        '</section>', END
    ))

def patch(before: str, channels: dict) -> str:
    if before.count(ANCHOR) != 1:
        raise ValueError("Homepage structure changed: central navigation anchor missing")
    if before.count('id="mpw-primary-personal-profile-20261016"') != 1:
        raise ValueError("Owner-selected profile section missing")
    if before.count('id="hero-title"') != 1:
        raise ValueError("Original hero heading missing")
    block = build(channels)
    a, b = before.count(START), before.count(END)
    if a == b == 0:
        after = before.replace(ANCHOR, block + "\n" + ANCHOR, 1)
    elif a == b == 1:
        start = before.index(START)
        finish = before.index(END) + len(END)
        if start >= finish or before.index(ANCHOR) < finish:
            raise ValueError("Existing hub out of expected position")
        after = before[:start] + block + before[finish:]
    else:
        raise ValueError("Partial or duplicate hub markers")
    if (after.count("{%") != before.count("{%") or after.count("{{") != before.count("{{")
            or after.count('id="hero-title"') != 1 or after.count(START) != 1
            or after.count(END) != 1 or after.index(END) > after.index(ANCHOR)):
        raise ValueError("Template preservation validation failed")
    return after

def target() -> Path:
    if APP.is_symlink() or not (APP / "manage.py").is_file():
        raise ValueError("Independent personal Django app identity mismatch")
    p = APP / REL
    if p.is_symlink() or not p.is_file() or p.resolve() != p:
        raise ValueError("Unsafe homepage target")
    return p

def django_check(src: str) -> None:
    sys.path.insert(0, str(APP))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.template import engines
    engines["django"].engine.from_string(src)

def atomic_write(path: Path, data: bytes) -> None:
    fd, temp = tempfile.mkstemp(prefix=".mpw-official-hub-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            os.fchmod(out.fileno(), stat.S_IMODE(path.stat().st_mode))
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        if os.path.lexists(temp):
            os.unlink(temp)

def backup_path(run_id: str) -> Path:
    if not re.fullmatch(r"[0-9]{6,24}", run_id):
        raise ValueError("Invalid GitHub run ID")
    return Path("/home/zomorod2/.backups/mojtaba-official-network-hub") / run_id

def install(content: Path, run_id: str) -> None:
    p = target()
    old = p.read_bytes()
    new = patch(old.decode("utf-8"), registry(content)).encode("utf-8")
    django_check(new.decode("utf-8"))
    if old == new:
        print("HUB_UNCHANGED=true", flush=True)
        return
    backup = backup_path(run_id)
    if backup.exists() or backup.is_symlink():
        raise ValueError("Backup run path already exists")
    backup.mkdir(mode=0o700, parents=True)
    dest = backup / "home.before"
    with dest.open("xb") as out:
        os.fchmod(out.fileno(), 0o600)
        out.write(old)
        out.flush()
        os.fsync(out.fileno())
    if dest.read_bytes() != old:
        raise ValueError("Backup verification failed")
    manifest = {"target": str(p), "before": checksum(old), "after": checksum(new)}
    (backup / "manifest.json").write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    if checksum(p.read_bytes()) != manifest["before"]:
        raise ValueError("Concurrent homepage edit detected")
    atomic_write(p, new)
    if checksum(p.read_bytes()) != manifest["after"]:
        raise ValueError("Post-write verification failed")
    print("HUB_INSTALLED=true BACKUP=" + str(backup), flush=True)

def rollback(run_id: str) -> None:
    p, backup = target(), backup_path(run_id)
    if backup.is_symlink() or not (backup / "manifest.json").is_file():
        raise ValueError("Backup unavailable")
    data = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    previous = (backup / "home.before").read_bytes()
    current = p.read_bytes()
    if (data["target"] != str(p) or checksum(previous) != data["before"]
            or checksum(current) not in (data["before"], data["after"])):
        raise ValueError("Rollback conflict or corrupted backup")
    if checksum(current) == data["after"]:
        atomic_write(p, previous)
    if checksum(p.read_bytes()) != data["before"]:
        raise ValueError("Rollback failed")
    print("HUB_ROLLBACK_VERIFIED=true", flush=True)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "install", "rollback"))
    parser.add_argument("--content", type=Path)
    parser.add_argument("--run-id")
    args = parser.parse_args()
    if args.action in ("check", "install") and not args.content:
        parser.error("--content is required")
    if args.action in ("install", "rollback") and not args.run_id:
        parser.error("--run-id is required")
    if args.action == "check":
        proposed = patch(target().read_text(encoding="utf-8"), registry(args.content))
        django_check(proposed)
        print("HUB_PREFLIGHT=PASS", flush=True)
    elif args.action == "install":
        install(args.content, args.run_id)
    else:
        rollback(args.run_id)

if __name__ == "__main__":
    main()
