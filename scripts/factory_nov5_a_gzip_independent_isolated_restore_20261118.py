#!/usr/bin/env python3
"""Independently restore ONLY existing cPanel Nov5-A gzip into ephemeral VPS
quarantine, verify source gzip SHA + restored SQLite SHA + full integrity_check.
Two pinned owner SSH sessions, bounded relay; no raw-file deletion or service start.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import select
import shlex
import stat
import subprocess
import sys
import time

SIZE_GZ = 279659980
SHA_GZ = "591a0b10b2f782cb7cb8db3fa340f4b3827b8d1db2960ca89a507098ccc35c78"
SIZE_RAW = 1408634880
SHA_RAW = "a9fd2175f9ace1a81d67cf7145e54b8621fd44cc06b0b2739bdc9345e21750e2"

CPANEL_SEND = r'''
import hashlib,os,pathlib,pwd,stat,sys
d=pathlib.Path("/home/zomorod2/restore-staging/factory")
p=d/"master-before-20261105T154953Z.sqlite3.gz"
if pwd.getpwuid(os.geteuid()).pw_name!="zomorod2":sys.exit(20)
for a in (pathlib.Path("/home/zomorod2"),d.parent,d):
 s=a.lstat()
 if not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.geteuid() or s.st_mode&0o022:sys.exit(21)
s=p.lstat()
if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.geteuid() or s.st_nlink!=1 or s.st_mode&0o077 or s.st_size!=279659980:sys.exit(22)
fd=os.open(p,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
try:
 st=os.fstat(fd)
 a=("st_dev","st_ino","st_size","st_ctime_ns","st_mtime_ns")
 if any(getattr(s,k)!=getattr(st,k) for k in a):sys.exit(23)
 h=hashlib.sha256()
 n=0
 while True:
  b=os.read(fd,1048576)
  if not b:break
  n+=len(b)
  if n>279659980:sys.exit(24)
  h.update(b)
  v=memoryview(b)
  while v:
   written=os.write(sys.stdout.fileno(),v)
   if written<1:sys.exit(25)
   v=v[written:]
 if n!=279659980 or h.hexdigest()!="591a0b10b2f782cb7cb8db3fa340f4b3827b8d1db2960ca89a507098ccc35c78" or any(getattr(s,k)!=getattr(os.fstat(fd),k) for k in a):sys.exit(26)
finally:os.close(fd)
'''

VPS_RECEIVE = r'''
import hashlib,json,os,pathlib,pwd,sqlite3,stat,sys,tempfile,urllib.parse,zlib
home=pathlib.Path("/home/githubops")
if pwd.getpwuid(os.geteuid()).pw_name!="githubops":sys.exit(30)
s=home.lstat()
if not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.geteuid() or s.st_mode&0o022:sys.exit(31)
space=os.statvfs(home)
free=space.f_bavail*space.f_frsize
if free<1408634880+1073741824:sys.exit(32)
with tempfile.TemporaryDirectory(prefix=".factory-nov5-a-restore-",dir=str(home)) as scratch:
 p=pathlib.Path(scratch)/"restored.sqlite3"
 fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0),0o600)
 try:
  zipsha=hashlib.sha256()
  plainsha=hashlib.sha256()
  dec=zlib.decompressobj(wbits=31)
  in_bytes=out_bytes=0
  def store(b):
   global out_bytes
   out_bytes+=len(b)
   if out_bytes>1408634880:raise RuntimeError("RAW_BOUND")
   plainsha.update(b)
   v=memoryview(b)
   while v:
    n=os.write(fd,v)
    if n<1:raise RuntimeError("SHORT_WRITE")
    v=v[n:]
  while True:
   compressed=os.read(sys.stdin.fileno(),1048576)
   if not compressed:break
   in_bytes+=len(compressed)
   if in_bytes>279659980:raise RuntimeError("GZIP_BOUND")
   zipsha.update(compressed)
   remain=compressed
   while remain:
    b=dec.decompress(remain,1048576)
    store(b)
    remain=dec.unconsumed_tail
    if dec.eof and remain:raise RuntimeError("GZIP_TRAILING")
  store(dec.flush())
  os.fsync(fd)
 finally:os.close(fd)
 if (not dec.eof or dec.unused_data or in_bytes!=279659980 or out_bytes!=1408634880
     or zipsha.hexdigest()!="591a0b10b2f782cb7cb8db3fa340f4b3827b8d1db2960ca89a507098ccc35c78"
     or plainsha.hexdigest()!="a9fd2175f9ace1a81d67cf7145e54b8621fd44cc06b0b2739bdc9345e21750e2"):
  raise RuntimeError("GZIP_OR_RAW_DIGEST_FAIL")
 verify=hashlib.sha256()
 with open(p,"rb",buffering=0) as f:
  while True:
   b=f.read(1048576)
   if not b:break
   verify.update(b)
 if verify.hexdigest()!="a9fd2175f9ace1a81d67cf7145e54b8621fd44cc06b0b2739bdc9345e21750e2":raise RuntimeError("ISOLATED_READBACK_FAIL")
 uri="file:"+urllib.parse.quote(str(p),safe="/")+"?mode=ro&immutable=1"
 con=sqlite3.connect(uri,uri=True,timeout=60)
 try:
  con.execute("PRAGMA query_only=ON")
  quick=con.execute("PRAGMA quick_check").fetchone()[0]
  full=con.execute("PRAGMA integrity_check").fetchone()[0]
 finally:con.close()
 if quick!="ok" or full!="ok":raise RuntimeError("SQLITE_FUNCTIONAL_FAIL")
 print("FACTORY_OFF_INDEPENDENT_GZIP_RESTORE="+json.dumps({
  "schema":"factory.nov5-a.vps-isolated-gzip-restore.v1",
  "gzip_bytes":in_bytes,"restored_bytes":out_bytes,
  "gzip_sha_verified":True,"restored_raw_sha_verified":True,
  "isolated_restored_file_readback_verified":True,
  "quick_check":"ok","integrity_check":"ok",
  "restoration_in_temporary_private_directory":True,
  "factory_started":False,"source_deleted":False,
  "production_database_modified":False,
  "cloud_uploaded":False},sort_keys=True,separators=(",",":")),flush=True)
'''


def secure_config(path):
    p = Path(path)
    st = p.lstat()
    if not p.is_absolute() or not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or st.st_mode & 0o077:
        raise RuntimeError("UNTRUSTED_SSH_CONFIG")
    return str(p)


def cmd(config, alias, script):
    return ["ssh", "-T", "-F", config, "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=yes", "-o", "ForwardAgent=no",
            "-o", "RequestTTY=no", "-o", "ServerAliveInterval=15",
            "-o", "ServerAliveCountMax=3", alias,
            "exec python3 -B -c " + shlex.quote(script)]


def execute(config):
    if os.geteuid() == 0:
        raise RuntimeError("ROOT_RUNNER_FORBIDDEN")
    config = secure_config(config)
    src = dst = None
    try:
        src = subprocess.Popen(cmd(config, "saeit-cpanel", CPANEL_SEND),
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, bufsize=0, close_fds=True)
        dst = subprocess.Popen(cmd(config, "saeit-vps", VPS_RECEIVE),
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, bufsize=0, close_fds=True)
        count = 0
        sha = hashlib.sha256()
        while True:
            r, _, _ = select.select([src.stdout], [], [], 150)
            if not r:
                raise RuntimeError("SOURCE_IDLE_HOLD")
            block = os.read(src.stdout.fileno(), 1048576)
            if not block:
                break
            count += len(block)
            if count > SIZE_GZ:
                raise RuntimeError("GZIP_TRANSFER_OVERSIZE")
            sha.update(block)
            view = memoryview(block)
            while view:
                n = os.write(dst.stdin.fileno(), view)
                if n < 1:
                    raise RuntimeError("DESTINATION_NO_PROGRESS")
                view = view[n:]
        dst.stdin.close()
        if src.wait(timeout=45) != 0 or count != SIZE_GZ or sha.hexdigest() != SHA_GZ:
            raise RuntimeError("SOURCE_STREAM_INVALID")
        if dst.wait(timeout=720) != 0:
            raise RuntimeError("VPS_ISOLATED_RESTORE_FAILED")
        response = dst.stdout.read(4096)
        if len(response) > 4095 or not response.startswith(b"FACTORY_OFF_INDEPENDENT_GZIP_RESTORE="):
            raise RuntimeError("VPS_RESTORE_RECEIPT_MISSING")
        raw = json.loads(response.split(b"=",1)[1])
        if (raw.get("gzip_bytes") != SIZE_GZ or raw.get("restored_bytes") != SIZE_RAW
                or raw.get("quick_check") != "ok" or raw.get("integrity_check") != "ok"
                or raw.get("restored_raw_sha_verified") is not True
                or raw.get("isolated_restored_file_readback_verified") is not True):
            raise RuntimeError("VPS_RESTORE_RECEIPT_INVALID")
        print("FACTORY_GZIP_A_ISOLATED_RESTORE_PROVEN="+json.dumps(raw,sort_keys=True,separators=(',',':')),flush=True)
    finally:
        for proc in (src,dst):
            if proc is not None:
                if proc.poll() is None:
                    proc.kill()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                for stream in (proc.stdout,proc.stderr,proc.stdin):
                    if stream is not None:
                        try:stream.close()
                        except OSError:pass


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--ssh-config",required=True)
    args=parser.parse_args()
    execute(args.ssh_config)


if __name__=="__main__":
    try:main()
    except BaseException as exc:
        code=str(exc) if type(exc) is RuntimeError else type(exc).__name__
        print("FACTORY_GZIP_A_ISOLATED_RESTORE_HOLD="+code,file=sys.stderr,flush=True)
        sys.exit(2)
