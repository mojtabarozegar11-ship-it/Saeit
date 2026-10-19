#!/usr/bin/env python3
"""Isolated, reversible release of Farm Dominion 3D and one new IT home card.

Invoked only on the owner's cPanel via pinned GitHub Actions -> VPS SSH.
No unrelated pages, templates or app data are modified.
"""
import os, re, sys, json, hashlib, shutil, tempfile, stat
from pathlib import Path

ROOT=Path("/home/zomorod2/public_html")
TAG="ZM-FARM-DOMINION-V4-20261019"
ROW_ID="ZM-R25"
CARD_ID="ZM-R25-GAME-FARM-DOMINION-20261019"
CARD_SLUG="farm-dominion-3d"
GAME=ROOT/"farm-wars"
PREVIEW=ROOT/"farm-dominion-preview"
PROTECTED=[".htaccess","agriculture/index.html","research/index.html",
 "tala/index.html","company/index.html"]
def sha(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for block in iter(lambda:f.read(262144),b""):h.update(block)
    return h.hexdigest()
def guard(p,exists=True):
    assert os.path.commonpath([str(p),str(ROOT)])==str(ROOT) or os.path.commonpath([str(p),str(STAGE)])==str(STAGE),f"path escaped approved roots: {p}"
    assert not p.is_symlink(),f"symlink blocked: {p}"
    if exists:assert p.is_file() and p.stat().st_size>0,f"missing file: {p}"
def atomic_copy(src,dst):
    guard(src)
    assert not dst.is_symlink()
    temporary=dst.with_name("."+dst.name+".farm-v4-"+RUN)
    assert not temporary.exists() and not temporary.is_symlink()
    shutil.copy2(src,temporary)
    assert sha(src)==sha(temporary)
    os.replace(temporary,dst)
def snap(path,out):
    guard(path);assert not out.exists()
    shutil.copy2(path,out)
    assert sha(path)==sha(out)
def metadata():
    return json.loads((STAGE/"release.json").read_text("utf-8"))
def store(m):
    tmp=STAGE/"release.json.temp"
    tmp.write_text(json.dumps(m,ensure_ascii=False,sort_keys=True),encoding="utf-8")
    os.replace(tmp,STAGE/"release.json")
def make_card(source):
    text=source.decode("utf-8")
    marker=r'(window\.ZOMOROD_ORBIT_DATA=)(\{.*?\})(;</script>)'
    matches=list(re.finditer(marker,text,re.S))
    assert len(matches)==1,"missing or duplicated home orbit manifest"
    m=matches[0];data=json.loads(m.group(2))
    rows=data.get("rows")
    assert isinstance(rows,list) and len(rows)>=26
    targets=[r for r in rows if r.get("id")==ROW_ID]
    assert len(targets)==1
    row=targets[0]
    assert row.get("title")=="فناوری اطلاعات و خدمات دیجیتال"
    assert row.get("index")==25 and row.get("slug")=="digital-services"
    assert len(row["cards"])>=20 and len(row["cards"])<=35
    assert all(c.get("slug")!=CARD_SLUG and c.get("id")!=CARD_ID for c in row["cards"])
    assert any(c.get("slug")=="game-development" for c in row["cards"]),"existing game-development card lost"
    previous_ids=[c.get("id") for c in row["cards"]]
    before_count=sum(len(r.get("cards",[])) for r in rows)
    entry={
      "id":CARD_ID,
      "title":"بازی سه‌بعدی فرمانروای مزرعه‌ها",
      "slug":CARD_SLUG,
      "image":"/farm-wars/cover.webp",
      "imageStatus":"real_gameplay_screenshot",
      "canonicalUrl":"/farm-wars/",
      "livePage":True,
      "previousCanonicalUrl":None
    }
    row["cards"].insert(0,entry)
    assert [c.get("id") for c in row["cards"][1:]]==previous_ids
    assert sum(len(r.get("cards",[])) for r in rows)==before_count+1
    packed=json.dumps(data,ensure_ascii=False,separators=(",",":"))
    assert "</script" not in packed.lower()
    edited=text[:m.start(2)]+packed+text[m.end(2):]
    assert edited.replace(packed,m.group(2),1)==text,"unexpected change to home outside data manifest"
    assert edited.count(CARD_ID)==1 and edited.count('window.ZOMOROD_ORBIT_DATA=')==1
    return edited.encode("utf-8"),before_count
def prepare():
    assert ROOT.is_dir() and GAME.is_dir() and PREVIEW.is_dir()
    for path in [ROOT/"index.html",GAME/"index.html",GAME/".htaccess",
                 PREVIEW/"index.html",PREVIEW/"game.js",ROOT/"agriculture/index.html"]:
       guard(path)
    assert not (GAME/"game.js").exists() and not (GAME/"assets").exists()
    assert not (GAME/"cover.webp").exists()
    assert "PassengerEnabled off" in (GAME/".htaccess").read_text()
    for rel in ["build/index.html","build/game.js","build/.htaccess"]:
       guard(STAGE/rel)
    models=list((STAGE/"build/assets").glob("*.glb"))
    assert len(models)==27
    for path in models:guard(path)
    for a,b in [(GAME/"index.html","old-game.html"),(PREVIEW/"index.html","old-preview.html"),
                (PREVIEW/"game.js","old-preview.js"),(ROOT/"index.html","old-home.html")]:
        snap(a,STAGE/b)
    protected={}
    for rel in PROTECTED:
       p=ROOT/rel
       if p.is_file() and not p.is_symlink():protected[rel]=sha(p)
    assert len(protected)>=2
    m={"phase":"prepared","oldGame":sha(STAGE/"old-game.html"),
       "oldHome":sha(STAGE/"old-home.html"),"newGame":sha(STAGE/"build/index.html"),
       "newJs":sha(STAGE/"build/game.js"),"newCover":None,
       "oldPreview":sha(STAGE/"old-preview.html"),"oldPreviewJs":sha(STAGE/"old-preview.js"),
       "protected":protected,"modelCount":len(models)}
    store(m);print("RIVER_PULSE_PRODUCTION_PREPARED=PASS")
def preview():
    m=metadata()
    assert m["phase"]=="prepared"
    assert sha(PREVIEW/"index.html")==m["oldPreview"] and sha(PREVIEW/"game.js")==m["oldPreviewJs"]
    try:
       atomic_copy(STAGE/"build/game.js",PREVIEW/"game.js")
       atomic_copy(STAGE/"build/index.html",PREVIEW/"index.html")
       assert sha(PREVIEW/"index.html")==m["newGame"]
       assert sha(PREVIEW/"game.js")==m["newJs"]
       m["phase"]="preview";store(m)
       print("RIVER_PULSE_PREVIEW_UPDATED=PASS")
    except BaseException:
       rollback_preview()
       raise
def rollback_preview():
    m=metadata()
    if sha(PREVIEW/"index.html") in [m["oldPreview"],m["newGame"]]:
       atomic_copy(STAGE/"old-preview.html",PREVIEW/"index.html")
    if sha(PREVIEW/"game.js") in [m["oldPreviewJs"],m["newJs"]]:
       atomic_copy(STAGE/"old-preview.js",PREVIEW/"game.js")
    print("RIVER_PULSE_PREVIEW_REVERTED=YES")
def artwork():
    m=metadata()
    assert m["phase"]=="preview",m["phase"]
    cover=STAGE/"build/cover.webp"
    guard(cover)
    assert 1000<cover.stat().st_size<160000,"real game cover should be optimized"
    m["newCover"]=sha(cover)
    store(m)
    print("RIVER_PULSE_REAL_SCREENSHOT_COVER=PASS",cover.stat().st_size)
def game():
    m=metadata()
    assert m["phase"]=="preview" and m["newCover"]
    assert sha(GAME/"index.html")==m["oldGame"]
    assert not (GAME/"assets").exists() and not (GAME/"game.js").exists()
    try:
       (GAME/"assets").mkdir(mode=0o755)
       for model in (STAGE/"build/assets").glob("*.glb"):
          assert re.fullmatch(r"[a-z0-9-]+\.glb",model.name)
          atomic_copy(model,GAME/"assets"/model.name)
       atomic_copy(STAGE/"build/game.js",GAME/"game.js")
       atomic_copy(STAGE/"build/cover.webp",GAME/"cover.webp")
       # Switch the visible route only after all assets are present.
       atomic_copy(STAGE/"build/index.html",GAME/"index.html")
       assert sha(GAME/"index.html")==m["newGame"]
       m["phase"]="game";store(m)
       print("RIVER_PULSE_GAME_PUBLISHED=PASS")
    except BaseException:
       rollback_game()
       raise
def rollback_game():
    m=metadata()
    if (GAME/"index.html").is_file() and sha(GAME/"index.html") in [m["newGame"],m["oldGame"]]:
       atomic_copy(STAGE/"old-game.html",GAME/"index.html")
    for name,expected in [("game.js",m["newJs"]),("cover.webp",m["newCover"])]:
       p=GAME/name
       if p.is_file() and not p.is_symlink() and sha(p)==expected:p.unlink()
    assets=GAME/"assets"
    if assets.is_dir() and not assets.is_symlink():
       allowed={p.name for p in (STAGE/"build/assets").glob("*.glb")}
       for p in assets.iterdir():
          if p.is_file() and not p.is_symlink() and p.name in allowed and sha(p)==sha(STAGE/"build/assets"/p.name):
             p.unlink()
       if not list(assets.iterdir()):assets.rmdir()
    print("RIVER_PULSE_GAME_ROLLED_BACK=YES")
def home():
    m=metadata()
    assert m["phase"]=="game"
    assert sha(ROOT/"index.html")==m["oldHome"],"concurrent homepage change blocked"
    edited,before_count=make_card((ROOT/"index.html").read_bytes())
    new_path=STAGE/"prepared-home.html"
    new_path.write_bytes(edited)
    m["newHome"]=sha(new_path)
    m["homeOldCards"]=before_count
    store(m)
    atomic_copy(new_path,ROOT/"index.html")
    assert sha(ROOT/"index.html")==m["newHome"]
    m["phase"]="home";store(m)
    print("RIVER_PULSE_NEW_IT_CARD_PUBLISHED=PASS originalCards",before_count,"newCards",before_count+1)
def rollback_home():
    m=metadata()
    home=ROOT/"index.html"
    if "newHome" in m and home.is_file() and sha(home)==m["newHome"]:
       atomic_copy(STAGE/"old-home.html",home)
       assert sha(home)==m["oldHome"]
       print("RIVER_PULSE_HOME_ROLLED_BACK=YES")
    else:print("RIVER_PULSE_HOME_ROLLBACK_SKIPPED_UNEXPECTED_CHANGE")
def verify():
    m=metadata()
    assert m["phase"]=="home"
    assert sha(ROOT/"index.html")==m["newHome"] and sha(GAME/"index.html")==m["newGame"]
    assert sha(GAME/"game.js")==m["newJs"] and sha(GAME/"cover.webp")==m["newCover"]
    assert len(list((GAME/"assets").glob("*.glb")))==27
    for rel,hash_before in m["protected"].items():
       assert sha(ROOT/rel)==hash_before,"protected page altered: "+rel
    data=(ROOT/"index.html").read_text("utf-8")
    assert data.count(CARD_ID)==1
    row=json.loads(re.search(r'window\.ZOMOROD_ORBIT_DATA=(\{.*?\});</script>',data,re.S).group(1))
    cards=next(r["cards"] for r in row["rows"] if r["id"]==ROW_ID)
    assert cards[0]["id"]==CARD_ID and cards[0]["canonicalUrl"]=="/farm-wars/"
    assert any(c.get("slug")=="game-development" for c in cards[1:])
    print("RIVER_PULSE_RELEASE_AND_UNTOUCHED_FILES=PASS")
def rollback():
    try:rollback_home()
    finally:
      try:rollback_game()
      finally:rollback_preview()
def main():
    global RUN,STAGE
    if len(sys.argv)!=3:raise SystemExit("usage: installer.py command RUN_ID")
    command,RUN=sys.argv[1:]
    assert re.fullmatch(r"[0-9]{4,15}",RUN)
    STAGE=Path("/home/zomorod2/.farm-dominion-v4-"+RUN)
    assert STAGE.is_dir() and not STAGE.is_symlink()
    mapping={"prepare":prepare,"preview":preview,"game":game,"home":home,
             "verify":verify,"artwork":artwork,"rollback":rollback,"rollback_game":rollback_game,
             "rollback_preview":rollback_preview,"rollback_home":rollback_home}
    if command not in mapping:raise SystemExit("invalid command")
    mapping[command]()
if __name__=="__main__":main()
