#!/usr/bin/env python3
"""MojPlayWin isolated Asset Lab: generate three original WebP diagrams, manifest,
verify every byte, and install/rollback exactly one versioned public directory.
Never edits PHP, .htaccess, Django, Passenger, or existing release directories.
"""
import fcntl
import hashlib
import json
import os
import pwd
import re
import shutil
import stat
import sys
from pathlib import Path

HOME=Path("/home/zomorod2")
SITE=HOME/"mojplaywin.com"
PARENT=SITE/"mpw-editorial"/"asset-lab"
TARGET=PARENT/"20261023"
PRIVATE=HOME/".private_mpw_assetlab_20261023"
RELEASE="ASSETLAB-20261023-01"
HTACCESS_SHA="6d06dc358b118ca59843941cd79c627eb4792a3584b0d11b4de7ed49b8552b63"
PHP=SITE/"design-preview-20261017"/"_mpw_dynamic_main_shell_20261019.php"
IMAGES={
 "convert.webp":"Illustration of image conversion from large source pixels to a compact WebP card",
 "budget.webp":"Illustration comparing a large source file against a smaller image delivery budget",
 "responsive.webp":"Illustration of three responsive image widths for mobile tablet and desktop",
}
FILES=("index.html","release.json",*(f"assets/{name}" for name in IMAGES))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def owned(p):return p.exists() and not p.is_symlink() and p.stat().st_uid==os.getuid()
def verify(root):
    if not owned(root) or not root.is_dir():raise RuntimeError("Unknown release directory")
    actual=[]
    for base,dirs,files in os.walk(root,followlinks=False):
        base=Path(base)
        if not owned(base):raise RuntimeError("Unsafe release directory owner")
        for d in dirs:
            if not owned(base/d):raise RuntimeError("Symlink or wrong directory owner")
        for name in files:
            p=base/name
            if not owned(p) or not p.is_file():raise RuntimeError("Unsafe release file")
            actual.append(str(p.relative_to(root)))
    if sorted(actual)!=sorted(FILES):raise RuntimeError("Unexpected release files "+repr(actual))
    manifest=json.loads((root/"release.json").read_text(encoding="utf8"))
    if manifest.get("release_id")!=RELEASE or manifest.get("locale")!="en":
        raise RuntimeError("Unexpected release identity")
    if manifest.get("assets")!=IMAGES:raise RuntimeError("Image alt metadata mismatch")
    expected=manifest.get("files_sha256",{})
    if sorted(expected)!=sorted(p for p in FILES if p!="release.json"):
        raise RuntimeError("Manifest hash set mismatch")
    for rel in FILES:
        p=root/rel
        size=p.stat().st_size
        if not 50<size<120000:raise RuntimeError("Unsafe release size "+rel)
        if rel.endswith(".webp"):
            b=p.read_bytes()
            if b[:4]!=b"RIFF" or b[8:12]!=b"WEBP":raise RuntimeError("Fake WebP asset "+rel)
        elif b"\0" in p.read_bytes():raise RuntimeError("Unexpected null byte")
        if rel!="release.json" and digest(p)!=expected[rel]:
            raise RuntimeError("Manifest SHA mismatch "+rel)
    html=(root/"index.html").read_text(encoding="utf8")
    if "ASSET_LAB_FUNCTIONAL_TEST_PASS" not in html or RELEASE not in html:
        raise RuntimeError("Browser functional selftest/version absent")
    for name,alt in IMAGES.items():
        if "assets/"+name not in html or 'alt="'+alt+'"' not in html:
            raise RuntimeError("Image path or alt missing "+name)
    return {rel:digest(root/rel) for rel in FILES}
def build(output):
    from PIL import Image, ImageDraw, ImageFont, features
    if not features.check("webp"):raise RuntimeError("Pillow has no WebP encoder")
    if output.exists() or output.is_symlink():raise RuntimeError("Build target exists")
    output.mkdir(parents=True,mode=0o755)
    (output/"assets").mkdir()
    src=Path("mpw-editorial/asset-lab/20261023/index.html")
    if not src.is_file():raise RuntimeError("Missing original HTML")
    shutil.copyfile(src,output/"index.html")
    try:font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",29)
    except OSError:font=ImageFont.load_default()
    try:small=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",17)
    except OSError:small=ImageFont.load_default()
    for idx,name in enumerate(IMAGES):
        w,h=640,360
        img=Image.new("RGB",(w,h))
        px=img.load()
        tones=[(11,37,56),(19,31,67),(12,43,49)]
        base=tones[idx]
        for y in range(h):
            for x in range(w):
                px[x,y]=(min(255,base[0]+x//28+y//35),min(255,base[1]+x//26),min(255,base[2]+y//17))
        d=ImageDraw.Draw(img)
        d.rounded_rectangle((20,20,620,340),radius=24,outline=(106,216,197),width=3)
        if idx==0:
            d.rounded_rectangle((58,85,250,255),radius=17,fill=(47,74,104),outline=(143,178,214),width=4)
            for y in range(5):
                for x in range(6):
                    color=(240,174,110) if (x+y)%3==0 else (90,182,213)
                    d.rectangle((82+x*25,113+y*23,100+x*25,129+y*23),fill=color)
            d.line([(277,172),(352,172)],fill=(255,215,145),width=8)
            d.polygon([(357,172),(332,158),(332,186)],fill=(255,215,145))
            d.rounded_rectangle((379,93,580,247),radius=17,fill=(19,79,82),outline=(112,238,202),width=4)
            d.text((411,143),"WebP",font=font,fill=(222,255,238))
            label="CONVERT · REAL WEBP"
        elif idx==1:
            d.rounded_rectangle((65,101,573,151),radius=14,fill=(76,103,138))
            d.rounded_rectangle((65,196,288,246),radius=14,fill=(93,223,190))
            d.text((82,111),"ORIGINAL",font=small,fill=(245,251,255))
            d.text((82,208),"WEBP",font=small,fill=(9,45,55))
            d.text((340,200),"BYTES SAVED",font=small,fill=(240,217,149))
            label="MEASURE · NEVER GUESS"
        else:
            for x,y,wid,hei in ((74,119,105,158),(248,101,150,178),(468,74,116,205)):
                d.rounded_rectangle((x,y,x+wid,y+hei),radius=13,fill=(24,76,93),outline=(122,240,204),width=4)
                d.rounded_rectangle((x+11,y+15,x+wid-11,y+hei-24),radius=6,fill=(39,116,128))
                d.line([(x+21,y+50),(x+wid-22,y+50)],fill=(255,214,141),width=5)
            label="RESPONSIVE · 3 REAL SIZES"
        d.text((48,39),label,font=small,fill=(255,220,162))
        img.save(output/"assets"/name,format="WEBP",quality=75,method=6)
    manifest={
      "release_id":RELEASE,"locale":"en","built_for":"MojPlayWin",
      "assets":IMAGES,
      "files_sha256":{p:digest(output/p) for p in FILES if p!="release.json"},
      "privacy":"all visitor image processing stays in the browser",
      "tool":"Image Delivery Lab",
      "guides_count":10,
    }
    (output/"release.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf8")
    result=verify(output)
    print("ASSETLAB_BUILD_VERIFIED",json.dumps(result,sort_keys=True))
def env():
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":raise RuntimeError("Wrong cPanel user")
    for p in (HOME,SITE,SITE/"mpw-editorial",SITE/".htaccess",PHP):
        if not owned(p):raise RuntimeError("Wrong production path owner: "+str(p))
    if digest(SITE/".htaccess")!=HTACCESS_SHA:raise RuntimeError("Protected .htaccess changed")
    if "MPW_NEXTWAVE_MAIN_NAV_20261023" not in PHP.read_text(encoding="utf8"):
        raise RuntimeError("Known production shell marker missing")
def operate(action,run,sha):
    if not re.fullmatch(r"[0-9]{8,20}",run) or not re.fullmatch(r"[0-9a-f]{40}",sha):
        raise RuntimeError("Invalid deployment identity")
    env()
    if not owned(PRIVATE) or not PRIVATE.is_dir() or PRIVATE.stat().st_dev!=SITE.stat().st_dev:
        raise RuntimeError("Private staging directory unsafe")
    stage=PRIVATE/("staging-"+run)/"20261023"
    receipt=PRIVATE/("receipt-"+run+".json")
    with open(PRIVATE/"lock","a+") as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        if action=="install":
            if TARGET.exists() or TARGET.is_symlink():raise RuntimeError("Never overwrite published release")
            if receipt.exists() or receipt.is_symlink():raise RuntimeError("Duplicate receipt")
            hashes=verify(stage)
            if PARENT.exists() or PARENT.is_symlink():
                if not owned(PARENT) or not PARENT.is_dir():raise RuntimeError("Untrusted release parent")
            else:PARENT.mkdir(mode=0o755)
            for base,dirs,files in os.walk(stage):
                os.chmod(base,0o755)
                for name in files:os.chmod(Path(base)/name,0o644)
            info={"release_id":RELEASE,"run":run,"commit":sha,"files_sha256":hashes,"target":str(TARGET)}
            with open(receipt,"x") as r:
                json.dump(info,r,sort_keys=True);r.flush();os.fsync(r.fileno())
            if TARGET.exists() or TARGET.is_symlink():raise RuntimeError("Concurrent deployment collision")
            os.replace(stage,TARGET)
            if verify(TARGET)!=hashes:raise RuntimeError("Post-rename hash mismatch")
            print("ASSETLAB_ATOMIC_DEPLOY",json.dumps(info,sort_keys=True))
        elif action=="rollback":
            if not receipt.is_file() or receipt.is_symlink():
                print("ASSETLAB_NOT_INSTALLED");return
            info=json.loads(receipt.read_text())
            if info.get("run")!=run or info.get("commit")!=sha or info.get("release_id")!=RELEASE:
                raise RuntimeError("Rollback receipt identity mismatch")
            if not TARGET.exists():print("ASSETLAB_NO_TARGET");return
            if verify(TARGET)!=info.get("files_sha256"):
                raise RuntimeError("Concurrent edit: refuse destructive rollback")
            shutil.rmtree(TARGET)
            print("ASSETLAB_EXACT_ROLLBACK",run)
        else:raise RuntimeError("Unknown command")
if __name__=="__main__":
    if len(sys.argv)==3 and sys.argv[1]=="build":build(Path(sys.argv[2]))
    elif len(sys.argv)==3 and sys.argv[1]=="verify":print("ASSETLAB_VERIFY_PASS",json.dumps(verify(Path(sys.argv[2]))))
    elif len(sys.argv)==4:operate(*sys.argv[1:])
    else:raise SystemExit("build PATH | verify PATH | install RUN SHA | rollback RUN SHA")
