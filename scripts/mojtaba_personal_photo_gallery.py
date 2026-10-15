#!/usr/bin/env python3
"""Non-destructive personal-site portfolio addition for owner-supplied photographs.

This installer intentionally refuses to publish without all ten matching files.
It changes only the verified V17 personal home template and a new static directory.
No MojPlayWin docroot, other domain, Django URL, SEO base or database writes.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import os
from pathlib import Path
import shutil
import tempfile
from datetime import datetime, timezone

APP = Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
HOME_REL = "templates/personal_site/core/home.html"
STATIC_REL = "static/personal_site/owner_gallery_20261015"
MARKER = 'id="owner-original-gallery-20261015"'
PHOTOS = [
    ("Founder portrait · MojPlayWin", "76d46c93cf269d39b5c71a93e25c90bd7b794fbd251cd7d503dbd5221de3dccf"),
    ("Executive work · Zomorod Melal", "00e1a093fb1b55e28b79fb3e9a640ae2fc025eca21ee6819c3eb7a2dcaf945e3"),
    ("Business presentation", "3446212e93ac0c759bbfe8bf4359727318b05a2c7bb93902505fb6843130aef9"),
    ("Agricultural research & technology", "9c3572cbba6b23f7744cb04f7f5ccb04bc90ca88a23b4836f27445814fa84fe7"),
    ("Business cooperation", "2ea023db5e6854b0c767f8bd4f6b5d4b0596296e9904c60a313e9f2209d8d5f8"),
    ("Executive leadership", "7fad4709ee52b6294d259c835d1445d1ed63de12d0a5799aa0b2f671a888977a"),
    ("Zomorod Melal leadership", "ee8aabee87ccc5fe302c97080cc314d9ab5236672219b3fca96ed8bdfbb72951"),
    ("Founder · MojPlayWin profile", "4ed4c074bc947acba9333707abb30caf6c084bdea8f6a202690d77405febd493"),
    ("MojPlayWin · Executive portrait", "474d586d1f47847aeae9a8e8b113d0e28de328a4f993a2315ac92cd39e241024"),
    ("Agriculture & management profile", "2b12cd8c95fb912467917d13bb7332989aee8635040d835ddd3ddf1853540e19"),
]

def verify_photos(folder: Path) -> None:
    assert folder.is_dir(), "Photo source directory is missing"
    for i, (title, expected) in enumerate(PHOTOS, 1):
        p = folder / f"photo-{i:02}.jpg"
        assert p.is_file() and not p.is_symlink(), f"Missing file {p.name}"
        got = hashlib.sha256(p.read_bytes()).hexdigest()
        assert got == expected, f"Owner-supplied photo {i:02} checksum mismatch"
        print(f"PHOTO_{i:02}=VERIFIED ({p.stat().st_size} bytes)")

def section() -> str:
    cards = []
    for i, (title, _) in enumerate(PHOTOS, 1):
        filename = f"photo-{i:02}.jpg"
        static_expr = "{% static 'personal_site/owner_gallery_20261015/" + filename + "' %}"
        name = html.escape(title, quote=True)
        cards.append(
            '<figure class="og-card"><a href="' + static_expr + '" target="_blank" rel="noopener"'
            ' aria-label="Open photo ' + str(i) + ': ' + name + '">'
            '<img src="' + static_expr + '" alt="' + name + '" loading="lazy" decoding="async"></a>'
            '<figcaption>PHOTO ' + f"{i:02}" + ' · ' + name + '</figcaption></figure>'
        )
    return """
<!-- owner-original-gallery start -->
<section id="owner-original-gallery-20261015" class="og-wrap" aria-label="Professional story and portfolio gallery">
  <style>
    .og-wrap{background:#101e2e;color:#eee5d8;padding:clamp(35px,5vw,70px) 20px;font-family:inherit}
    .og-wrap *{box-sizing:border-box}
    .og-inner{width:100%;max-width:1160px;margin:0 auto}
    .og-wrap h2,.og-wrap h3{color:#f5eee3;font-family:Georgia,'Times New Roman',serif;font-weight:400}
    .og-wrap h2{font-size:clamp(35px,5vw,59px);line-height:1.15;margin:10px 0 20px}
    .og-wrap h3{font-size:clamp(23px,3vw,31px);margin:0 0 14px}
    .og-wrap p{font-size:clamp(16px,1.65vw,18px);line-height:1.8;color:#bbc7d4;margin:0 0 18px}
    .og-kicker{font-size:12px!important;font-weight:800;color:#dfbd7d!important;letter-spacing:.21em;text-transform:uppercase}
    .og-story{max-width:970px;margin-bottom:45px}
    .og-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px;margin:22px 0 45px}
    .og-box{border:1px solid rgba(223,189,125,.3);padding:28px;background:#1c2f44;border-radius:10px}
    .og-percent{font:normal 52px Georgia,serif;color:#dfbd7d}
    .og-gallery{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
    .og-card{padding:0;margin:0;overflow:hidden;background:#172839;border:1px solid rgba(223,189,125,.22);border-radius:9px}
    .og-card img{width:100%;height:320px;object-fit:contain;background:#111b29;display:block}
    .og-card a:focus-visible{outline:3px solid #dfbd7d;outline-offset:-3px}
    .og-card figcaption{font-size:14px;line-height:1.5;color:#f0e4d5;padding:14px 17px}
    .og-note{font-size:12px!important;color:#9fb0c1!important;margin-top:17px!important}
    @media(max-width:850px){.og-gallery{grid-template-columns:repeat(2,minmax(0,1fr))}}
    @media(max-width:600px){.og-grid{grid-template-columns:1fr}.og-gallery{gap:9px}.og-card img{height:205px}.og-card figcaption{font-size:12px;padding:12px}.og-wrap{padding:36px 14px}}
  </style>
  <div class="og-inner">
    <div class="og-story">
      <p class="og-kicker">From the land of Cyrus to Vancouver, Canada</p>
      <h2>Rooted in heritage. Building beyond borders.</h2>
      <p>I am Mojtaba Roozegar, an Iranian entrepreneur and researcher. I come from the land of Cyrus the Great and Persepolis, where history, craftsmanship, science and culture remain important parts of my identity.</p>
      <p>My recent move to Vancouver, British Columbia, was unexpected and unplanned. It is a new chapter after years of practical experience in Iran, including the management of Zomorod Melal Agro-Industry Company, scientific and agricultural projects, jewelry, gold coins, carpets, hospitality, publishing and professional website development.</p>
      <p>My personal website is a bridge for conversations, ideas and professional collaborations. I believe that research, creativity and experience can cross geographical borders.</p>
    </div>
    <p class="og-kicker">The MojPlayWin vision</p>
    <h2>Experience meets innovation.</h2>
    <div class="og-grid">
      <div class="og-box"><div class="og-percent">80%</div><h3>Research, technology &amp; education</h3><p>Planned focus on scientific research, artificial intelligence, emerging technologies, original digital products, gaming, publishing and accessible education.</p></div>
      <div class="og-box"><div class="og-percent">20%</div><h3>Specialist business experience</h3><p>Selected work and collaboration in agriculture, project management, jewelry, precious metals, carpets, hospitality and professional digital services.</p></div>
    </div>
    <p class="og-kicker">Personal visual portfolio</p>
    <h2>Ten images. Each with its own place.</h2>
    <p>Explore my professional interests through ten individual branded visual portraits. Select any image to open it independently, in its original supplied composition.</p>
    <div class="og-gallery">""" + "\n".join(cards) + """</div>
    <p class="og-note">These are editorial and branded images supplied for this website; depicted scenes are not independent documentary proof of specific meetings or locations. Planned percentages are goals, not audited business results.</p>
  </div>
</section>
<!-- owner-original-gallery end -->
"""

def prepare_home(current: str) -> str:
    if MARKER in current:
        raise ValueError("Gallery already installed: refusing duplicate insertion")
    if "{% load static %}" not in current or "{% block content %}" not in current:
        raise ValueError("Unexpected personal home template")
    if current.count("{% block content %}") != 1:
        raise ValueError("Ambiguous template content block")
    marker = "{% endblock %}"
    pos = current.rfind(marker)
    if pos < 0 or pos < current.find("{% block content %}"):
        raise ValueError("Missing content closing block")
    out = current[:pos] + section() + "\n" + current[pos:]
    assert out.count(MARKER) == 1
    assert out.count('class="og-card"') == 10
    return out

def main() -> None:
    cli = argparse.ArgumentParser()
    cli.add_argument("operation", choices=("check", "install"))
    cli.add_argument("--app", type=Path, default=APP)
    cli.add_argument("--photo-dir", type=Path, required=True, help="Directory containing photo-01.jpg through photo-10.jpg")
    args = cli.parse_args()
    app = args.app.resolve(strict=True)
    if app != APP or app.is_symlink() or not (app / "manage.py").is_file():
        raise SystemExit("Verified V17 application path mismatch; no changes made")
    home = app / HOME_REL
    target = app / STATIC_REL
    if home.is_symlink() or not home.is_file() or target.exists() or target.is_symlink():
        raise SystemExit("Unsafe original template or pre-existing target; no changes made")
    verify_photos(args.photo_dir)
    original = home.read_text(encoding="utf-8")
    proposed = prepare_home(original)
    print("ORIGINAL_TEMPLATE_PRESERVED=yes")
    print("GALLERY_PHOTOS=10")
    if args.operation == "check":
        print("CHECK_OK; NOT_INSTALLED")
        return
    backup_dir = Path.home() / ".backups/mojtaba-original-photos"
    backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup_file = backup_dir / ("home_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".html")
    shutil.copy2(home, backup_file)
    backup_file.chmod(0o600)
    staged = []
    installed = False
    try:
        with tempfile.TemporaryDirectory(prefix="owner-gallery-",dir=str(target.parent)) as d:
            stage_dir = Path(d)
            for i in range(1, 11):
                shutil.copy2(args.photo_dir / f"photo-{i:02}.jpg", stage_dir / f"photo-{i:02}.jpg")
            os.rename(stage_dir, target)
        tmp_file = home.with_name(home.name + ".gallery-tmp")
        tmp_file.write_text(proposed, encoding="utf-8")
        os.chmod(tmp_file, home.stat().st_mode & 0o777)
        os.replace(tmp_file, home)
        installed = True
        restart = app / "tmp/restart.txt"
        if restart.parent.is_dir():
            restart.touch()
        print("INSTALLED_OK; BACKUP=" + str(backup_file))
        print("NEXT: run Django collectstatic where applicable; verify homepage and ten HTTPS images")
    except BaseException:
        if installed:
            shutil.copy2(backup_file, home)
        if target.is_dir():
            shutil.rmtree(target)
        print("FAILED; ROLLBACK_ATTEMPTED")
        raise

if __name__ == "__main__":
    main()
