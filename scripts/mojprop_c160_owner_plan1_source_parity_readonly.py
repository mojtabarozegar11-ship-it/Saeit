#!/usr/bin/env python3
"""C160: owner-only full review-bundle SHA-256 comparison on real cPanel staging.

Designed for source-only GitHub Actions ephemeral preflight. The CI runner
injects a strict manifest built from the exact PR checkout into a throwaway
copy of THIS script, which then travels via the existing pinned SSH/STDIN
factory->cPanel relay. Never write to cPanel, import Django, query SQL,
read secrets, inspect media/customer records or change Passenger.
Only aggregate grouped counts are emitted; no filenames/hashes/content from
the server are printed. This is NOT a full system backup/restore proof.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import re
import stat

OWNER = "zomorod2"
ROOT = Path("/home/zomorod2/Saeit-staging")
MAX_FILES = 128
MAX_FILE_BYTES = 384*1024
SHA64 = re.compile(r"[a-f0-9]{64}\Z")
# The exact string below MUST occur once; CI injects only a locally
# validated source manifest. Without injection, all results fail closed.
EMBEDDED_MANIFEST = None
GROUPS = ("config_reference", "core_views", "core_templates",
          "prop_app", "prop_migrations", "excluded_secrets")


def _group(name):
    if name == "config/settings.py":
        return "excluded_secrets"
    if name.startswith("config/"):
        return "config_reference"
    if name.startswith("core/templates/"):
        return "core_templates"
    if name.startswith("core/"):
        return "core_views"
    if name.startswith("prop_firm/migrations/"):
        return "prop_migrations"
    return "prop_app"


def _safe_name(name):
    if type(name) is not str or not 1 <= len(name) <= 210:
        return False
    parts = name.split("/")
    if any(p in ("",".","..") for p in parts):
        return False
    if not name.startswith(("config/","core/","prop_firm/")):
        return False
    if not name.endswith((".py",".html",".json")):
        return False
    return str(PurePosixPath(*parts)) == name


def validate_expected(items):
    """Only hash approved first-party source filenames; no arbitrary paths."""
    if type(items) is not dict or not 1 <= len(items) <= MAX_FILES:
        raise ValueError("invalid bounded source map")
    if "core/moj_prop_views.py" not in items or \
       "core/templates/mojplaywin/moj_prop_interest_form_d.html" not in items or \
       "config/urls.py" not in items or \
       "prop_firm/migrations/0008_prospect_contact_intake.py" not in items:
        raise ValueError("required funded Plan1 source missing")
    for path,value in items.items():
        if (not _safe_name(path) or type(value) is not str
                or SHA64.fullmatch(value) is None):
            raise ValueError("unsafe source manifest")
    return items


def safe_owner_dir(path, uid):
    try:
        st = path.lstat()
    except OSError:
        return False
    return (stat.S_ISDIR(st.st_mode) and st.st_uid == uid and
            not st.st_mode & 0o022)


def file_parity(root, relative, expected_sha, uid):
    if not _safe_name(relative) or type(expected_sha) is not str or \
       SHA64.fullmatch(expected_sha) is None:
        return "unsafe"
    if relative == "config/settings.py":
        return "withheld"
    if not safe_owner_dir(root,uid):
        return "unsafe"
    target = root / relative
    parent = target.parent
    while parent != root:
        if root not in parent.parents:
            return "unsafe"
        try:
            parent_st = parent.lstat()
        except FileNotFoundError:
            return "missing"
        except OSError:
            return "unavailable"
        if (not stat.S_ISDIR(parent_st.st_mode)
                or parent_st.st_uid != uid or parent_st.st_mode & 0o022):
            return "unsafe"
        parent = parent.parent
    try:
        st = target.lstat()
    except FileNotFoundError:
        return "missing"
    except OSError:
        return "unavailable"
    if (not stat.S_ISREG(st.st_mode) or st.st_uid != uid
            or st.st_mode & 0o022 or st.st_nlink != 1
            or not 0 < st.st_size <= MAX_FILE_BYTES):
        return "unsafe"
    fd = None
    try:
        fd = os.open(str(target),os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
        opened = os.fstat(fd)
        if (not stat.S_ISREG(opened.st_mode) or opened.st_uid != uid
                or opened.st_nlink != 1 or opened.st_mode & 0o022
                or opened.st_ino != st.st_ino or opened.st_dev != st.st_dev
                or opened.st_size != st.st_size):
            return "unsafe"
        size = 0
        digest = hashlib.sha256()
        while True:
            chunk = os.read(fd,65536)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_FILE_BYTES:
                return "unsafe"
            digest.update(chunk)
        if size != opened.st_size:
            return "unavailable"
        return "matches" if digest.hexdigest() == expected_sha else "drifted"
    except OSError:
        return "unavailable"
    finally:
        if fd is not None:
            os.close(fd)


def compare(root, manifest, uid):
    expected = validate_expected(manifest)
    groups = {g:{status:0 for status in
                 ("matches","missing","drifted","unsafe","unavailable","withheld")}
              for g in GROUPS}
    for rel, sha in sorted(expected.items()):
        group = _group(rel)
        groups[group][file_parity(root,rel,sha,uid)] += 1
    totals = {status:sum(g[status] for g in groups.values())
              for status in ("matches","missing","drifted",
                             "unsafe","unavailable","withheld")}
    return {"file_count":len(expected),"group_counts":groups,
            "total_counts":totals,"read_customer_or_database":False,
            "server_source_contents_exposed":False,
            "backup_or_restore_proven":False,
            "production_deploy_authorized":False}


def report(manifest=EMBEDDED_MANIFEST):
    out = {"schema":"mojprop.owner.cpanel.source_bundle_parity.c160.v1",
           "owner_identity_verified":False,"read_only":True,
           "comparison_completed":False,
           "source_bundle_sha256_manifest_verified_in_ci":False,
           "scope_legacy_reference_not_live_worker":True,
           "result":None,
           "account_quota_proven":False,
           "independent_full_app_db_media_restore_proven":False,
           "public_form_get_verified":False,
           "customer_data_accessed":False,
           "backup_contents_read":False,
           "database_accessed":False,
           "external_network_called":False,
           "production_deployment_authorized":False,
           "payment_created":False,"cost_incurred":False}
    try:
        if pwd.getpwuid(os.geteuid()).pw_name != OWNER:
            return out
        out["owner_identity_verified"] = True
        validate_expected(manifest)
        if not safe_owner_dir(ROOT,os.geteuid()):
            return out
        out["result"] = compare(ROOT,manifest,os.geteuid())
        out["comparison_completed"] = True
        # The runner validated manifest against its own checkout; remote
        # cannot prove that independently, so leave proof flag false.
    except (OSError,ValueError,TypeError,KeyError):
        pass
    return out


if __name__ == "__main__":
    print("MOJPROP_C160_FULL_SOURCE_PARITY_READONLY=" +
          json.dumps(report(),sort_keys=True,separators=(",",":")))
