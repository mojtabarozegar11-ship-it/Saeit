#!/usr/bin/env python3
"""C152 verify existing owner-local *SOURCE* rollback file hashes, read-only.

Scan ONLY an immutable list of first-party Python source relative paths, and
only if an owner-private legacy source manifest independently asserts original
SHA256. Never open an unknown manifest-provided path, DB/media snapshot,
backup archive, customer record or restore receipt. No bytes or filenames
from any saved file are emitted. Local source hash verification is NOT full
DB/app/media restore or authorization to run old rollback or migrate schema.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat

OWNER="zomorod2"
ROOT=Path("/home/zomorod2/.mojplaywin-moj-prop-backups")
CASE=re.compile(r"[0-9]{8,20}\Z")
SHA40=re.compile(r"[a-f0-9]{40}\Z")
SHA64=re.compile(r"[a-f0-9]{64}\Z")
MAX_ENTRIES=128
MAX_CASES=64
MAX_MANIFEST=65536
MAX_SOURCE_BYTES=512*1024
MAX_ALL_READ_BYTES=64*1024*1024
ALLOWED_SOURCE=frozenset((
    "config/urls.py",
    # Never open owner-configured settings in a general source hash probe.
    # That file might contain private credentials; do not infer full backup.
    "core/models.py","core/admin.py",
    "core/mojprop_accessible_intake.py","core/mojprop_views.py",
    "core/mojprop_receipts.py","core/mojprop_catalog_contract.py",
    "core/mojprop_workflow.py","core/mojprop_offer_draft.py",
    "core/mojprop_quote_contract.py","core/mojprop_quote_views.py",
    "core/management/commands/mojprop_sales_action_queue.py",
    "core/signal_free_models.py","core/guest_recovery_models.py",
    "core/signal_free_views.py",
    "core/migrations/0041_mojprop_request.py",
    "core/migrations/0042_mojprop_offer.py",
    "core/migrations/0043_mojprop_digital_inquiry.py",
    "core/migrations/0044_mojprop_acceptance_evidence.py",
    "core/migrations/0045_mojprop_delivery_evidence.py",
    "core/migrations/0046_signal_free_subscription.py",
    "core/migrations/0047_mpw_guest_email_recovery.py",
    "scripts/fixtures/mojprop_legacy_request_source_c84.py",
    "scripts/fixtures/mojprop_legacy_admin_source_c84.py",
    "scripts/mojprop_schema_preflight_c83.py",
    "scripts/mojprop_db_release_evidence.py",
    "scripts/mojprop_restore_capacity_admission.py",
    "scripts/mojprop_live_database_identity_c85.py",
))
SENSITIVE_EXCLUDE=frozenset(("config/settings.py",))


def _safe_dir(path,uid):
    try:
        st=path.lstat()
    except OSError:
        return False
    return (stat.S_ISDIR(st.st_mode) and st.st_uid==uid and
            not st.st_mode & 0o022)


def _unique_pairs(pairs):
    result={}
    for key,item in pairs:
        if key in result:
            raise ValueError("duplicate metadata field")
        result[key]=item
    return result


def _read_small_fixed_json(path,uid):
    fd=None
    try:
        fd=os.open(str(path),os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
        st=os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid!=uid
                or st.st_mode & 0o022 or st.st_nlink!=1
                or not 1<=st.st_size<=MAX_MANIFEST):
            return None
        blob=os.read(fd,MAX_MANIFEST+1)
        if len(blob)!=st.st_size:
            return None
        return json.loads(blob.decode("utf-8"),object_pairs_hook=_unique_pairs)
    except (OSError,UnicodeError,ValueError,TypeError):
        return None
    finally:
        if fd is not None:
            os.close(fd)


def validate_legacy_manifest(doc,case_name):
    """Return only fixed allowlisted (path, hash) tuples and withheld count."""
    if (type(doc) is not dict or doc.get("run_id")!=case_name or
            type(doc.get("commit")) is not str or
            SHA40.fullmatch(doc["commit"]) is None or
            "schema_migration_attempted" in doc):
        return None
    files=doc.get("files")
    if (type(files) is not list or not 1<=len(files)<=80
            or len(set(x for x in files if type(x) is str))!=len(files)
            or any(type(x) is not str or
                   not x.startswith(("core/","config/","scripts/")) or
                   ".." in x.split("/") for x in files)):
        return None
    allowed=[]
    withheld=0
    for name in files:
        entry=doc.get(name)
        if type(entry) is not dict or type(entry.get("existed")) is not bool:
            return None
        if entry["existed"]:
            if (type(entry.get("sha256")) is not str or
                    SHA64.fullmatch(entry["sha256"]) is None or
                    type(entry.get("mode")) is not int or
                    not 0<=entry["mode"]<=0o777):
                return None
            if name in ALLOWED_SOURCE:
                allowed.append((name,entry["sha256"]))
            else:
                withheld+=1
    return allowed,withheld


def _safe_source_file_sha(case_dir,relative,uid):
    """SHA256 of owner-safe, regular, bounded FIRST-PARTY source only."""
    if relative not in ALLOWED_SOURCE or not _safe_dir(case_dir,uid):
        return None
    target=case_dir/relative
    current=target.parent
    while current!=case_dir:
        if case_dir not in current.parents or not _safe_dir(current,uid):
            return None
        current=current.parent
    fd=None
    try:
        fd=os.open(str(target),os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
        st=os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid!=uid or
                st.st_mode & 0o022 or st.st_nlink!=1 or
                not 1<=st.st_size<=MAX_SOURCE_BYTES):
            return None
        digest=hashlib.sha256()
        read_total=0
        while True:
            data=os.read(fd,65536)
            if not data:
                break
            read_total+=len(data)
            if read_total>MAX_SOURCE_BYTES:
                return None
            digest.update(data)
        if read_total!=st.st_size:
            return None
        return (digest.hexdigest(),read_total)
    except OSError:
        return None
    finally:
        if fd is not None:
            os.close(fd)


def inventory(root,uid):
    out={"completed":False,"owner_root_verified":False,
         "legacy_manifest_cases_checked":0,
         "legacy_manifest_cases_recognized":0,
         "legacy_cases_with_all_allowed_source_hashes_matching":0,
         "allowed_source_copies_with_matching_sha256":0,
         "allowed_source_copies_missing_or_mismatched":0,
         "sensitive_or_unreviewed_source_entries_not_opened":0,
         "verified_read_bytes_bounded":0,
         "saved_source_contents_disclosed":False,
         "customer_data_accessed":False,
         "database_or_media_backup_read":False,
         "source_only_is_full_restore":False,
         "independent_db_app_media_restore_proven":False}
    if not _safe_dir(root,uid):
        return out
    out["owner_root_verified"]=True
    checked=recognized=full=ok=bad=withheld=read=0
    entries=0
    try:
        with os.scandir(root) as scan:
            for entry in scan:
                entries+=1
                if entries>MAX_ENTRIES:
                    return out
                if not CASE.fullmatch(entry.name):
                    continue
                try:
                    st=entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                if not stat.S_ISDIR(st.st_mode) or st.st_uid!=uid or st.st_mode&0o022:
                    continue
                checked+=1
                if checked>MAX_CASES:
                    return out
                folder=root/entry.name
                doc=_read_small_fixed_json(folder/"manifest.json",uid)
                parsed=validate_legacy_manifest(doc,entry.name)
                if parsed is None:
                    continue
                recognized+=1
                sources,held=parsed
                withheld+=held
                all_good=bool(sources)
                for name,expected in sources:
                    proof=_safe_source_file_sha(folder,name,uid)
                    if proof is None:
                        bad+=1
                        all_good=False
                    else:
                        sha,size=proof
                        read+=size
                        if read>MAX_ALL_READ_BYTES:
                            return out
                        if sha==expected:
                            ok+=1
                        else:
                            bad+=1
                            all_good=False
                if all_good:
                    full+=1
    except OSError:
        return out
    out.update(completed=True,legacy_manifest_cases_checked=checked,
               legacy_manifest_cases_recognized=recognized,
               legacy_cases_with_all_allowed_source_hashes_matching=full,
               allowed_source_copies_with_matching_sha256=ok,
               allowed_source_copies_missing_or_mismatched=bad,
               sensitive_or_unreviewed_source_entries_not_opened=withheld,
               verified_read_bytes_bounded=read)
    return out


def report():
    out={"schema":"mojprop.cpanel.legacy_source_backup_sha256.c152.v1",
         "read_only":True,"owner_identity_verified":False,
         "inventory":inventory(Path("/no-source-backups-here"),-1),
         "customer_data_accessed":False,"db_media_backup_content_read":False,
         "offhost_independent_backup_proven":False,
         "full_app_db_media_restore_proven":False,
         "production_deployment_authorized":False,
         "payment_created":False,"cost_incurred":False}
    try:
        if pwd.getpwuid(os.geteuid()).pw_name!=OWNER:
            return out
        out["owner_identity_verified"]=True
        out["inventory"]=inventory(ROOT,os.geteuid())
    except (OSError,ValueError,KeyError):
        pass
    return out

if __name__=="__main__":
    print("MOJPROP_C152_LEGACY_SOURCE_SHA256_READONLY="+
          json.dumps(report(),sort_keys=True,separators=(",",":")))
