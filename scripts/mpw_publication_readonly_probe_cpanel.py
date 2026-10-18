"""Read-only main-domain Apache/Passenger publication boundary probe. No writes."""
import getpass,json,os,subprocess
from pathlib import Path

def main():
    assert getpass.getuser()=="zomorod2"
    home=Path("/home/zomorod2")
    cp=subprocess.run(["uapi","--output=json","DomainInfo","list_domains"],capture_output=True,text=True,timeout=25)
    print("UAPI_DOMAININFO_OK="+str(cp.returncode==0))
    if cp.returncode==0:
        try:
            top=json.loads(cp.stdout)
            def scan(obj):
                if isinstance(obj,dict):
                    if any("mojplaywin.com" in str(v).lower() for k,v in obj.items() if k in ("domain","domain_name","domainname")):
                        print("DOMAIN_MATCH="+json.dumps({k:v for k,v in obj.items() if k in ("domain","domain_name","documentroot","document_root","dir","relative_document_root","type","base_uri")},ensure_ascii=False)[:800])
                    for val in obj.values():scan(val)
                elif isinstance(obj,list):
                    for val in obj:scan(val)
            scan(top.get("result",top))
        except Exception as e: print("DOMAININFO_FORMAT_ERROR="+type(e).__name__)
    for rel in ("mojplaywin.com","public_html","public_html/mojplaywin.com","Saeit-staging","mojplaywin.com/.htaccess","mojplaywin.com/passenger_wsgi.py"):
        path=home/rel
        print("PATH_INFO="+json.dumps({"relative":rel,"exists":path.exists(),"directory":path.is_dir(),"symlink":path.is_symlink(),"mode":oct(path.stat().st_mode & 0o777) if path.exists() else None}))
        if rel.endswith(".htaccess") and path.is_file() and not path.is_symlink():
            for ln in path.read_text("utf8",errors="replace").splitlines()[:140]:
                if any(x in ln.lower() for x in ("passenger","rewrite","documentroot","directoryindex","options","fallback","handler","disable")) and not any(x in ln.lower() for x in ("secret","key=","token","password")):
                    print("HTACCESS_ROUTING="+ln[:160])
    mainroot=home/"mojplaywin.com"
    if mainroot.is_dir() and not mainroot.is_symlink():
        print("MAIN_ROOT_NAMES="+json.dumps(sorted(p.name for p in mainroot.iterdir() if p.name not in (".env",".git") and not p.is_symlink())[:100]))
        for name in ("mpw-editorial","editorial","insights","articles","robots.txt","favicon.ico"):
            path=mainroot/name
            print("PUBLISH_TARGET="+json.dumps({"name":name,"exists":path.exists(),"symlink":path.is_symlink(),"dir":path.is_dir()}))
    print("READ_ONLY_PROBE_DONE=true")
if __name__=="__main__":main()
