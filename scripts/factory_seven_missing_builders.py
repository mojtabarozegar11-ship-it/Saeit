#!/usr/bin/env python3
"""Seven missing-family engineering builders, isolated PRIVATE candidates.

Each adapter makes actual runnable source/output and measures it. A ZIP of
source is never represented as an APK, AppImage, ONNX, PTH or spoken MP3.
This is a dependency-aware production entrypoint, NOT QA1000 certification.
Python 3.8+ with optional local ffmpeg/espeak and onnx libraries.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import wave
import zipfile

FAMILIES = ("F12", "F13", "F16", "F17", "F23", "F26", "F40")
LABELS = {
    "F12": "mobile_puzzle_game", "F13": "desktop_puzzle_game",
    "F16": "mobile_inventory_app", "F17": "desktop_inventory_software",
    "F23": "offline_ai_assistant", "F26": "machine_learning_model",
    "F40": "narrated_audio_lessons",
}
NATIVE_REQUIRED = {
    "F12": (".apk", ".aab"), "F13": (".exe", ".AppImage"),
    "F16": (".apk", ".aab"), "F17": (".zip",),
    "F23": (".py", ".json", ".zip"), "F26": (".onnx", ".pth"),
    "F40": (".mp3", ".vtt"),
}
HERE = Path(__file__).resolve().parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

def jsonbytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)+"\n").encode("utf8")

def put(folder, name, contents):
    path = folder/name
    path.write_bytes(contents if isinstance(contents, bytes) else contents.encode("utf8"))
    return name

def run(command, timeout=35):
    return subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=timeout, universal_newlines=True, check=True)

# These are original small, runnable applications; not production-quality
# mobile-store binaries or a claim to surpass existing commercial products.
MOBILE_GAME = r"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gem Route — offline puzzle</title>
<style>body{background:#132333;color:#eff7f7;font:18px system-ui;text-align:center}
#board{display:grid;grid-template-columns:repeat(6,1fr);width:min(90vw,420px);
margin:auto;gap:4px}button{font:inherit;min-height:48px;border:0;border-radius:8px}
.tile{background:#28485c;color:#ffe5ac}.wall{background:#4b3f5b}
button:focus{outline:3px solid #ffe5ac}nav{margin:12px}</style>
<h1>Gem Route</h1><p id="message" aria-live="polite">Move to the star, avoid walls.</p>
<div id="board" aria-label="Six by six puzzle grid"></div><nav>
<button data-m="up">↑</button><button data-m="left">←</button>
<button data-m="down">↓</button><button data-m="right">→</button>
<button id="next">Next level</button></nav><script src="game.js"></script></html>"""
GAME_JS = r"""'use strict';
let levels=[],index=0,player=0;
const board=document.getElementById('board'),msg=document.getElementById('message');
function render(){
  board.replaceChildren();
  const level=levels[index];
  for(let i=0;i<36;i++){
    let b=document.createElement('button');b.type='button';
    b.className='tile'+(level.walls.includes(i)?' wall':'');
    b.textContent=i===player?'◆':i===level.goal?'★':level.walls.includes(i)?'×':'·';
    b.setAttribute('aria-label','cell '+i+' '+b.textContent);b.disabled=true;
    board.append(b);
  }
}
function move(delta){
  const n=player+delta;
  if(n<0||n>=36||((delta===1||delta===-1)&&Math.floor(n/6)!==Math.floor(player/6))
    ||levels[index].walls.includes(n))return;
  player=n;render();
  if(player===levels[index].goal)msg.textContent='Level '+(index+1)+' completed!';
}
function start(i){index=i;player=levels[i].start;msg.textContent='Level '+(i+1)+' of '+levels.length;render();}
const keys={ArrowUp:-6,ArrowDown:6,ArrowLeft:-1,ArrowRight:1};
document.addEventListener('keydown',e=>{if(Object.prototype.hasOwnProperty.call(keys,e.key)){
 e.preventDefault();move(keys[e.key]);}});
document.querySelectorAll('[data-m]').forEach(b=>b.addEventListener('click',
()=>move({up:-6,down:6,left:-1,right:1}[b.dataset.m])));
document.getElementById('next').addEventListener('click',()=>start((index+1)%levels.length));
fetch('levels.json').then(r=>r.json()).then(d=>{levels=d;start(0);})
.catch(()=>{msg.textContent='Serve this directory using python3 -m http.server on localhost';});
"""
DESKTOP_GAME = r'''"""Gem Route: playable 48-level terminal puzzle; no external dependencies."""
import argparse
import json
from pathlib import Path
def move(level, position, direction):
    offsets={"w":-6,"s":6,"a":-1,"d":1}
    if direction not in offsets: return position
    next_position=position+offsets[direction]
    if not 0<=next_position<36: return position
    if direction in ("a","d") and next_position//6!=position//6: return position
    return position if next_position in level["walls"] else next_position
def draw(level, position):
    return "\n".join(" ".join("@" if i==position else
        "*" if i==level["goal"] else "#" if i in level["walls"] else "."
        for i in range(y*6,y*6+6)) for y in range(6))
def main():
    p=argparse.ArgumentParser();p.add_argument("--self-test",action="store_true")
    p.add_argument("--level",type=int,default=1);a=p.parse_args()
    levels=json.loads((Path(__file__).parent/"levels.json").read_text("utf8"))
    if a.self_test:
        assert len(levels)==48
        for item in levels:
            assert len(set(item["walls"]))==len(item["walls"])
            assert item["start"] not in item["walls"] and item["goal"] not in item["walls"]
            assert all(0<=v<36 for v in item["walls"])
            assert move(item,item["start"],"invalid")==item["start"]
        print("48_LEVEL_ENGINE_CHECK_PASS");return
    if not 1<=a.level<=len(levels):p.error("level out of range")
    level=levels[a.level-1];position=level["start"]
    while True:
        print(draw(level,position))
        if position==level["goal"]:print("Solved!");break
        direction=input("w/a/s/d move, q quit: ").strip().lower()
        if direction=="q":break
        position=move(level,position,direction)
if __name__=="__main__":main()
'''
MOBILE_APP = r"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Field Ledger — private offline inventory</title>
<style>body{background:#142a33;color:#f5f9f9;font:18px system-ui;padding:18px}
main{max-width:650px;margin:auto}input,select,button{font:inherit;padding:10px;max-width:100%}
li{padding:12px;border-bottom:1px solid #658}button:focus,input:focus{outline:3px solid gold}</style>
<main><h1>Field Ledger</h1><p>No account, remote server or synchronization.</p>
<form id="f"><label>Item <input id="name" required maxlength="70"></label>
<label>Quantity <input id="quantity" required type="number" min="0" max="1000000" step="1"></label>
<button>Save entry</button></form><button id="export">Export local JSON</button>
<p id="status" role="status"></p><ul id="items"></ul></main><script src="app.js"></script></html>"""
APP_JS = r"""'use strict';
const KEY='field_ledger_local_v1',items=document.getElementById('items');
function get(){try{let v=JSON.parse(localStorage.getItem(KEY)||'[]');
return Array.isArray(v)?v.slice(0,200):[]}catch(_){return []}}
function show(){items.replaceChildren();get().forEach((v,i)=>{
const li=document.createElement('li'),b=document.createElement('button');
li.append(document.createTextNode(v.name+' — '+v.quantity+' '));
b.textContent='Remove';b.addEventListener('click',()=>{
let rows=get();rows.splice(i,1);localStorage.setItem(KEY,JSON.stringify(rows));show()});
li.append(b);items.append(li)})}
document.getElementById('f').addEventListener('submit',e=>{
e.preventDefault();const name=document.getElementById('name').value.trim(),
count=Number(document.getElementById('quantity').value),rows=get();
if(name.length<1||name.length>70||!Number.isSafeInteger(count)||count<0||count>1000000
||rows.length>=200){document.getElementById('status').textContent='Invalid input or storage full';return}
rows.push({name,quantity:count});localStorage.setItem(KEY,JSON.stringify(rows));
e.target.reset();show()});
document.getElementById('export').addEventListener('click',()=>{
const blob=new Blob([JSON.stringify(get(),null,2)],{type:'application/json'});
const a=document.createElement('a');a.href=URL.createObjectURL(blob);
a.download='field-ledger-export.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)});
show();
"""
DESKTOP_APP = r'''"""Offline CSV inventory and valuation, Python 3.8+, no cloud or payments."""
import argparse
import csv
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
def summarize(rows):
    value=Decimal("0");count=0
    for row in rows:
        try:
            quantity=int(row["quantity"]);price=Decimal(row["unit_price"])
        except (KeyError,ValueError,InvalidOperation,TypeError):
            raise ValueError("INVALID_INVENTORY_ROW")
        if quantity<0 or quantity>1000000 or price<0 or price>1000000000 or not price.is_finite():
            raise ValueError("INVALID_INVENTORY_RANGE")
        value+=quantity*price;count+=quantity
    return {"total_quantity":count,"inventory_value":str(value)}
def main():
    p=argparse.ArgumentParser();p.add_argument("--csv");p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    if args.self_test:
        assert summarize([{"quantity":"3","unit_price":"1.25"}])=={
            "total_quantity":3,"inventory_value":"3.75"}
        try:summarize([{"quantity":"-1","unit_price":"10"}])
        except ValueError:pass
        else:raise AssertionError("invalid rows accepted")
        print("INVENTORY_ENGINE_CHECK_PASS");return
    if not args.csv:p.error("--csv path required")
    with Path(args.csv).open(encoding="utf8",newline="") as f:
        print(json.dumps(summarize(csv.DictReader(f)),sort_keys=True))
if __name__=="__main__":main()
'''
MODEL_RUNTIME = r'''"""A reproducible synthetic regression baseline, NOT real-world ML certification."""
import argparse
import json
from pathlib import Path
def predict(model,x):
    if len(x)!=2 or not all(isinstance(v,(int,float)) for v in x):
        raise ValueError("EXPECTED_TWO_NUMERIC_FEATURES")
    return model["bias"]+sum(a*b for a,b in zip(model["weights"],x))
def main():
    p=argparse.ArgumentParser();p.add_argument("--model",type=int,default=1)
    p.add_argument("--x1",type=float,default=1.0);p.add_argument("--x2",type=float,default=1.0)
    p.add_argument("--self-test",action="store_true");a=p.parse_args()
    items=json.loads((Path(__file__).parent/"models.json").read_text())
    assert len(items)==48
    if a.self_test:
        for model in items:
            assert model["mae"]<0.5 and len(model["weights"])==2
        print("48_SYNTHETIC_MODELS_TEST_PASS");return
    if not 1<=a.model<=48:p.error("model index out of range")
    print(predict(items[a.model-1],[a.x1,a.x2]))
if __name__=="__main__":main()
'''

def levels():
    records=[]
    for i in range(48):
        # A guaranteed unobstructed path from 0 to 35 runs along top row
        # and then down the final column, with distinct extra obstacles.
        forbidden=set(range(6))|{5+6*n for n in range(6)}
        walls=sorted({[6,12,18,24,30,31][j] for j in range(6) if ((i+1)>>j)&1}-forbidden)
        records.append({"id":"level_%02d"%(i+1),"start":0,"goal":35,"walls":walls,
                        "difficulty":1+i//8,"theme":i%12})
    return records

def train_model(i):
    # Deterministic gradient descent on distinct synthetic measurements.
    samples=[(x/10.0,y/10.0) for x in range(1,9) for y in range(1,9)]
    truth=(i+2)/11.0;w=[0.0,0.0];bias=0.0
    for _ in range(2200):
        g1=g2=gb=0.0
        for x,y in samples:
            target=truth*x+(truth/2)*y+(i%7)/13.0
            diff=w[0]*x+w[1]*y+bias-target
            g1+=diff*x;g2+=diff*y;gb+=diff
        w[0]-=0.2*g1/64;w[1]-=0.2*g2/64;bias-=0.2*gb/64
    mae=sum(abs(w[0]*x+w[1]*y+bias-(truth*x+truth/2*y+(i%7)/13.0))
            for x,y in samples)/64
    return {"id":"model_%02d"%(i+1),"weights":w,"bias":bias,"mae":mae,
            "data_origin":"deterministic synthetic examples; no domain performance claim"}

def audio_available():
    return shutil.which("espeak-ng") or shutil.which("espeak")

def media_ffmpeg():
    # User-controlled binary override is deliberately not executed; only the
    # verified VPS toolchain bin or system package is accepted.
    location=Path(os.environ.get("FACTORY_TOOLCHAIN_BIN",""))
    candidate=location/"ffmpeg" if location.is_absolute() and location.name=="bin" else None
    if candidate and candidate.is_file() and not candidate.is_symlink():
        return str(candidate)
    return shutil.which("ffmpeg")

def create(root,family):
    root=Path(root)
    if not root.is_dir() or root.is_symlink():raise ValueError("PRIVATE_FACTORY_ROOT_REQUIRED")
    if family not in FAMILIES:raise ValueError("UNKNOWN_FAMILY")
    name="fieldwork_"+LABELS[family]+"_pilot"
    base=root/"engineering-gaps"/"seven-builders"/name
    if base.is_symlink() or base.parent.is_symlink():raise ValueError("UNSAFE_DESTINATION")
    base.mkdir(parents=True,exist_ok=True,mode=0o700)
    stage=Path(tempfile.mkdtemp(prefix=".incoming-",dir=str(base)))
    status="source_pilot_only";missing=[];checks=[]
    try:
        package=stage/name;package.mkdir(mode=0o700)
        if family in ("F12","F13"):
            collection=levels()
            put(package,"levels.json",jsonbytes(collection))
            if family=="F12":
                put(package,"index.html",MOBILE_GAME);put(package,"game.js",GAME_JS)
                if shutil.which("node"):
                    run(["node","--check",str(package/"game.js")])
                    checks.append("real_javascript_parse_check")
                else:missing.append("JavaScript parser and device runtime smoke test")
                missing.extend(["Android SDK / signed production APK or AAB", "real-device touch and performance QA"])
            else:
                put(package,"game.py",DESKTOP_GAME)
                run([sys.executable,str(package/"game.py"),"--self-test"])
                missing=["signed EXE or AppImage distribution", "desktop GUI/device QA"]
                checks.append("48_level_executable_terminal_game")
            assert len(collection)==48 and len({x["id"] for x in collection})==48
            checks.append("48_distinct_level_specs")
        elif family=="F16":
            put(package,"index.html",MOBILE_APP);put(package,"app.js",APP_JS)
            if shutil.which("node"):
                run(["node","--check",str(package/"app.js")])
                checks.append("real_javascript_parse_check")
            else:missing.append("JavaScript parser and mobile runtime smoke test")
            collection=[{"id":"item_%02d"%(i+1),"name":"Inventory sample %02d"%(i+1),
                         "quantity":i+1} for i in range(48)]
            put(package,"examples.json",jsonbytes(collection))
            missing.extend(["Android SDK / signed APK or AAB", "automated mobile storage and accessibility QA"])
            checks.append("offline_inventory_source_with_48_distinct_examples")
        elif family=="F17":
            put(package,"desktop.py",DESKTOP_APP)
            put(package,"sample.csv","quantity,unit_price\n3,1.25\n7,2.50\n")
            run([sys.executable,str(package/"desktop.py"),"--self-test"])
            collection=[{"id":"inventory_%02d"%(i+1),"quantity":i+1,
                         "unit_price":str((i+3)/4)} for i in range(48)]
            put(package,"cases.json",jsonbytes(collection))
            checks.append("real_decimal_csv_command_line_tests")
        elif family=="F26":
            collection=[train_model(i) for i in range(48)]
            assert max(x["mae"] for x in collection)<0.5
            put(package,"models.json",jsonbytes(collection))
            put(package,"predict.py",MODEL_RUNTIME)
            run([sys.executable,str(package/"predict.py"),"--self-test"])
            checks.append("48_fitted_and_executable_synthetic_baselines")
            # A model JSON is not an ONNX or Torch state_dict.
            missing=["ONNX or PTH native export with verified runtime",
                     "real representative training data and independent ML audit"]
        elif family=="F40":
            collection=[{"id":"lesson_%02d"%(i+1),
                         "text":"Lesson %d. Check your source records. Record the result. Review the decision before acting."%(i+1)}
                        for i in range(48)]
            put(package,"transcripts.json",jsonbytes(collection))
            voice=audio_available();ffmpeg=media_ffmpeg()
            if voice and ffmpeg:
                cues=[]
                for index,item in enumerate(collection):
                    wav=package/(item["id"]+".wav")
                    mp3=package/(item["id"]+".mp3")
                    run([voice,"-v","en","-s","145","-w",str(wav),item["text"]])
                    with wave.open(str(wav),"rb") as f:
                        seconds=f.getnframes()/f.getframerate()
                    run([ffmpeg,"-hide_banner","-loglevel","error","-y","-i",str(wav),
                         "-codec:a","libmp3lame","-q:a","5",str(mp3)],timeout=20)
                    assert mp3.read_bytes()[:3]==b"ID3" or mp3.read_bytes()[:2] in (b"\xff\xfb",b"\xff\xf3")
                    def stamp(t):
                        ms=int(round(t*1000));return "%02d:%02d:%02d.%03d"%(ms//3600000,(ms//60000)%60,(ms//1000)%60,ms%1000)
                    vtt="WEBVTT\n\n00:00:00.000 --> "+stamp(seconds)+"\n"+item["text"]+"\n"
                    put(package,item["id"]+".vtt",vtt)
                    wav.unlink()
                    cues.append(seconds)
                checks.append("48_real_speech_mp3_and_timed_vtt")
            else:
                missing=["espeak/espeak-ng voice engine and ffmpeg native MP3 encoder"]
        elif family=="F23":
            # Its audited 50-stage builder is intentionally separate; never
            # substitute a toy JSON recipe for a verified AI model.
            required=("factory_build50_f23_assistant.py",
                      "factory_f23_assistant_independent_review.py",
                      "factory_f23_offline_assistant_runtime.py",
                      "factory_build_50.py")
            if all((HERE/f).is_file() for f in required):
                spec=importlib.util.spec_from_file_location("f23_native_producer",str(HERE/required[0]))
                mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
                result=mod.build(root)
                checks.append("existing_50_stage_producer:"+result["status"])
                if result["status"] in ("technical_50_stage_build_completed",
                                        "unchanged_verified_technical_product"):
                    status="verified_f23_native_offline_assistant"
                else:missing.append("F23 BUILD50 structural rework")
            else:missing.append("F23 pinned builder and independent reviewer installation")
            put(package,"f23_run_receipt.json",jsonbytes({"checks":checks,"missing":missing}))
            missing.append("genuine generative AI model capability unverified")
        put(package,"README.txt",
            "Private, reproducible engineering sample for "+family+".\n"
            "The 1000-point independent professional QA, native consumer "
            "distribution, source licensing and owner release are NOT approved.\n"
            "Native and specialist missing evidence: "+", ".join(missing)+".\n")
        filenames=sorted(p.name for p in package.iterdir() if p.is_file())
        assert filenames and len(set(filenames))==len(filenames)
        archive=stage/(name+"-internal-qa.zip")
        with zipfile.ZipFile(str(archive),"w",zipfile.ZIP_DEFLATED) as z:
            for filename in filenames:
                info=zipfile.ZipInfo(name+"/"+filename,(2020,1,1,0,0,0))
                info.compress_type=zipfile.ZIP_DEFLATED
                z.writestr(info,(package/filename).read_bytes())
        with zipfile.ZipFile(str(archive)) as z:
            assert z.testzip() is None
            assert sorted(z.namelist())==[name+"/"+x for x in filenames]
        if family=="F17":status="verified_source_zip_with_executed_cli_tests"
        if family=="F40" and not missing:status="verified_synthesized_mp3_and_vtt_private_pilot"
        if family=="F13":status="verified_executable_source_with_distribution_hold"
        if family=="F26":status="verified_synthetic_training_with_native_hold"
        if family in ("F12","F16"):status="web_source_with_android_build_hold"
        receipt={"schema":"zomorodmelal.factory.seven-gap-private.v1",
                 "family_id":family,"product_id":name,"status":status,
                 "private_archive_sha256":sha(archive.read_bytes()),
                 "source_files":{x:sha((package/x).read_bytes()) for x in filenames},
                 "actual_checks":checks,"unresolved_native_or_specialist_gates":missing,
                 "native_distribution_verified":family=="F40" and not missing,
                 "independent_quality_1000_passed":False,
                 "commercial_release_allowed":False,"public_listing_enabled":False}
        put(stage,"technical_receipt.json",jsonbytes(receipt))
        dest=base/receipt["private_archive_sha256"][:20]
        if dest.is_symlink():raise RuntimeError("PRIVATE_VERSION_SYMLINK")
        if dest.exists():
            # Version old private evidence safely; never overwrite a product
            # whose source/receipts differ without an explicit migration.
            old=dest/"technical_receipt.json"
            if old.is_file() and not old.is_symlink():
                previous=json.loads(old.read_text("utf8"))
                if previous.get("private_archive_sha256")==receipt["private_archive_sha256"]:
                    return dict(receipt,status="unchanged_private_candidate")
            raise RuntimeError("PRIVATE_PRODUCT_VERSION_HASH_COLLISION")
        os.replace(str(stage),str(dest))
        return receipt
    finally:
        if stage.exists():shutil.rmtree(str(stage))

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--factory-private",required=True)
    p.add_argument("--family",choices=FAMILIES)
    p.add_argument("--tick",action="store_true",help="Build one family in the bounded periodic cycle")
    args=p.parse_args()
    if args.family and args.tick:p.error("--family and --tick are mutually exclusive")
    selected=(FAMILIES[(int(time.time())//3600)%len(FAMILIES)],) if args.tick else ((args.family,) if args.family else FAMILIES)
    results=[]
    for family in selected:
        try:results.append(create(args.factory_private,family))
        except Exception as exc:
            # One failed specialist environment must not prevent work on other
            # families. Never record a pass for a failure.
            results.append({"family_id":family,"status":"builder_failed",
                            "error_type":type(exc).__name__,
                            "independent_quality_1000_passed":False})
    print("ZOMORODMELAL_SEVEN_GAP_BUILDERS="+json.dumps(results,sort_keys=True))
    if any(r["status"]=="builder_failed" for r in results):return 2
    return 0
if __name__=="__main__":sys.exit(main())
