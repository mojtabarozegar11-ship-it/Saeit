#!/usr/bin/env python3
"""Hash-pinned, single-file MojPlayWin homepage MOJ PROP spotlight with private rollback."""
from __future__ import annotations
import getpass
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile

TARGET = Path("/home/zomorod2/mojplaywin.com/design-preview-20261017/production-home-20261017.html")
BACKUP_DIR = Path("/home/zomorod2/.private_mojplaywin_main_agents/mpw_mojprop_home_20261121")
BACKUP = BACKUP_DIR / "production-home-before-mojprop-20261121.html"
MANIFEST = BACKUP_DIR / "manifest.json"
BASE_SHA = "40173e740c370b06f0e3f718ad051c7f64699a32f102e9ad5eb5aeb19bc5b137"
MARKER = 'id="mpw-mojprop-spotlight-20261121"'
TITLE = "MOJ PROP Simulated Trading Challenge | MojPlayWin"
DESCRIPTION = ("Discover MOJ PROP at MojPlayWin: a 60-day simulated trading challenge, "
               "$1,000 virtual reference account, risk rules and Starter30 details.")
SPOTLIGHT = """<section class="mpw-mojprop-spotlight" id="mpw-mojprop-spotlight-20261121" aria-labelledby="mpw-mojprop-title">
  <div class="mpw-mojprop-copy">
    <span class="mpw-mojprop-kicker">FEATURED PROGRAM · SIMULATED TRADING</span>
    <h2 id="mpw-mojprop-title">MOJ PROP <span>60-Day Trading Challenge</span></h2>
    <p>Explore a structured simulated trading evaluation with a $1,000 virtual reference account, transparent risk limits and a 30 TRX Starter30 option.</p>
    <ul class="mpw-mojprop-facts" aria-label="Program highlights">
      <li>60-day simulation</li><li>$1,000 virtual account</li><li>Risk-first evaluation</li>
    </ul>
    <div class="mpw-mojprop-actions">
      <a class="mpw-mojprop-primary" href="/moj-prop/" aria-label="Explore the official MOJ PROP English page">Explore MOJ PROP <span aria-hidden="true">→</span></a>
      <a class="mpw-mojprop-secondary" href="/moj-prop/starter-30-trx/">Read Starter30 terms</a>
    </div>
    <p class="mpw-mojprop-disclosure">Simulated accounts; no customer capital is held. Review the program rules and payment availability before purchasing. No guaranteed earnings.</p>
  </div>
  <div class="mpw-mojprop-art" aria-hidden="true">
    <span class="mpw-mojprop-art-overline">MOJPLAYWIN PRESENTS</span>
    <strong>MOJ <span>PROP</span></strong>
    <div class="mpw-mojprop-art-divider"></div>
    <div class="mpw-mojprop-art-stats"><span><b>60</b> DAYS</span><span><b>$1K</b> VIRTUAL</span><span><b>30</b> TRX</span></div>
    <span class="mpw-mojprop-art-foot">SIMULATION · RISK DISCIPLINE · TRANSPARENCY</span>
  </div>
</section>
"""
STYLE = """<style id="mpw-mojprop-home-spotlight-css-20261121">
.mpw-mojprop-spotlight{box-sizing:border-box;position:relative;isolation:isolate;display:grid;grid-template-columns:minmax(0,1.28fr) minmax(265px,.72fr);align-items:center;gap:clamp(24px,4vw,60px);width:min(1440px,calc(100% - 34px));margin:22px auto 20px;padding:clamp(26px,4.5vw,60px);border:1px solid rgba(239,195,113,.55);border-radius:28px;background:radial-gradient(ellipse at 85% 24%,rgba(225,172,80,.15),transparent 48%),linear-gradient(115deg,#101a22 0%,#0b1017 58%,#1b1711 100%);box-shadow:0 18px 64px rgba(0,0,0,.35);color:#fbf3e4}
.mpw-mojprop-spotlight *{box-sizing:border-box}
.mpw-mojprop-kicker{font-size:.76rem;font-weight:800;letter-spacing:.15em;color:#e7c27d}
.mpw-mojprop-spotlight h2{margin:14px 0 17px;font-size:clamp(2.65rem,5vw,5.35rem);line-height:1.02;letter-spacing:-.05em;color:#fff9ed;text-wrap:balance}
.mpw-mojprop-spotlight h2 span{display:block;font-size:clamp(1.15rem,2.15vw,2rem);letter-spacing:-.015em;line-height:1.3;color:#f0ce93;margin-top:12px}
.mpw-mojprop-copy>p:not(.mpw-mojprop-disclosure){max-width:62ch;color:#e5dfd6;font-size:clamp(.98rem,1.25vw,1.12rem);line-height:1.72}
.mpw-mojprop-facts{display:flex;flex-wrap:wrap;list-style:none;gap:9px;padding:0;margin:22px 0}
.mpw-mojprop-facts li{font-weight:700;font-size:.82rem;border:1px solid rgba(224,189,127,.47);border-radius:50px;padding:8px 13px;color:#f6dfb0;background:rgba(247,217,157,.065)}
.mpw-mojprop-actions{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin-top:26px}
.mpw-mojprop-actions a{display:inline-flex;align-items:center;justify-content:center;min-height:52px;padding:13px 22px;border-radius:12px;font-size:.93rem;font-weight:800;text-decoration:none}
.mpw-mojprop-actions .mpw-mojprop-primary{color:#14130f;background:linear-gradient(115deg,#ffe4a8,#cda660);border:1px solid #eed29b}
.mpw-mojprop-actions .mpw-mojprop-secondary{color:#f7e7c4;border:1px solid rgba(245,206,136,.62);background:#202126}
.mpw-mojprop-actions a:focus-visible{outline:3px solid #fff;outline-offset:4px}
.mpw-mojprop-disclosure{font-size:.77rem;line-height:1.65;color:#c8bfaf;margin:18px 0 0}
.mpw-mojprop-art{display:flex;flex-direction:column;justify-content:center;align-items:center;min-height:320px;border-radius:22px;border:1px solid rgba(231,187,108,.36);background:repeating-linear-gradient(125deg,transparent 0 34px,rgba(226,192,123,.03) 35px 36px),radial-gradient(circle at center,rgba(199,146,57,.22),transparent 68%),#0c1118;padding:25px;text-align:center}
.mpw-mojprop-art-overline,.mpw-mojprop-art-foot{font-size:.66rem;letter-spacing:.2em;font-weight:750;color:#c9b48e}
.mpw-mojprop-art strong{font-size:clamp(2.7rem,5.5vw,5.8rem);line-height:1.08;letter-spacing:-.075em;color:#fff0d0;margin:35px 0 18px}
.mpw-mojprop-art strong span{color:#d9b474}
.mpw-mojprop-art-divider{height:1px;width:90%;background:linear-gradient(90deg,transparent,#cbac73,transparent)}
.mpw-mojprop-art-stats{display:flex;gap:clamp(12px,2vw,26px);margin:24px 0}
.mpw-mojprop-art-stats span{display:flex;flex-direction:column;font-size:.68rem;letter-spacing:.08em;color:#e4d5b9}
.mpw-mojprop-art-stats b{font-size:1.9rem;color:#f5d296;letter-spacing:-.03em}
@media(max-width:850px){.mpw-mojprop-spotlight{grid-template-columns:1fr}.mpw-mojprop-art{min-height:210px}.mpw-mojprop-art strong{margin:18px 0}}
@media(max-width:430px){.mpw-mojprop-spotlight{width:calc(100% - 20px);padding:23px 18px;border-radius:19px}.mpw-mojprop-actions a{width:100%}}
</style>
"""
SCHEMA = """<script id="mpw-mojprop-home-schema-20261121" type="application/ld+json">{"@context":"https://schema.org","@type":"WebPage","@id":"https://mojplaywin.com/#webpage","url":"https://mojplaywin.com/","name":"MOJ PROP Simulated Trading Challenge | MojPlayWin","description":"Discover MOJ PROP simulated trading evaluation, a virtual reference account and Starter30 details.","isPartOf":{"@id":"https://mojplaywin.com/#website"},"about":{"@type":"Service","name":"MOJ PROP simulated trading challenge","url":"https://mojplaywin.com/moj-prop/","serviceType":"Simulated trading evaluation"}}</script>
"""

def sha(x: bytes) -> str:
    return hashlib.sha256(x).hexdigest()

def once(text: str, old: str, new: str) -> str:
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f"Expected one occurrence; found {n}: {old[:80]}")
    return text.replace(old,new,1)

def patch(source: str) -> str:
    if MARKER in source:
        raise RuntimeError("Already patched; refuse a second insertion")
    replacements = [
      ("<title>Moj Play Win | Games, AI, Research & Digital Products</title>",f"<title>{TITLE}</title>"),
      ('<meta name="description" content="Moj Play Win (MojPlayWin) brings together original games, AI tools, scientific research, web development and digital products.">',f'<meta name="description" content="{DESCRIPTION}">'),
      ('<meta property="og:title" content="Moj Play Win | Games, AI, Research & Digital Products">',f'<meta property="og:title" content="{TITLE}">'),
      ('<meta property="og:description" content="Explore original games, AI tools, scientific research and digital products at Moj Play Win (MojPlayWin).">',f'<meta property="og:description" content="{DESCRIPTION}">'),
      ('<meta name="twitter:title" content="Moj Play Win | Games, AI, Research & Digital Products">',f'<meta name="twitter:title" content="{TITLE}">'),
      ('<meta name="twitter:description" content="Original games, research, AI and digital products at Moj Play Win.">',f'<meta name="twitter:description" content="{DESCRIPTION}">')
    ]
    for old,new in replacements:
        source=once(source,old,new)
    source=once(source,"</head>",SCHEMA+STYLE+"</head>")
    old_start='  <section class="mpx-featured" id="starter30-direct-home"'
    next_start='  <div class="mpo-orbits" aria-label="Seventeen interactive project and service rows">'
    start=source.index(old_start)
    end=source.index(next_start,start)
    old=source[start:end]
    if old.count("<section")==0 or old.count("<section")!=1 or old.count("</section>")!=1 or "/moj-prop/starter-30-trx/" not in old:
        raise RuntimeError("Existing Starter30 feature does not match expected structure")
    source=source[:start]+source[end:]
    anchor='<section class="mpo-experience" data-mojplaywin-orbital="v1" aria-labelledby="mw-home-title">'
    source=once(source,anchor,SPOTLIGHT+anchor)
    if source.count('href="/moj-prop/"') < 1 or source.count('rel="canonical" href="https://mojplaywin.com/"') != 1:
        raise RuntimeError("MOJ PROP destination or home canonical invalid")
    if source.count('id="main-content"')!=1 or source.count('<h1 id="mw-home-title">')!=1:
        raise RuntimeError("Homepage landmarks altered")
    if source.count(MARKER)!=1 or source.count("mpw-mojprop-home-schema-20261121")!=1:
        raise RuntimeError("Spotlight markers invalid")
    return source

def atomic_bytes(path: Path, raw: bytes, mode: int) -> None:
    temp=None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,prefix=".mpw-prop-home-",delete=False) as f:
            temp=Path(f.name)
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temp,mode)
        os.replace(temp,path)
    finally:
        if temp and temp.exists(): temp.unlink()

def run(mode: str) -> None:
    if getpass.getuser()!="zomorod2":
        raise RuntimeError("Wrong deployment account")
    if TARGET.is_symlink() or TARGET.parent.is_symlink() or not TARGET.is_file():
        raise RuntimeError("Invalid live homepage path")
    raw=TARGET.read_bytes()
    current=sha(raw)
    if mode=="--rollback":
        if not MANIFEST.is_file() or not BACKUP.is_file():
            raise RuntimeError("No verified rollback manifest")
        m=json.loads(MANIFEST.read_text())
        previous=BACKUP.read_bytes()
        if sha(previous)!=m["before"] or current!=m["after"]:
            raise RuntimeError("Rollback SHA lease failed; do not overwrite concurrent edits")
        atomic_bytes(TARGET,previous,stat.S_IMODE(TARGET.stat().st_mode))
        print("ROLLBACK_OK",sha(TARGET.read_bytes()))
        return
    if current!=BASE_SHA:
        raise RuntimeError("LIVE_SHA_DRIFT; expected "+BASE_SHA+" got "+current)
    proposed=patch(raw.decode("utf-8")).encode("utf-8")
    if not 1000 < len(proposed)-len(raw) < 11000:
        raise RuntimeError("Unexpected patch size")
    print("CANDIDATE_VALID",json.dumps({"before":current,"after":sha(proposed),"added_bytes":len(proposed)-len(raw),"path":str(TARGET)}))
    if mode=="--check":
        return
    if mode!="--apply":
        raise RuntimeError("Usage --check | --apply | --rollback")
    if BACKUP_DIR.exists() and BACKUP_DIR.is_symlink():
        raise RuntimeError("Backup symlink not allowed")
    BACKUP_DIR.mkdir(parents=True,exist_ok=True,mode=0o700)
    os.chmod(BACKUP_DIR,0o700)
    if BACKUP.exists() or MANIFEST.exists():
        raise RuntimeError("Backup/manifest already exists; fail closed")
    BACKUP.write_bytes(raw)
    os.chmod(BACKUP,0o600)
    if sha(BACKUP.read_bytes())!=BASE_SHA:
        raise RuntimeError("Backup hash mismatch; no deploy")
    m={"before":current,"after":sha(proposed),"target":str(TARGET),"backup":str(BACKUP),"scope":"homepage-only-banner-and-seo"}
    MANIFEST.write_text(json.dumps(m,indent=2)+"\n")
    os.chmod(MANIFEST,0o600)
    if sha(TARGET.read_bytes())!=current:
        raise RuntimeError("Concurrent live change; no deploy")
    atomic_bytes(TARGET,proposed,stat.S_IMODE(TARGET.stat().st_mode))
    if sha(TARGET.read_bytes())!=m["after"]:
        raise RuntimeError("Post-deploy hash mismatch; invoke checked rollback")
    print("LIVE_HOME_UPDATED",m["after"],"BACKUP_SHA_VERIFIED",m["before"])

if __name__=="__main__":
    if len(sys.argv)!=2: raise SystemExit("Usage: python script.py --check|--apply|--rollback")
    run(sys.argv[1])
