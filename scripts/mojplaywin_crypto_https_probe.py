#!/usr/bin/env python3
"""Single temporary, non-sensitive HTTPS metadata probe in an EXISTING payment dir."""
import hashlib
import os
from pathlib import Path
import sys

F=Path("/home/zomorod2/mojplaywin.com/checkout/crypto/__mjwp_https_probe_20261018.php")
SOURCE="""<?php header('Cache-Control: no-store');header('Content-Type: application/json');echo json_encode(['probe'=>'MJWP_ONLY_HTTPS_CHECK_20261018','https_on'=>isset($_SERVER['HTTPS'])&&!in_array(strtolower((string)$_SERVER['HTTPS']),['off','0',''],true),'port_443'=>($_SERVER['SERVER_PORT']??'')==='443','trusted_host'=>in_array(strtolower(explode(':',$_SERVER['HTTP_HOST']??'')[0]),['mojplaywin.com','www.mojplaywin.com'],true)]);"""
HASH=hashlib.sha256(SOURCE.encode()).hexdigest()

def check():
    if F.parent.is_symlink() or not F.parent.is_dir() or F.is_symlink():
        raise RuntimeError("Unexpected shared payment directory")
def stage():
    check()
    if F.exists(): raise RuntimeError("TLS probe already exists")
    fd=os.open(str(F),os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0),0o644)
    with os.fdopen(fd,"wb") as h:
        h.write(SOURCE.encode());h.flush();os.fsync(h.fileno())
    print("TLS_PROBE_STAGED=true")
def cleanup():
    check()
    if F.is_file():
        if hashlib.sha256(F.read_bytes()).hexdigest()!=HASH:
            raise RuntimeError("TLS probe modified; refuse deletion")
        F.unlink()
    print("TLS_PROBE_REMOVED=true")

if __name__=="__main__":
    if sys.argv[1:]==["stage"]:stage()
    elif sys.argv[1:]==["cleanup"]:cleanup()
    else:raise SystemExit(2)
