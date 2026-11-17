#!/usr/bin/env python3
"""C151 determine legacy owner rollback manifest format without disclosing data.

Read at most 64KiB of each *fixed-name* manifest.json in up to 64 private
case directories. Never open saved app/DB/media backup files, customer data
or restore receipts. Emit only aggregate structural counts (no names,
SHA strings, dates, run IDs, filenames, field values or exceptions).
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import pwd
import re
import stat

OWNER="zomorod2"
ROOT=Path("/home/zomorod2/.mojplaywin-moj-prop-backups")
CASE=re.compile(r"(?:[0-9]{8,20}|mojprop[-_][a-z0-9_-]{4,45})\Z")
SHA40=re.compile(r"[a-f0-9]{40}\Z")
MAX_ENTRIES=128
MAX_CASES=64
MAX_BYTES=65536
SIG_KEYS=(
    "parsed_json_map", "schema_string", "matching_run_id",
    "run_id_string_mismatch", "commit_40hex", "commit_sha_40hex",
    "files_list_string", "files_list_map", "files_mapping",
    "file_entries_absent_or_other", "migration_flag_boolean",
    "rolled_back_boolean", "declared_first_party_source_list",
    "original_file_metadata_dict_present", "schema_contains_static_marker",
)

def _safe_dir(path, uid):
    try:
        st=path.lstat()
    except OSError:
        return False
    return (stat.S_ISDIR(st.st_mode) and st.st_uid==uid
            and not st.st_mode & 0o022)

def _unique_pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError("duplicate metadata key")
        result[key]=value
    return result

def _read_manifest(case_dir, uid):
    if not _safe_dir(case_dir,uid) or not CASE.fullmatch(case_dir.name):
        return None
    path=case_dir/"manifest.json"
    fd=None
    try:
        fd=os.open(str(path),os.O_RDONLY | getattr(os,"O_NOFOLLOW",0))
        stat_result=os.fstat(fd)
        if (not stat.S_ISREG(stat_result.st_mode) or
                stat_result.st_uid!=uid or stat_result.st_mode & 0o022 or
                stat_result.st_nlink!=1 or
                not 1<=stat_result.st_size<=MAX_BYTES):
            return None
        data=os.read(fd,MAX_BYTES+1)
        if len(data)!=stat_result.st_size:
            return None
        return json.loads(data.decode("utf-8"),object_pairs_hook=_unique_pairs)
    except (OSError,ValueError,UnicodeError,TypeError):
        return None
    finally:
        if fd is not None:
            os.close(fd)

def fingerprint(doc, dirname):
    """Only fixed booleans: never output any field values or source filenames."""
    features={name:False for name in SIG_KEYS}
    if type(doc) is not dict:
        return features
    features["parsed_json_map"]=True
    features["schema_string"]=type(doc.get("schema")) is str
    if features["schema_string"]:
        features["schema_contains_static_marker"]="static" in doc["schema"].lower()
    features["matching_run_id"]=(type(doc.get("run_id")) is str
                                  and doc["run_id"]==dirname)
    features["run_id_string_mismatch"]=(type(doc.get("run_id")) is str
                                        and doc["run_id"]!=dirname)
    features["commit_40hex"]=(type(doc.get("commit")) is str
                               and SHA40.fullmatch(doc["commit"]) is not None)
    features["commit_sha_40hex"]=(type(doc.get("commit_sha")) is str
                                   and SHA40.fullmatch(doc["commit_sha"]) is not None)
    files=doc.get("files")
    features["files_list_string"]=(type(files) is list and bool(files)
                                    and all(type(x) is str for x in files))
    features["files_list_map"]=(type(files) is list and bool(files)
                                 and all(type(x) is dict for x in files))
    features["files_mapping"]=type(files) is dict
    features["file_entries_absent_or_other"]=not any(features[k] for k in (
        "files_list_string","files_list_map","files_mapping"))
    features["migration_flag_boolean"]=type(doc.get("schema_migration_attempted")) is bool
    features["rolled_back_boolean"]=type(doc.get("rolled_back")) is bool
    if features["files_list_string"]:
        entries=files
        features["declared_first_party_source_list"]=all(
            value.startswith(("config/","core/","scripts/")) and
            ".." not in value.split("/") for value in entries)
        features["original_file_metadata_dict_present"]=any(
            type(doc.get(name)) is dict for name in entries)
    return features

def inventory(root, uid):
    counts={k:0 for k in SIG_KEYS}
    out={"completed":False,"owner_root_verified":False,
         "cases_checked":0,"manifest_attempts":0,
         "features":counts,
         "read_source_backup_contents":False,
         "read_database_or_media":False,
         "independent_restore_proven":False}
    if not _safe_dir(root,uid):
        return out
    out["owner_root_verified"]=True
    count=0
    cases=0
    try:
        with os.scandir(root) as entries:
            for entry in entries:
                count+=1
                if count>MAX_ENTRIES:
                    return out
                if not CASE.fullmatch(entry.name):
                    continue
                try:
                    st=entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                if (not stat.S_ISDIR(st.st_mode) or
                        st.st_uid!=uid or st.st_mode & 0o022):
                    continue
                cases+=1
                if cases>MAX_CASES:
                    return out
                features=fingerprint(_read_manifest(root/entry.name,uid),entry.name)
                for name, value in features.items():
                    counts[name]+=int(value)
    except OSError:
        return out
    out.update(completed=True,cases_checked=cases,manifest_attempts=cases)
    return out

def report():
    out={"schema":"mojprop.cpanel.local_manifest_shape_features.c151.v1",
         "read_only":True,"owner_identity_verified":False,
         "inventory":inventory(Path("/nonexistent-safe-default"),-1),
         "backup_file_content_read":False,"customer_data_accessed":False,
         "database_accessed":False,"external_network_called":False,
         "provider_offhost_backup_verified":False,
         "app_db_media_restore_verified":False,
         "production_release_authorized":False,"cost_incurred":False}
    try:
        if pwd.getpwuid(os.geteuid()).pw_name!=OWNER:
            return out
        out["owner_identity_verified"]=True
        out["inventory"]=inventory(ROOT,os.geteuid())
    except (OSError,KeyError,ValueError):
        pass
    return out

if __name__=="__main__":
    print("MOJPROP_C151_OWNER_MANIFEST_FORMAT_READONLY="+
          json.dumps(report(),sort_keys=True,separators=(",",":")))
