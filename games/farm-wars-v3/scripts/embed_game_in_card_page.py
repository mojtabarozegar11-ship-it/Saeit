#!/usr/bin/env python3
"""Put the already-verified Farm Dominion game *inside* the canonical game-dev card page.

Strictly scoped to these two existing files, with strong preconditions and rollback:
  ~/public_html/topics/zm-r25/game-development/index.html
  ~/public_html/index.html

The original research article, all other homepage cards and the independent game
at /farm-wars/ remain intact. Iframe references same-origin playable 3D WebGL game.
"""
from pathlib import Path
import hashlib,json,os,re,shutil,sys,html

ROOT=Path("/home/zomorod2/public_html")
TOPIC=ROOT/"topics/zm-r25/game-development/index.html"
HOME=ROOT/"index.html"
ROW_ID="ZM-R25"
GAME_ID="ZM-R25-GAME-FARM-DOMINION-20261019"
DEST="/topics/zm-r25/game-development/"
MARK="ZM-FARM-WARS-EMBEDDED-IN-IT-GAME-CARD-20261019"
CSS=r"""
<style id="zm-game-card-play-css">
#zm-farm-card-play{display:block;isolation:isolate;margin:26px auto 35px;max-width:1340px;padding:clamp(12px,2vw,24px);border:1px solid rgba(210,189,105,.52);border-radius:25px;background:linear-gradient(150deg,#143b2ef8,#0b211bef);color:#f5eed5;box-shadow:0 16px 46px #051a1475;font-family:inherit;direction:rtl}
#zm-farm-card-play *{box-sizing:border-box}
#zm-farm-card-play .zm-play-head{display:flex;justify-content:space-between;align-items:center;gap:15px;flex-wrap:wrap;padding:0 2px 12px}
#zm-farm-card-play .zm-play-eyebrow{font-size:11px;color:#a6e1c0;font-weight:800;letter-spacing:1px}
#zm-farm-card-play h2{color:#ffe3a3;font-size:clamp(19px,2.5vw,29px);margin:4px 0;line-height:1.4}
#zm-farm-card-play p{margin:4px 0;color:#d5e6d6;line-height:1.9;font-size:clamp(11px,1.5vw,14px)}
#zm-farm-card-play .zm-play-fullscreen{display:inline-flex;justify-content:center;align-items:center;gap:7px;padding:11px 17px;background:linear-gradient(145deg,#f7d994,#c3a058);border-radius:13px;color:#253223!important;text-decoration:none!important;font-weight:800;font-size:13px;border:1px solid #fff1bb;text-wrap:nowrap}
#zm-farm-card-play .zm-play-fullscreen:focus-visible{outline:3px solid #fff7d5;outline-offset:3px}
#zm-farm-card-play .zm-play-viewport{width:100%;height:min(90svh,860px);min-height:740px;max-height:900px;overflow:hidden;border:2px solid #a8c69c73;border-radius:18px;background:#91bfa8;box-shadow:0 12px 30px #0006}
#zm-farm-card-play iframe{width:100%;height:100%;border:0;display:block;background:#8cbbab}
#zm-farm-card-play .zm-play-footnote{text-align:center;font-size:11px;color:#b8d5bb;margin-top:10px}
@media(max-width:740px){
 #zm-farm-card-play{margin:15px -8px 22px;padding:8px;border-radius:14px}
 #zm-farm-card-play .zm-play-head{padding:10px 8px}
 #zm-farm-card-play .zm-play-viewport{height:92svh;min-height:720px;max-height:none;border-radius:12px}
 #zm-farm-card-play .zm-play-fullscreen{padding:9px 12px;font-size:11px}
}
@media(prefers-reduced-motion:reduce){#zm-farm-card-play *{scroll-behavior:auto!important;transition:none!important}}
</style>
"""
SECTION=r"""
<!-- ZM-FARM-WARS-EMBEDDED-IN-IT-GAME-CARD-20261019 -->
<section id="zm-farm-card-play" aria-labelledby="zm-farm-card-heading" lang="fa" dir="rtl">
  <div class="zm-play-head">
    <div>
      <div class="zm-play-eyebrow">ZOMOROD · FARM DOMINION · WEBGL 3D</div>
      <h2 id="zm-farm-card-heading">🌾 بازی فرمانروای مزرعه‌ها ـ کشاورزی و نبرد سه‌بعدی</h2>
      <p>مزرعه بسازید، آب رودخانه را مدیریت کنید، بذرهای ژنتیکی تولید کنید و قلعه‌های رقیب را فتح کنید. بازی مستقیماً در همین صفحه اجرا می‌شود.</p>
    </div>
    <a class="zm-play-fullscreen" href="/farm-wars/" target="_blank" rel="noopener noreferrer" aria-label="بازکردن بازی فرمانروای مزرعه‌ها به صورت تمام صفحه">⛶ اجرای تمام‌صفحه</a>
  </div>
  <div class="zm-play-viewport">
    <iframe id="zm-farm-3d-player" title="بازی سه‌بعدی فرمانروای مزرعه‌ها در صفحه بازی‌سازی زمرد ملل" src="/farm-wars/" loading="eager" allow="fullscreen" allowfullscreen referrerpolicy="same-origin"></iframe>
  </div>
  <p class="zm-play-footnote">برای بازی، روی «ورود به دنیای سه‌بعدی» در قاب بازی بزنید. پیشرفت در همین مرورگر ذخیره می‌شود.</p>
  <noscript><p>برای اجرای بازی سه‌بعدی جاوااسکریپت مرورگر را فعال کنید، یا از پیوند «اجرای تمام‌صفحه» استفاده کنید.</p></noscript>
</section>
"""

def hash_bytes(b):return hashlib.sha256(b).hexdigest()
def guard(path):
    assert path.is_file() and not path.is_symlink(), "Protected file missing or symlink: "+str(path)
    assert path.stat().st_size>500
def atomic(path,data):
    assert not path.is_symlink()
    temp=path.with_name("."+path.name+".zm-game-embed-"+RUN)
    assert not temp.exists() and not temp.is_symlink()
    with open(temp,"xb") as f:f.write(data)
    os.chmod(temp,0o644)
    assert hash_bytes(temp.read_bytes())==hash_bytes(data)
    os.replace(temp,path)
def validate_article(src):
    assert src.startswith(b"<!doctype html") and b"</html>" in src.lower()
    s=src.decode("utf-8")
    assert MARK not in s,"Game embedding already present; refusing duplicate"
    title=re.search(r"<title\b[^>]*>(.*?)</title>",s,re.S|re.I)
    assert title and "بازی" in title.group(1)
    h1=re.search(r"<h1\b[^>]*>[\s\S]*?</h1>",s,re.I)
    main=re.search(r"<main\b[^>]*>",s,re.I)
    assert main and h1 and main.end()<h1.start(), "Game article structure changed"
    assert s.count("</head>")==1
    assert s.count("</main>")==1
    assert "game-development" in s and "زمرد ملل" in s
    return s,main,h1
def edit_article(src):
    s,main,h1=validate_article(src)
    s=s.replace("</head>",CSS+"</head>",1)
    h1new=re.search(r"<h1\b[^>]*>[\s\S]*?</h1>",s,re.I)
    assert h1new
    s=s[:h1new.end()]+SECTION+s[h1new.end():]
    assert s.count(MARK)==1 and s.count('id="zm-farm-3d-player"')==1
    assert s.count('src="/farm-wars/"')==1
    assert s.replace(SECTION,"",1).replace(CSS,"",1)==src.decode("utf-8")
    return s.encode("utf-8")
def validate_home(homebytes):
    s=homebytes.decode("utf-8")
    marker=r'(window\.ZOMOROD_ORBIT_DATA=)(\{.*?\})(;</script>)'
    matches=list(re.finditer(marker,s,re.S))
    assert len(matches)==1,"Homepage manifest missing or repeated"
    m=matches[0];data=json.loads(m.group(2))
    row=[r for r in data["rows"] if r.get("id")==ROW_ID]
    assert len(row)==1 and row[0].get("title")=="فناوری اطلاعات و خدمات دیجیتال"
    cards=row[0]["cards"]
    assert len(cards)==22
    game=[c for c in cards if c.get("id")==GAME_ID]
    assert len(game)==1 and game[0].get("canonicalUrl")=="/farm-wars/"
    existing=[c for c in cards if c.get("slug")=="game-development"]
    assert len(existing)==1 and existing[0].get("canonicalUrl")==DEST
    assert sum(len(r["cards"]) for r in data["rows"])==606
    return s,m,data
def edit_home(src):
    s,m,data=validate_home(src)
    row=next(r for r in data["rows"] if r["id"]==ROW_ID)
    next(c for c in row["cards"] if c["id"]==GAME_ID)["canonicalUrl"]=DEST
    new=json.dumps(data,ensure_ascii=False,separators=(",",":"))
    res=(s[:m.start(2)]+new+s[m.end(2):]).encode("utf-8")
    assert res.decode("utf-8").replace(new,m.group(2),1)==s
    return res
def meta_path():return STAGE/"metadata.json"
def store(obj):
    file=meta_path();temp=file.with_name("metadata.tmp")
    temp.write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True),encoding="utf-8")
    os.replace(temp,file)
def load():return json.loads(meta_path().read_text(encoding="utf-8"))
def prepare():
    guard(TOPIC);guard(HOME);guard(ROOT/"farm-wars/index.html");guard(ROOT/"farm-wars/game.js")
    article=TOPIC.read_bytes();home=HOME.read_bytes()
    updated_article=edit_article(article);updated_home=edit_home(home)
    assert not (STAGE/"old-article.html").exists()
    for name,data in [("old-article.html",article),("old-home.html",home),
                      ("new-article.html",updated_article),("new-home.html",updated_home)]:
      out=STAGE/name;out.write_bytes(data);assert out.read_bytes()==data
    meta={"phase":"prepared","oldArticle":hash_bytes(article),"newArticle":hash_bytes(updated_article),
          "oldHome":hash_bytes(home),"newHome":hash_bytes(updated_home),
          "gameIndex":hash_bytes((ROOT/"farm-wars/index.html").read_bytes()),
          "gameJs":hash_bytes((ROOT/"farm-wars/game.js").read_bytes())}
    store(meta)
    print("IT_GAME_ARTICLE_SAFE_PREPARE=PASS",len(article),"->",len(updated_article),"home",len(home),flush=True)
def publish_article():
    m=load();assert m["phase"]=="prepared"
    assert hash_bytes(TOPIC.read_bytes())==m["oldArticle"],"Article changed concurrently"
    atomic(TOPIC,(STAGE/"new-article.html").read_bytes())
    assert hash_bytes(TOPIC.read_bytes())==m["newArticle"]
    m["phase"]="article";store(m)
    print("IT_GAME_CARD_DESTINATION_EMBEDDED=PASS",flush=True)
def publish_home():
    m=load();assert m["phase"]=="article"
    assert hash_bytes(TOPIC.read_bytes())==m["newArticle"]
    assert hash_bytes(HOME.read_bytes())==m["oldHome"],"Home changed concurrently"
    atomic(HOME,(STAGE/"new-home.html").read_bytes())
    assert hash_bytes(HOME.read_bytes())==m["newHome"]
    m["phase"]="home";store(m)
    print("IT_NEW_GAME_CARD_NOW_LINKS_TO_EXISTING_GAME_PAGE=PASS",flush=True)
def verify():
    m=load();assert m["phase"]=="home"
    assert hash_bytes(TOPIC.read_bytes())==m["newArticle"]
    assert hash_bytes(HOME.read_bytes())==m["newHome"]
    assert hash_bytes((ROOT/"farm-wars/index.html").read_bytes())==m["gameIndex"]
    assert hash_bytes((ROOT/"farm-wars/game.js").read_bytes())==m["gameJs"]
    article=TOPIC.read_text("utf-8")
    assert MARK in article and "iframe" in article and 'src="/farm-wars/"' in article
    assert "بازی‌سازی" in article
    s=HOME.read_text("utf-8")
    data=json.loads(re.search(r"window\.ZOMOROD_ORBIT_DATA=(\{.*?\});</script>",s,re.S).group(1))
    assert sum(len(r["cards"]) for r in data["rows"])==606
    row=next(r for r in data["rows"] if r["id"]==ROW_ID)
    assert sum(c["canonicalUrl"]==DEST for c in row["cards"])==2
    print("IT_GAME_EMBED_PRESERVED_ARTICLE_AND_ALL_CARDS=PASS",flush=True)
def rollback():
    m=load()
    for path,old,new,backup in [(HOME,"oldHome","newHome","old-home.html"),
                                 (TOPIC,"oldArticle","newArticle","old-article.html")]:
      if path.is_file() and not path.is_symlink():
        digest=hash_bytes(path.read_bytes())
        if digest==m[new]:
          atomic(path,(STAGE/backup).read_bytes())
          assert hash_bytes(path.read_bytes())==m[old]
          print("IT_EMBED_ROLLBACK_RESTORED",path.name,str(path),flush=True)
        else:print("IT_EMBED_ROLLBACK_SKIPPED_UNEXPECTED_CONTENT",path,flush=True)
def main():
    global RUN,STAGE
    assert len(sys.argv)==3,"usage: script action RUN_ID"
    action,RUN=sys.argv[1:]
    assert re.fullmatch(r"\d{5,15}",RUN)
    STAGE=Path("/home/zomorod2/.zm-it-game-embed-"+RUN)
    assert STAGE.is_dir() and not STAGE.is_symlink()
    actions={"prepare":prepare,"article":publish_article,"home":publish_home,
             "verify":verify,"rollback":rollback}
    assert action in actions
    actions[action]()
if __name__=="__main__":main()
