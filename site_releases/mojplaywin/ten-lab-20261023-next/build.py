#!/usr/bin/env python3
"""Build ten self-contained English browser experiences with deterministic metadata."""
from pathlib import Path
import html,json,re,hashlib,sys
root=Path(__file__).resolve().parent
target=Path(sys.argv[1]) if len(sys.argv)>1 else root/'dist'
games=[
("hex-bloom","Hex Bloom","Merge strategy puzzle","Fuse matching neighboring hex-like energy blooms, plan each move and grow a 128-point crystal.","merge / plan"),
("prism-relay","Prism Relay","Laser reflection puzzle","Rotate mirror panels to bend a light beam and illuminate every receiver.","rotate / route"),
("kitchen-rush","Kitchen Rush","Restaurant time management","Assemble ingredient combinations quickly to serve incoming orders and maintain your customer streak.","prep / serve"),
("type-defender","Type Defender","Typing action defense","Type descending code words to stop approaching cyber threats before they reach the shield.","type / defend"),
("codebreaker-vault","Codebreaker Vault","Deduction and logic","Crack a hidden four-symbol security code using exact and misplaced clues in eight guesses.","deduce / unlock"),
]
tools=[
("file-fingerprint","File Fingerprint","SHA-256 file verifier","Calculate the SHA-256 checksum of a local file and compare its integrity against an expected digest.","hash / verify"),
("meeting-time-planner","Meeting Time Planner","Worldwide time zone planner","Compare a proposed meeting date across five real time zones with working-hour indicators.","schedule / compare"),
("subtitle-shifter","Subtitle Shifter","Subtitle timing editor","Shift subtitle timestamps, convert SRT to VTT and export the corrected captions.","shift / convert"),
("text-diff-lab","Text Diff Lab","Text comparison utility","Compare two text versions line-by-line with additions, removals and a downloadable report.","compare / export"),
("passphrase-forge","Passphrase Forge","Local secure phrase creator","Generate cryptographically random memorable passphrases or strong passwords directly in your browser.","generate / protect"),
]
manifest={"version":"20261023-next-v1","brand":"MojPlayWin","language":"en","games":[dict(zip(("slug","title","genre","description","verbs"),g)) for g in games],"tools":[dict(zip(("slug","title","genre","description","verbs"),t)) for t in tools]}
def page(title,body,description,url,script=None,kind="CollectionPage"):
    esc=html.escape
    canonical="https://mojplaywin.com/game-releases/20261023-next/"+url
    script_tag=f'<script defer src="{esc(script)}"></script>' if script else ""
    jsonld=json.dumps({"@context":"https://schema.org","@type":kind,"name":title,"description":description,"inLanguage":"en","url":canonical},ensure_ascii=False).replace("</","<\\/")
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="dark"><meta name="theme-color" content="#081528"><title>{esc(title)} | MojPlayWin</title><meta name="description" content="{esc(description)}"><link rel="canonical" href="{esc(canonical)}"><meta property="og:title" content="{esc(title)} | MojPlayWin"><meta property="og:type" content="website"><meta property="og:description" content="{esc(description)}"><link rel="stylesheet" href="{ '../' if '/' in url else ''}assets/theme.css"><script type="application/ld+json">{jsonld}</script>{script_tag}</head><body>{body}<footer><span>© 2022 Mojtaba Roozegar · MojPlayWin</span><span>English-only · No accounts · No ads · No payments</span></footer></body></html>'''
def card(item,group):
    s=item["slug"]
    return f'<a class="card" href="./{s}/index.html"><span class="eyebrow">{html.escape(item["genre"])}</span><h2>{html.escape(item["title"])}</h2><p>{html.escape(item["description"])}</p><span class="action">{"PLAY NOW" if group=="games" else "OPEN TOOL"} ↗</span></a>'
hub='<header class="hero"><a class="brand" href="https://mojplaywin.com/">✧ MOJPLAYWIN</a><span class="label">ORIGINAL · BROWSER EDITION · 2026</span><h1>Five more worlds.<br><em>Five more useful tools.</em></h1><p>Ten MORE distinct, English-language experiences. Real gameplay, usable output, mobile-friendly controls, and privacy-first local processing.</p><div class="stats"><span>05 playable games</span><span>05 practical utilities</span><span>100% client-side</span></div></header><main><section class="collection"><div class="section-heading"><span>01 / ARCADE</span><h2>Interactive games</h2><p>Different choices, controls and win conditions. Play free; progress stays on your device.</p></div><div class="cards">'+''.join(card(x,"games") for x in manifest["games"])+'</div></section><section class="collection"><div class="section-heading"><span>02 / WORKSHOP</span><h2>Useful tools</h2><p>Process your own files and details in this browser. No server upload or account required.</p></div><div class="cards">'+''.join(card(x,"tools") for x in manifest["tools"])+'</div></section></main>'
game_template='''<header class="compact"><a class="brand" href="../index.html">← TEN EXPERIENCES</a><span class="label">ORIGINAL BROWSER GAME</span></header><main class="layout"><section class="game-shell"><div class="game-meta"><span class="eyebrow">{genre}</span><h1>{title}</h1><p>{description}</p></div><div class="scoreline"><span id="score">SCORE 0</span><span id="level">LEVEL 1</span><span id="best">BEST 0</span></div><div class="playfield"><canvas id="stage" width="920" height="520" aria-label="{title} game board"></canvas><div id="overlay" class="overlay"><h2 id="overlay-title">READY TO PLAY?</h2><p id="overlay-text">Tap PLAY to begin.</p><button class="primary" id="start">START GAME</button></div></div><div class="ctrls"><button id="left" aria-label="Move left">◀</button><button id="up" aria-label="Move up or jump">▲</button><button id="action" class="primary">ACTION</button><button id="down" aria-label="Move down">▼</button><button id="right" aria-label="Move right">▶</button><button id="pause">PAUSE</button></div><div class="note" id="instructions" role="status">Loading game…</div></section><aside class="side"><div class="aside-card"><span class="eyebrow">HOW IT WORKS</span><h2>Play, learn, replay.</h2><p>{description}</p><p>Keyboard and touch controls are supported. Press the on-screen buttons, or use arrows and Space. Pause anytime; moving to another tab pauses automatically.</p></div><div class="aside-card"><span class="eyebrow">PRIVACY</span><p>Optional best score is saved only in local storage on this device. No tracking or payments.</p></div></aside></main>'''
tool_template='''<header class="compact"><a class="brand" href="../index.html">← TEN EXPERIENCES</a><span class="label">PRACTICAL BROWSER TOOL</span></header><main class="layout"><section class="tool-shell"><div class="game-meta"><span class="eyebrow">{genre}</span><h1>{title}</h1><p>{description}</p></div><div id="workspace" class="workspace" data-app="{slug}"></div><div id="feedback" role="status" aria-live="polite"></div></section><aside class="side"><div class="aside-card"><span class="eyebrow">YOUR DATA</span><h2>Stays with you.</h2><p>Runs locally in your browser. You decide whether to download or print output. Nothing is uploaded to MojPlayWin.</p></div><div class="aside-card"><span class="eyebrow">LIMITS</span><p>Review generated outputs before professional or legal use. Currency, tax and schema rules differ by country.</p></div></aside></main>'''
target.mkdir(parents=True,exist_ok=True)
(target/'assets').mkdir(exist_ok=True)
for name in ('theme.css','arcade.js','workshop.js'):
    (target/'assets'/name).write_bytes((root/'assets'/name).read_bytes())
for group,items in (('games',games),('tools',tools)):
    for slug,title,genre,description,verbs in items:
        d=target/slug;d.mkdir(exist_ok=True)
        src=(game_template if group=='games' else tool_template).format(slug=slug,title=html.escape(title),genre=html.escape(genre),description=html.escape(description))
        script='../assets/arcade.js' if group=='games' else '../assets/workshop.js'
        if group=='games':src=src.replace('<canvas id="stage"','<canvas data-game="'+slug+'" id="stage"')
        (d/'index.html').write_text(page(title,src,description,slug+'/index.html',script,'VideoGame' if group=='games' else 'SoftwareApplication'),encoding='utf8')
(target/'index.html').write_text(page('Original Games and Practical Tools',hub,'Five additional distinct playable games and five additional practical browser tools.','index.html'),encoding='utf8')
(target/'release.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
hashes={str(p.relative_to(target)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(target.rglob('*')) if p.is_file()}
(target/'hashes.json').write_text(json.dumps(hashes,sort_keys=True),encoding='utf8')
assert len(list(target.rglob('index.html')))==11
assert len(set(x["slug"] for x in manifest["games"]+manifest["tools"]))==10
print('MPW_TEN_DISTINCT_PAGES_BUILT=11 | assets=3 | slugs=10 | SHA manifest entries='+str(len(hashes)))
