"""Pinned English Moj Prop STATIC release host adapter (no automatic deployment).

Exact original/private release source and fixed allowed site path. Import has
no side effects. CLI supports read-only PRE-FLIGHT only. No code here asserts
full DB/app/media recoverability, tenant isolation, or all-writer coordination.
Write methods are only an injected adapter for an independently owner-gated
release controller; never a standalone production release.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import stat
from urllib import request, error

from scripts.mojprop_exact_static_atomic_release_c127 import atomic_replace
from scripts.mojprop_seo_current_live_v3_contract_20261120 import PINS, CHANGED, build_v3
from scripts.mojprop_seo_three_page_transaction_20261120 import PROTECTED, digest

ACCOUNT = "zomorod2"
WEB_ROOT = Path("/home/zomorod2/mojplaywin.com/moj-prop")
PRIVATE = Path("/home/zomorod2/.mojprop-seo-private-20261120-_jl1iuq4")
STAGE = PRIVATE / "current-live-v3-review-only-vkc6ghxf"
ALL_PATHS = frozenset(PINS) | frozenset(PROTECTED)
MAX_BYTES = 512_000
PUBLIC_BASE = "https://mojplaywin.com/moj-prop/"


class HostSafetyError(ValueError):
    pass


def _safe_directory(path, *, owner, private=False):
    st = path.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != owner or path.is_symlink():
        raise HostSafetyError("unsafe directory identity")
    if st.st_mode & 0o022:
        raise HostSafetyError("writable directory")
    if private and (stat.S_IMODE(st.st_mode) & 0o077):
        raise HostSafetyError("private directory permissions")
    return st


def _check_tree(path, root, *, owner, private):
    # All root-to-target parents are individually checked, not only the leaf.
    try:
        parts = path.relative_to(root).parts
    except ValueError as exc:
        raise HostSafetyError("path outside approved tenant") from exc
    if not parts or any(x in ("..", ".", "") for x in parts):
        raise HostSafetyError("invalid path")
    _safe_directory(root,owner=owner,private=private)
    parent=root
    for part in parts[:-1]:
        parent=parent/part
        _safe_directory(parent,owner=owner,private=private)


def _read_owned(path, root, *, owner, private=False):
    _check_tree(path,root,owner=owner,private=private)
    st=path.lstat()
    if not stat.S_ISREG(st.st_mode) or path.is_symlink() or st.st_uid!=owner or st.st_nlink!=1 or st.st_size>MAX_BYTES:
        raise HostSafetyError("unsafe file identity")
    if st.st_mode & 0o022 or (private and st.st_mode & 0o077):
        raise HostSafetyError("unsafe file permissions")
    flags=os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC
    fd=os.open(path,flags)
    try:
        now=os.fstat(fd)
        if (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)!=(now.st_dev,now.st_ino,now.st_size,now.st_mtime_ns):
            raise HostSafetyError("file changed during open")
        data=b""
        while len(data)<=MAX_BYTES:
            part=os.read(fd,min(65536,MAX_BYTES+1-len(data)))
            if not part:break
            data+=part
        if len(data)!=st.st_size or len(data)>MAX_BYTES:
            raise HostSafetyError("file changed during read")
        end=os.fstat(fd)
        if (end.st_ino,end.st_size,end.st_mtime_ns)!=(st.st_ino,st.st_size,st.st_mtime_ns):
            raise HostSafetyError("file changed during read")
        return data
    finally:os.close(fd)


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, hdrs, newurl):
        return None


class ExactStaticHost:
    def __init__(self, *, root=WEB_ROOT, private=PRIVATE, stage=STAGE, account=ACCOUNT):
        owner=os.geteuid()
        if owner==0 or pwd.getpwuid(owner).pw_name!=account:
            raise HostSafetyError("wrong runtime account")
        self.owner=owner
        self.root=Path(root)
        self.private=Path(private)
        self.stage=Path(stage)
        _safe_directory(self.root,owner=owner)
        _safe_directory(self.private,owner=owner,private=True)
        _safe_directory(self.stage,owner=owner,private=True)

    def read_live(self, relative):
        if relative not in ALL_PATHS:raise HostSafetyError("disallowed live page")
        return _read_owned(self.root/relative,self.root,owner=self.owner)

    def read_backup(self, relative):
        if relative not in CHANGED:raise HostSafetyError("out-of-scope backup")
        return _read_owned(self.stage/"baseline"/relative,self.private,owner=self.owner,private=True)

    def read_historical(self, relative):
        if relative not in PINS:raise HostSafetyError("out-of-scope historical page")
        return _read_owned(self.private/"original"/relative,self.private,owner=self.owner,private=True)

    def read_candidate(self, relative):
        if relative not in PINS:raise HostSafetyError("out-of-scope candidate page")
        return _read_owned(self.stage/"candidate"/relative,self.private,owner=self.owner,private=True)

    def read_public(self, relative):
        if relative not in ALL_PATHS:raise HostSafetyError("disallowed public page")
        url=PUBLIC_BASE+relative.removesuffix("index.html")
        opener=request.build_opener(_NoRedirect)
        req=request.Request(url,headers={"Accept":"text/html","Accept-Encoding":"identity","Cache-Control":"no-cache"},method="GET")
        try:
            with opener.open(req,timeout=12) as response:
                if response.status!=200 or response.geturl()!=url:
                    raise HostSafetyError("unverified public response")
                if "html" not in response.headers.get("Content-Type","").lower():
                    raise HostSafetyError("unexpected response type")
                data=response.read(MAX_BYTES+1)
        except (error.HTTPError,error.URLError,TimeoutError) as exc:
            raise HostSafetyError("public verification unavailable") from exc
        if len(data)>MAX_BYTES or not data:
            raise HostSafetyError("public HTML size out of bounds")
        return data

    @contextlib.contextmanager
    def local_lock(self):
        """Cooperative host lock only; NOT proof that all writers coordinate."""
        lock=self.private/".mojprop-three-html.lock"
        _check_tree(lock,self.private,owner=self.owner,private=True)
        fd=os.open(lock,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
        try:
            st=os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_uid!=self.owner or st.st_nlink!=1 or st.st_mode&0o077:
                raise HostSafetyError("unsafe lock")
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            yield
        finally:
            os.close(fd)

    def replace_exact(self, relative, expected_sha, payload):
        """Accessible only to trusted approved release orchestration; never CLI."""
        if relative not in CHANGED or type(payload) is not bytes:
            raise HostSafetyError("write outside exact three-page scope")
        before,after=PINS[relative]
        new=digest(payload)
        if (expected_sha,new) not in ((before,after),(after,before)):
            raise HostSafetyError("unreviewed exact transition")
        target=self.root/relative
        _check_tree(target,self.root,owner=self.owner,private=False)
        if digest(self.read_live(relative))!=expected_sha:
            raise HostSafetyError("live changed before swap")
        atomic_replace(target,payload,expected_sha,euid=self.owner)

    def preflight(self, *, public=True):
        historical={p:self.read_historical(p) for p in PINS}
        live={p:self.read_live(p) for p in PINS}
        proposed,contract=build_v3(historical,live)
        for p in PINS:
            if self.read_candidate(p)!=proposed[p]:
                raise HostSafetyError("private staged candidate differs")
        for p in CHANGED:
            if self.read_backup(p)!=live[p]:
                raise HostSafetyError("private baseline differs")
        for p,h in PROTECTED.items():
            if digest(self.read_live(p))!=h:
                raise HostSafetyError("protected live page changed")
        if public:
            for p in ALL_PATHS:
                if self.read_live(p)!=self.read_public(p):
                    raise HostSafetyError("host/public mismatch")
        return {"exact_pages":len(PINS),"write_scope":list(CHANGED),
                "protected_pages":sorted(PROTECTED),"public_checked":public,
                "private_baseline_and_candidate_verified":True,
                "independent_full_restore_verified":False,
                "tenant_isolation_verified":False,
                "all_writers_lock_verified":False,
                "production_release_authorized":False}


def main():
    parser=argparse.ArgumentParser(description="READ-ONLY exact Moj Prop static preflight")
    parser.add_argument("action",choices=("preflight",))
    args=parser.parse_args()
    if args.action=="preflight":
        report=ExactStaticHost().preflight(public=True)
        print(json.dumps(report,sort_keys=True))


if __name__=="__main__":
    main()
