#!/usr/bin/env python3
"""Publish only a new /trust/index.html from an approved artifact on cPanel.
No edits to the homepage, .htaccess, database, payments or sibling sites.
Run by an authorized host operator after source review, not by CI automatically.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import tempfile
from urllib.error import HTTPError
from urllib.request import Request, urlopen

HOST = "zomorodmelal.ir"
URL = "https://" + HOST + "/trust/"
HOME = Path("/home/zomorod2")
MAX_BYTES = 200_000

def require(ok, message):
    if not ok:
        raise RuntimeError(message)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def regular(p):
    return p.is_file() and not p.is_symlink() and p.resolve() == p

def origin():
    require(os.geteuid() != 0 and pwd.getpwuid(os.geteuid()).pw_name == "zomorod2",
            "Run only as the authorized cPanel account")
    raw = subprocess.check_output(["uapi","--output=json","DomainInfo","domains_data"],
                                  stderr=subprocess.PIPE, timeout=30)
    document = json.loads(raw)
    matches = set()
    def walk(node):
        if isinstance(node, dict):
            domain = node.get("domain") or node.get("servername")
            root = node.get("documentroot") or node.get("document_root") or node.get("docroot")
            if isinstance(domain,str) and domain.lower().rstrip(".") in (HOST,"www."+HOST) and isinstance(root,str):
                matches.add(Path(root.rstrip("/")))
            for value in node.values():
                walk(value)
        elif isinstance(node,list):
            for value in node:
                walk(value)
    walk(document)
    require(len(matches)==1,"Unverified or ambiguous document root")
    root = next(iter(matches))
    require(root.is_relative_to(HOME) and root.is_dir() and root.resolve()==root
            and root.stat().st_uid==os.geteuid(),"Unsafe document root")
    return root

def get(url):
    try:
        with urlopen(Request(url,headers={"Cache-Control":"no-cache","User-Agent":"Zomorod-Scoped-Release/1.0"}),timeout=20) as r:
            require(r.geturl()==url,"Unexpected public redirect")
            return r.status,r.read(MAX_BYTES+1)
    except HTTPError as exc:
        if exc.code==404 and exc.geturl()==url:
            return 404,b""
        raise

def write_new(p,data,mode):
    with os.fdopen(os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,mode),"wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())

def main():
    a=argparse.ArgumentParser()
    a.add_argument("source",type=Path)
    a.add_argument("expected_sha256")
    a.add_argument("--publish",action="store_true",help="Explicit authorized live release")
    args=a.parse_args()
    source=args.source.absolute()
    require(regular(source) and 0<source.stat().st_size<=MAX_BYTES,"Unsafe source")
    data=source.read_bytes()
    require(re.fullmatch("[0-9a-f]{64}",args.expected_sha256) and sha(data)==args.expected_sha256,
            "Source digest mismatch")
    require(b'<link rel="canonical" href="https://zomorodmelal.ir/trust/">' in data
            and b'<html lang="fa" dir="rtl">' in data,"Unexpected source identity")
    root=origin()
    protected=[root/"index.html",root/".htaccess",
               root/"amozeshgah/index.html",root/"mohammad/index.html",root/"ghanadi/index.html"]
    require(all(regular(p) for p in protected),"Protected baseline incomplete")
    before={str(p):sha(p.read_bytes()) for p in protected}
    target=root/"trust"
    require(not target.exists() and not target.is_symlink(),"Existing trust path: no overwrite")
    status,_=get(URL)
    require(status==404,"Public route already occupied")
    print(json.dumps({"state":"ready_for_authorized_publish","source_sha256":sha(data),
                      "protected":before},ensure_ascii=False))
    if not args.publish:
        return
    backup_parent=HOME/".backups"
    require(backup_parent.is_dir() and backup_parent.resolve()==backup_parent
            and backup_parent.stat().st_uid==os.geteuid(),"Private backup root not verified")
    # Every authorized attempt retains its own recovery evidence, even after rollback.
    backup=Path(tempfile.mkdtemp(prefix="zomorod-trust-"+sha(data)[:16]+"-",dir=backup_parent))
    # Keep actual recovery bytes, not only hashes, outside the public root.
    copies={}
    for i,p in enumerate(protected):
        snapshot=backup/("protected-%02d.bin"%i)
        original=p.read_bytes()
        require(sha(original)==before[str(p)],"Concurrent protected edit during snapshot")
        write_new(snapshot,original,0o600)
        require(sha(snapshot.read_bytes())==before[str(p)],"Snapshot verification failed")
        copies[str(p)]=snapshot.name
    write_new(backup/"manifest.json",json.dumps({"source_sha256":sha(data),"protected":before,
             "snapshots":copies,"target":str(target)},ensure_ascii=False).encode(),0o600)
    write_new(backup/"approved.html",data,0o600)
    require(all(sha(p.read_bytes())==before[str(p)] for p in protected),"Concurrent protected edit")
    # An independent staging inode prevents changes to public bytes from
    # altering the private approved artifact. Never overwrite existing files.
    staged=backup/"publish-stage.html"
    write_new(staged,data,0o644)
    inode=staged.stat()
    target.mkdir(mode=0o755)
    dest=target/"index.html"
    published=False
    try:
        os.link(staged,dest,follow_symlinks=False)
        published=True
        staged.unlink()
        require(regular(dest) and sha(dest.read_bytes())==sha(data),"Published bytes differ")
        code,body=get(URL)
        require(code==200 and sha(body)==sha(data),"Public HTML differs or route unavailable")
        require(all(sha(p.read_bytes())==before[str(p)] for p in protected),"Protected file changed")
    except BaseException:
        # Withdraw only our unchanged new file; never alter concurrent edits.
        if published and regular(dest) and os.path.samestat(dest.stat(),inode) and sha(dest.read_bytes())==sha(data):
            os.rename(dest,backup/"withdrawn.html")
        if target.is_dir() and not target.is_symlink() and not any(target.iterdir()):
            target.rmdir()
        raise
    print("TRUST_PUBLIC_RELEASE=verified SHA256="+sha(data))

if __name__=="__main__":
    main()
