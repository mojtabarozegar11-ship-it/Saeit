#!/usr/bin/env python3
"""Privately verify owner activation, then release only stale keyed OpenAlex cooldown.

No credential, full provider URL, response body, or token is logged. A successful
remote GET is required before the research queue can be explicitly retried.
"""
import argparse
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import time
import urllib.error
import urllib.request

API="https://api.openalex.org/works?per_page=1"
ENDPOINT="https://api.openalex.org/works"
SCHEMA="saeit.factory.provider-cooldown.v1"

def private_key(operations):
    path=Path(operations)/".openalex-api-key"
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("OPENALEX_PRIVATE_KEY_ABSENT_OR_UNSAFE")
    info=path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode & 0o077:
        raise RuntimeError("OPENALEX_PRIVATE_KEY_PERMISSIONS")
    key=path.read_text(encoding="ascii").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,200}",key):
        raise RuntimeError("OPENALEX_PRIVATE_KEY_INVALID_FORMAT")
    return key

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        return None

def authenticated_probe(key,fetch=None):
    req=urllib.request.Request(API,headers={
        "Accept":"application/json",
        "Authorization":"Bearer "+key,
        "User-Agent":"SaeitFactoryActivationProbe/1.0"})
    if fetch is None:
        fetch=urllib.request.build_opener(NoRedirect).open
    try:
        with fetch(req,timeout=25) as response:
            if response.status!=200:
                return "UNEXPECTED_HTTP_STATUS"
            raw=response.read(65537)
    except urllib.error.HTTPError as error:
        if error.code==403:
            return "PENDING_OR_UNAUTHORIZED"
        if error.code==429:
            return "PROVIDER_RATE_LIMITED"
        return "HTTP_"+str(error.code)
    except (urllib.error.URLError,TimeoutError,OSError):
        return "NETWORK_UNAVAILABLE"
    if len(raw)>65536:
        return "INVALID_RESPONSE"
    try:
        value=json.loads(raw)
    except (ValueError,UnicodeError):
        return "INVALID_RESPONSE"
    if not isinstance(value,dict) or not isinstance(value.get("results"),list):
        return "INVALID_RESPONSE"
    return "ACTIVE"

def _atomic_json(path,data):
    handle,name=tempfile.mkstemp(prefix=".auth-cooldown-",dir=path.parent)
    try:
        os.fchmod(handle,0o600)
        with os.fdopen(handle,"w",encoding="utf8") as stream:
            json.dump(data,stream,sort_keys=True,ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def release_verified_cooldown(factory_private,wait_seconds=20):
    base=Path(factory_private)/"production-instructions/stage-02"
    lock=base/".research-scout.lock"
    state=base/"literature-provider-cooldowns.json"
    if base.is_symlink() or not base.is_dir() or lock.is_symlink() or state.is_symlink():
        raise RuntimeError("OPENALEX_UNSAFE_FACTORY_STAGE")
    handle=os.open(lock,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(handle,"a+b") as stream:
        deadline=time.monotonic()+wait_seconds
        while True:
            try:
                fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic()>=deadline:
                    return "BUSY_WORKER"
                time.sleep(.25)
        if not state.is_file():
            return "NO_PERSISTED_COOLDOWN"
        if state.stat().st_uid!=os.getuid() or state.stat().st_mode & 0o022:
            raise RuntimeError("OPENALEX_UNSAFE_COOLDOWN_OWNER")
        packet=json.loads(state.read_text(encoding="utf8"))
        if packet.get("schema")!=SCHEMA:
            raise RuntimeError("OPENALEX_INVALID_COOLDOWN_SCHEMA")
        if packet.get("openalex_credential_mode")!="keyed":
            return "AUTH_MODE_CHANGED"
        blocked=packet.get("blocked_until_utc")
        if not isinstance(blocked,dict):
            raise RuntimeError("OPENALEX_INVALID_COOLDOWN_MAP")
        if ENDPOINT not in blocked:
            return "NOT_BLOCKED"
        blocked.pop(ENDPOINT)
        packet["checked_utc"]=dt.datetime.now(dt.timezone.utc).isoformat()
        _atomic_json(state,packet)
        return "RELEASED"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--credential-dir",required=True)
    p.add_argument("--factory-private",required=True)
    args=p.parse_args()
    status=authenticated_probe(private_key(args.credential_dir))
    print("FACTORY_OPENALEX_ACTIVATION="+status)
    if status!="ACTIVE":
        print("FACTORY_OPENALEX_IMMEDIATE_RESEARCH_ALLOWED=false")
        return
    result=release_verified_cooldown(args.factory_private)
    print("FACTORY_OPENALEX_COOLDOWN="+result)
    print("FACTORY_OPENALEX_IMMEDIATE_RESEARCH_ALLOWED="+str(
        result in ("RELEASED","NO_PERSISTED_COOLDOWN","NOT_BLOCKED")).lower())

if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        print("FACTORY_OPENALEX_ACTIVATION_PROBE_FAILED="+type(exc).__name__)
        raise SystemExit(1)
