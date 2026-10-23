#!/usr/bin/env python3
"""Independent VPS-side public HTTPS/byte-hash verification (outside cPanel)."""
from pathlib import Path
import hashlib,json,subprocess,sys,tempfile,os,time
BASE="https://zomorodmelal.ir/"
def get(rel,run):
    url=BASE+rel+("?release="+run)
    errors=[]
    for attempt in range(3):
        with tempfile.NamedTemporaryFile(delete=False) as f:tmp=f.name
        try:
            cmd=["curl","--fail","--location","--silent","--show-error",
                 "--connect-timeout","8","--max-time","30",
                 "--header","Cache-Control: no-cache",
                 "--header","User-Agent: ZomorodVPSIndependentQA/1",
                 "--output",tmp,"--write-out","%{http_code}",url]
            p=subprocess.run(cmd,capture_output=True,text=True,timeout=38)
            if p.returncode==0 and p.stdout.strip()=="200":
                return Path(tmp).read_bytes()
            errors.append("rc="+str(p.returncode)+" http="+p.stdout.strip()+" "+p.stderr[-140:])
        except Exception as e:errors.append(type(e).__name__+": "+str(e)[:140])
        finally:
            try:os.unlink(tmp)
            except OSError:pass
        if attempt<2:time.sleep(2+attempt*2)
    raise RuntimeError("VPS_PUBLIC_HTTPS_FAILED "+url+" "+repr(errors))
def main(manifest,run,preflight=False):
    if preflight:
        for rel in ("","agriculture/","games/seed-guardian/"):
            data=get(rel,run)
            assert len(data)>500,rel
            print("VPS_EXTERNAL_PREFLIGHT_200",rel or "/")
        return
    m=json.loads(Path(manifest).read_text("utf-8"))
    assert len(m)==6
    for rel,meta in m.items():
        url=rel.removesuffix("index.html")
        raw=get(url,run)
        if hashlib.sha256(raw).hexdigest()!=meta["sha256"]:
            raise RuntimeError("VPS_PUBLIC_SHA256_MISMATCH "+url)
        print("VPS_INDEPENDENT_PUBLIC_200_SHA256_PASS",BASE+url)
    for rel,terms in {
        "agriculture/water-soil/":["emitter-uniformity/","emitter-uniformity-guide/","irrigation-uniformity.webp"],
        "agriculture/greenhouse/":["dewpoint-vpd/","dewpoint-vpd-guide/","greenhouse-dewpoint.webp"],
    }.items():
        s=get(rel,run).decode("utf-8")
        assert "ZM-AGRICULTURE-TOOLS-20261023-B" in s
        for term in terms:assert term in s,(rel,term)
        print("VPS_EXTERNAL_CATEGORY_CARD_IMAGE_PASS",rel)
    old=(
        "","agriculture/","games/","games/water-path/","games/air-supremacy/",
        "games/seed-guardian/","agriculture/water-soil/irrigation-planner/",
        "agriculture/greenhouse/ventilation-estimator/",
        "agriculture/water-soil/research-lab-20261023/",
        "agriculture/water-soil/irrigation-need.html",
        "agriculture/seeds/seeding-rate.html",
        "agriculture/greenhouse/planting-planner/",
        "agriculture/livestock/feed-dry-matter/","agriculture/digital-lab/",
    )
    for rel in old:
        assert len(get(rel,run))>200,rel
        print("VPS_EXTERNAL_PROTECTED_200",rel or "/")
    print("VPS_INDEPENDENT_ALL_SIX_SHA_TWO_CARDS_FOURTEEN_OLD_ROUTES_PASS")
if __name__=="__main__":
    if len(sys.argv)<3:raise SystemExit("usage: verifier.py manifest run [preflight]")
    main(sys.argv[1],sys.argv[2],len(sys.argv)>3 and sys.argv[3]=="preflight")
