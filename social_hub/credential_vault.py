"""Private, atomic multi-account API credential provisioning.

Intended for a trusted SSH terminal on the isolated owner host, not a web
request, GitHub, HTTP endpoint, chat, or a remote provider callback.

A JSON vault is unencrypted at rest but owner-only (0700 directory, 0600 file),
kept outside the webroot. One OS-atomic replace provisions the full batch.
Never print, return, log or store credential values in the public or social DB.
"""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import re
import stat
import tempfile

from .adapters import Blocked
from .catalog import RESTRICTED_HANDLES, platform

MAX_VAULT_BYTES = 1_000_000
MAX_IMPORT_BYTES = 1_000_000
MAX_ACCOUNTS = 120
ALIAS = re.compile(r"MPW_SOCIAL_(PERSONAL|ZOMOROD|MOJPLAYWIN)_[A-Z0-9_]{1,70}_[0-9A-F]{32}_TOKEN\Z")
DANGEROUS_PATH_PARTS = {"public_html", "htdocs", "www", "static", ".git", "media"}

def _path(value, *, existing=False):
    if not isinstance(value,(str,os.PathLike)) or not str(value):
        raise Blocked("Private vault absolute path is not configured")
    path = Path(value)
    if (not path.is_absolute() or path.name in ("", ".", "..") or
        any(x.lower() in DANGEROUS_PATH_PARTS for x in path.parts)):
        raise Blocked("Vault must be an absolute path outside all webroots")
    parent=path.parent
    if (not parent.is_dir() or parent.is_symlink() or
        parent.stat().st_mode & 0o077 or parent.stat().st_uid!=os.geteuid()):
        raise Blocked("Vault parent directory must belong to current user and be mode 0700")
    if path.is_symlink():
        raise Blocked("Symlinked private credentials refused")
    if existing and not path.is_file():
        raise Blocked("Vault/manifest file does not exist")
    if path.exists():
        info=path.stat()
        if (not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or
            info.st_uid!=os.geteuid() or info.st_nlink!=1):
            raise Blocked("Private credential file must be owner-only regular file mode 0600")
    return path

def _private_json(path, *, limit=MAX_VAULT_BYTES, missing=None):
    target=_path(path)
    if not target.exists():
        if missing is not None:
            return missing
        raise Blocked("Private credentials file not yet provisioned")
    if target.stat().st_size>limit:
        raise Blocked("Private credentials file exceeds allowed limit")
    flags=os.O_RDONLY | getattr(os,"O_NOFOLLOW",0)
    fd=os.open(target,flags)
    try:
        info=os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or
            info.st_uid!=os.geteuid() or info.st_nlink!=1 or info.st_size>limit):
            raise Blocked("Unsafe private credentials handle")
        with os.fdopen(fd,"rb",closefd=False) as source:
            data=source.read(limit+1)
        if len(data)>limit:
            raise Blocked("Private credentials too large")
    finally:
        os.close(fd)
    try:
        return json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeError):
        raise Blocked("Private credential JSON is malformed") from None

def _token(value):
    if (not isinstance(value,str) or not 6<=len(value)<=6000 or
        any(x.isspace() or ord(x)<33 or ord(x)==127 for x in value)):
        raise Blocked("API credential must be a nonempty, single-line opaque string")
    return value

def _vault(path):
    data=_private_json(path,missing={"schema_version":1,"secrets":{}})
    if (not isinstance(data,dict) or set(data)!={"schema_version","secrets"}
        or type(data["schema_version"]) is not int or data["schema_version"]!=1
        or not isinstance(data["secrets"],dict) or len(data["secrets"])>MAX_ACCOUNTS):
        raise Blocked("Private credential vault schema invalid")
    for alias,secret in data["secrets"].items():
        if not isinstance(alias,str) or not ALIAS.fullmatch(alias):
            raise Blocked("Invalid stored credential identifier")
        _token(secret)
    return data["secrets"]

def credential_for(account, *, env=None, vault_file=None):
    """Resolve one account's privately scoped token, fail closed on ambiguity."""
    env=os.environ if env is None else env
    alias=account.get("token_env") if isinstance(account,dict) else None
    if not isinstance(alias,str) or not ALIAS.fullmatch(alias):
        raise Blocked("Unrecognized private API credential identity")
    environment=env.get(alias,"")
    if environment:
        _token(environment)
    path=vault_file if vault_file is not None else env.get("MPW_SOCIAL_CREDENTIAL_VAULT","")
    local=_vault(path).get(alias,"") if path else ""
    if environment and local:
        raise Blocked("Same account configured in multiple secret stores")
    return environment or local

def has_credential(account, *, env=None, vault_file=None):
    return bool(credential_for(account,env=env,vault_file=vault_file))

def load_private_import(path):
    """Read owner-created one-time input file, refusing world-readable secrets."""
    return _private_json(path,limit=MAX_IMPORT_BYTES)

def _validate_import(store,manifest,*,env=None):
    env=os.environ if env is None else env
    if (not isinstance(manifest,dict) or
        set(manifest)!={"schema_version","owner_confirmed","credentials"} or
        type(manifest["schema_version"]) is not int or manifest["schema_version"]!=1 or
        manifest["owner_confirmed"] is not True):
        raise Blocked("Credential batch must be owner-confirmed schema version 1")
    rows=manifest["credentials"]
    if not isinstance(rows,list) or not 1<=len(rows)<=MAX_ACCOUNTS:
        raise Blocked("Credential batch must have between 1 and 120 accounts")
    mapped={}
    for row in rows:
        if not isinstance(row,dict) or set(row)!={"account_id","token"}:
            raise Blocked("Unknown credential input fields; no extra private keys supported")
        aid=row["account_id"]
        if not isinstance(aid,str) or not re.fullmatch(r"[a-f0-9]{32}",aid):
            raise Blocked("Invalid private account ID")
        if aid in mapped:
            raise Blocked("Duplicate account ID in credential batch")
        account=store.account(aid)
        if not account or not account["verified"]:
            raise Blocked("Owner-attested account record required before provisioning")
        if not platform(account["platform"]).sendable:
            raise Blocked("Manual/read-only profile may not receive write API credentials")
        if any(k in (account["destination"]+" "+account["public_url"]).casefold()
               for k in RESTRICTED_HANDLES):
            raise Blocked("Restricted promotional account excluded")
        alias=account["token_env"]
        if not ALIAS.fullmatch(alias):
            raise Blocked("Private account credential name not recognized")
        if env.get(alias):
            raise Blocked("Account already has credential in process environment; remove ambiguity first")
        mapped[aid]=(account,alias,_token(row["token"]))
    return mapped

def plan_import(store,manifest,*,vault_file,env=None,replace=False):
    """No external activity, no writes and zero credential output."""
    mapped=_validate_import(store,manifest,env=env)
    prior=_vault(vault_file)
    collisions=[aid for aid,(_,alias,_) in mapped.items() if alias in prior]
    if collisions and not replace:
        raise Blocked("Existing credentials need explicit rotation flag")
    if len(prior)+sum(1 for _,alias,_ in mapped.values() if alias not in prior)>MAX_ACCOUNTS:
        raise Blocked("Credential vault account capacity exceeded")
    return {"accounts":len(mapped),
            "new_credentials":len(mapped)-len(collisions),
            "rotations":len(collisions),
            "provider_authorizations_completed":False,
            "outbound_enabled":False,
            "tokens_returned":False}

def _atomic_write(path,content):
    path=_path(path)
    encoded=json.dumps(content,ensure_ascii=True,separators=(",",":"),sort_keys=True).encode("utf-8")
    if len(encoded)>MAX_VAULT_BYTES:
        raise Blocked("Private vault exceeds maximum size")
    tmp=None
    try:
        with tempfile.NamedTemporaryFile(mode="wb",prefix=".social-vault-",suffix=".tmp",
                                         dir=path.parent,delete=False) as stream:
            tmp=Path(stream.name)
            os.fchmod(stream.fileno(),0o600)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        _path(tmp,existing=True)
        os.replace(tmp,path)
        tmp=None
        # After atomic replace, sync directory for durable private installation.
        dirfd=os.open(path.parent,os.O_RDONLY|getattr(os,"O_DIRECTORY",0))
        try: os.fsync(dirfd)
        finally: os.close(dirfd)
    finally:
        if tmp is not None:
            try: tmp.unlink()
            except FileNotFoundError: pass

def _lock(vault_file):
    """Private lock file is stable across os.replace; fcntl protects full read-modify-write."""
    target=_path(vault_file)
    lock=target.with_name(target.name+".lock")
    _path(lock)
    flags=os.O_RDWR|os.O_CREAT|getattr(os,"O_NOFOLLOW",0)
    fd=os.open(lock,flags,0o600)
    info=os.fstat(fd)
    if (not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077
        or info.st_uid!=os.geteuid() or info.st_nlink!=1):
        os.close(fd)
        raise Blocked("Unsafe credential provisioning lock")
    fcntl.flock(fd,fcntl.LOCK_EX)
    return fd

def import_batch(store,manifest,*,vault_file,actor,replace=False,env=None):
    """Single atomic file replacement; no provider authorization or publication.

    Existing read-only API checks are invalidated before replacing tokens,
    making credential rotations fail-closed even if file writes are interrupted.
    """
    if not isinstance(actor,str) or not (actor.startswith("owner-cli:") and len(actor)<=100):
        raise Blocked("Provisioning requires an explicitly approved owner SSH CLI")
    env=os.environ if env is None else env
    lock=_lock(vault_file)
    try:
        planned=plan_import(store,manifest,vault_file=vault_file,env=env,replace=replace)
        mapping=_validate_import(store,manifest,env=env)
        prior=_vault(vault_file)
        for account,alias,secret in mapping.values():
            prior[alias]=secret
        # Invalidate old verification attestations before any new credential is available.
        with store.transaction():
            for account,alias,secret in mapping.values():
                store.db.execute("DELETE FROM api_checks WHERE account_id=?",(account["id"],))
        _atomic_write(vault_file,{"schema_version":1,"secrets":prior})
        with store.transaction():
            for account,alias,secret in mapping.values():
                store.event(account["id"],account["brand"],actor,"credential_privately_staged",
                            "provider_read_only_recheck_required")
        return {**planned,"status":"private_credentials_staged","identity_recheck_required":True}
    finally:
        fcntl.flock(lock,fcntl.LOCK_UN)
        os.close(lock)

def disconnect_batch(store,account_ids,*,vault_file,actor):
    """Locally remove credentials for named accounts and invalidate checks.

    A provider-side OAuth grant/token must still be revoked at provider portal.
    """
    if not isinstance(actor,str) or not actor.startswith("owner-cli:"):
        raise Blocked("Only trusted owner CLI may disconnect credentials")
    if not isinstance(account_ids,list) or not 1<=len(account_ids)<=MAX_ACCOUNTS:
        raise Blocked("Specify between 1 and 120 account IDs")
    if len(account_ids)!=len(set(account_ids)):
        raise Blocked("Duplicate disconnect account")
    accounts=[]
    for aid in account_ids:
        a=store.account(aid)
        if not a: raise Blocked("Unknown account in disconnect list")
        accounts.append(a)
    lock=_lock(vault_file)
    try:
        prior=_vault(vault_file)
        removed=0
        for account in accounts:
            removed+=int(prior.pop(account["token_env"],None) is not None)
        with store.transaction():
            for account in accounts:
                store.db.execute("DELETE FROM api_checks WHERE account_id=?",(account["id"],))
        _atomic_write(vault_file,{"schema_version":1,"secrets":prior})
        with store.transaction():
            for account in accounts:
                store.event(account["id"],account["brand"],actor,
                            "local_credential_revoked","provider_side_revocation_required")
        return {"accounts":len(accounts),"local_credentials_removed":removed,
                "provider_side_revocation_required":True,"outbound_enabled":False}
    finally:
        fcntl.flock(lock,fcntl.LOCK_UN)
        os.close(lock)
