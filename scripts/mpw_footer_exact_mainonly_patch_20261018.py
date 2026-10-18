#!/usr/bin/env python3
"""Owner-only, atomic MojPlayWin footer patch. No shared templates, routes or Passenger restarts."""
import hashlib,json,os,pwd,re,stat,sys,tempfile
from pathlib import Path

HOME=Path("/home/zomorod2")
ROOT=HOME/"mojplaywin.com"
APP=HOME/"Saeit-staging"
PRE=ROOT/"design-preview-20261017/mpw-ten-editorials-20261018/pages"
STATIC=dict([["about-mojtaba-rozegar","24a5af9f63be2cd7f716c2336a565afdb41dde7547eec8ca038c13bf4a2c8a11"],["about","13b86a034a68f527f9e12e745142730c30b456ac16a8e2c613fb51f06fbf105b"],["agents","19e54c41db0e2baf29b7b411872b0f035540a92f0e74a1bca9406293e4d3e83c"],["company","88940442988d1e8fcf1fb7bf424f473865efda45e95cf9e8f239a01b817b27ab"],["economy","777dd116f5a56c13494423b2063fe7d3c37b726f42043169f7f3a81bdbeeb65f"],["industry","298a66165d12d0258ac074112f021eebda21f3e84ef2eff56b908e8bb49cf0ff"],["knowledge","c1969e5e6ac314d46b592d35829fee8cb5d1212afc996dd97edc43d2fe20cab6"],["market","643eb70137052321f0c89e43b4788357b157b2a430211d8dc0172d51d8da740e"],["research","932ee5dc408e62acfcb36803645846309d7b0c330da4d9994cd4e03c2b40ec9b"],["services","f8561faae7e1fcc48733f2709581f21f0f54f3bd050ac7d47e63ba67b2486598"],["studio","6f94ad96b5f1a9f58d01b3bc89a6eba01b0b2304c6bee414baaca8cda3f8c4bc"],["ventures-agriculture","23a4f82a8ed18c0834c1f08f304747443f739226c3f9a3f948c2f0103c959261"],["ventures-cafe-restaurant","afba268f3df3b59d980c3b27b1fd2a4c5307298266ec2871d81cdd4968ded58b"],["ventures-carpets","9cbd9d3ff8c69c4366d7e09943eed27b447b6e5ee182ae430c2ffa0c99de27e9"],["ventures-currency-crypto","db6a74832dd6d6fa2b4317862df283893b3f4d6dba5caa93baead61a22c48e65"],["ventures-ecommerce","40c0a577ee09653d22ea2e016f66c6ac220ba52edad533a2bd75db31b28302"],["ventures-fuel-station","2d8527f4cb667d3aff4b1d8b5d4b5833aedee7b534f3899392447e33ad24190b"],["ventures-hospitality","b862139f052fa06d5642d22550837ecf6ce2d6c8cb21efeeebf08c0475daadef"],["ventures-jewelry-gold","4143ffc4f0763cc7cf108cdf9c27d79498674c685ec58b6ed6e86a859c87b68f"]])
APP_SHA={
"core/templates/mojplaywin/footer.html":"bf282e0c7c33793c0347f8d1a1d914c124f1a2e1e28eec467abd0e2fc7430dd4",
"core/templates/brands/mojplaywin/base.html":"1f302e6d82fb3ff3a9e99a58af224d84a85cdc87358e593725be9e133e2d5303"}
MARK="mpw-founder-footer-final"
ADD=('\n<span class="'+MARK+'" data-mpw-footer-only="true" '
'style="grid-column:1/-1;flex-basis:100%;display:block;width:100%;box-sizing:border-box;'
'text-align:center;margin-top:12px;padding:16px 10px 6px;border-top:1px solid rgba(218,176,89,.38);'
'font-size:clamp(1.05rem,2vw,1.4rem);font-weight:900;letter-spacing:.065em;color:#f2cb76;'
'text-shadow:0 1px 0 #4b3418,0 2px 0 #241805,0 5px 14px rgba(214,173,85,.55);">'
'Mojtaba Roozegar</span>\n')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def verify():
    assert pwd.getpwuid(os.getuid()).pw_name=="zomorod2"
    for p in (ROOT,APP,PRE):
        if not p.is_dir() or p.is_symlink():raise RuntimeError("Unexpected directory "+str(p))
    w=ROOT/"passenger_wsgi.py"
    if not w.is_file() or w.is_symlink() or "Saeit-staging" not in w.read_text(errors="replace"):raise RuntimeError("WSGI mismatch")
    h=ROOT/".htaccess"
    if not h.is_file() or h.is_symlink():raise RuntimeError("Rewrite file mismatch")
    ht=h.read_text(errors="replace")
    for name in STATIC:
        if "/design-preview-20261017/mpw-ten-editorials-20261018/pages/"+name+".html" not in ht:raise RuntimeError("Route mismatch "+name)
def candidates():
    for name,old in STATIC.items():yield PRE/(name+".html"),old
    for name,old in APP_SHA.items():yield APP/name,old
def patch(text):
    footers=list(re.finditer(r"<footer\b[^>]*>[\s\S]*?</footer\s*>",text,re.I))
    keep=[f for f in footers if "MojPlayWin" in f.group(0) and ("mw-site-footer" in f.group(0) or "mpw-footer" in f.group(0))]
    if len(keep)!=1:raise RuntimeError("Unexpected branded footer count "+str(len(keep)))
    chosen=keep[0]; segment=chosen.group(0)
    if "Mojtaba Roozegar" in segment or MARK in segment:raise RuntimeError("Already tagged or non-unique footer")
    end=re.search(r"</footer\s*>\s*$",segment,re.I)
    if end is None:raise RuntimeError("Footer closing missing")
    offset=chosen.start()+end.start()
    updated=text[:offset]+ADD+text[offset:]
    if updated.replace(ADD,"",1)!=text or updated.count(MARK)!=1:raise RuntimeError("Non-additive patch")
    return updated
def prepare():
    verify()
    batch=[]
    for file,expected in candidates():
        if not file.is_file() or file.is_symlink():raise RuntimeError("Missing "+str(file))
        before=file.read_bytes()
        if sha(before)!=expected:raise RuntimeError("Concurrent edit "+str(file))
        after=patch(before.decode("utf8","strict")).encode("utf8")
        batch.append((file,before,after,stat.S_IMODE(file.stat().st_mode)))
    if len(batch)!=21:raise RuntimeError("Target count mismatch")
    return batch
def atom(p,raw,mode):
    if not p.is_file() or p.is_symlink():raise RuntimeError("Unsafe target")
    fd,t=tempfile.mkstemp(prefix=".mpw-founder-",dir=p.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as f:f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(t,p)
    finally:
        if os.path.exists(t):os.unlink(t)
def backup_dir(runid):
    if not re.fullmatch(r"[0-9]{9,20}",runid):raise RuntimeError("Unsafe run ID")
    return HOME/(".mpw-founder-mainonly-"+runid)
def install(runid):
    batch=prepare()
    b=backup_dir(runid)
    if b.exists() or b.is_symlink():raise RuntimeError("Backup conflict")
    b.mkdir(mode=0o700)
    records=[]
    for i,(p,old,new,mode) in enumerate(batch):
        backup=b/("%02d.bak"%i)
        with backup.open("xb") as f:f.write(old)
        os.chmod(backup,0o600)
        records.append({"path":str(p),"before":sha(old),"after":sha(new),"mode":mode,"bak":backup.name})
    (b/"manifest.json").write_text(json.dumps(records))
    changed=[]
    try:
        for p,old,new,mode in batch:
            if sha(p.read_bytes())!=sha(old):raise RuntimeError("Race detected")
            atom(p,new,mode);changed.append((p,old,mode))
            if sha(p.read_bytes())!=sha(new):raise RuntimeError("Bad postwrite checksum")
    except Exception:
        for p,old,mode in reversed(changed):
            if p.is_file() and not p.is_symlink():atom(p,old,mode)
        (b/"FAILED").write_text("restored")
        raise
    (b/"INSTALLED").write_text("yes")
    print("FOOTER_ATOMIC_INSTALLED="+str(len(changed))+" PASSENGER_RESTART=false BACKUP="+str(b),flush=True)
def rollback(runid):
    b=backup_dir(runid)
    if not b.is_dir() or b.is_symlink():raise RuntimeError("Backup absent")
    rows=json.loads((b/"manifest.json").read_text())
    for row in rows:
        p=Path(row["path"]);old=(b/row["bak"]).read_bytes()
        if sha(old)!=row["before"] or sha(p.read_bytes())!=row["after"]:raise RuntimeError("Rollback conflict")
    for row in rows:atom(Path(row["path"]),(b/row["bak"]).read_bytes(),row["mode"])
    print("ROLLBACK_COMPLETE="+str(len(rows)))
def selftest():
    x='<footer class="mw-site-footer">MojPlayWin</footer><footer class="site-footer">Zomorodmelal</footer>'
    y=patch(x)
    assert y.replace(ADD,"",1)==x
    assert MARK in y.split("</footer>")[0]
    assert "Mojtaba Roozegar" in patch('<footer class="mpw-footer">MojPlayWin</footer>')
    print("SELFTEST=PASS")
if __name__=="__main__":
    mode=sys.argv[1] if len(sys.argv)>1 else ""
    if mode=="selftest":selftest()
    elif mode=="audit":print("SAFE_TARGETS="+str(len(prepare())))
    elif mode=="install" and len(sys.argv)==3:install(sys.argv[2])
    elif mode=="rollback" and len(sys.argv)==3:rollback(sys.argv[2])
    else:raise SystemExit("selftest|audit|install RUNID|rollback RUNID")
