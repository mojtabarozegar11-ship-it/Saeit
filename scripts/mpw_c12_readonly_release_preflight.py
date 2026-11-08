#!/usr/bin/env python3
"""Read-only, bounded C12 release gate. No secrets, user files, DB or network."""
import json
import os
import pwd
import stat
from pathlib import Path

HOME = Path("/home/zomorod2")
DOC = HOME / "mojplaywin.com"
APP = HOME / "Saeit-staging"
TARGET = DOC / "mpw-editorial" / "research-library" / "20261108-c12"
ZIP = HOME / "MojPlayWin_Research_Library_20261108_C12.zip"
EXPECTED = "f567f40353fb3290a55fdf8caab595887422e65d8bf6d6cb40ce1f48a1fb0aaf"

def meta(p):
    try:
        s = p.lstat()
        return {"exists": True, "directory": stat.S_ISDIR(s.st_mode),
                "regular": stat.S_ISREG(s.st_mode), "symlink": stat.S_ISLNK(s.st_mode),
                "owned_by_effective_user": s.st_uid == os.geteuid(),
                "mode_owner_writable": bool(s.st_mode & stat.S_IWUSR)}
    except FileNotFoundError:
        return {"exists": False}
    except OSError:
        return {"exists": None}

def main():
    names = {"home": HOME, "document_root": DOC, "application_root": APP,
             "passenger_wsgi": DOC / "passenger_wsgi.py",
             "htaccess": DOC / ".htaccess",
             "versioned_target": TARGET, "release_zip": ZIP,
             "versioned_parent": TARGET.parent,
             "staging_python": HOME / "virtualenv" / "Saeit-staging" / "3.11" / "bin" / "python"}
    evidence = {k: meta(v) for k, v in names.items()}
    zip_meta = evidence["release_zip"]
    # Hash only the explicitly named release archive, never customer or private files.
    if zip_meta.get("regular") and zip_meta.get("owned_by_effective_user") and not zip_meta.get("symlink"):
        import hashlib
        h = hashlib.sha256()
        try:
            with ZIP.open("rb") as f:
                while chunk := f.read(1024 * 1024):
                    h.update(chunk)
            zip_meta["expected_sha256_matches"] = h.hexdigest() == EXPECTED
        except OSError:
            zip_meta["expected_sha256_matches"] = None
    else:
        zip_meta["expected_sha256_matches"] = False
    # Inspect the entire versioned publication ancestry without following symlinks.
    ancestry = [DOC / "mpw-editorial", DOC / "mpw-editorial" / "research-library", TARGET.parent]
    ancestry_meta = [meta(p) for p in ancestry]
    evidence["publication_ancestry"] = ancestry_meta
    conditions = {
        "effective_user_is_zomorod2": pwd.getpwuid(os.geteuid()).pw_name == "zomorod2",
        "docroot_owned_directory": evidence["document_root"].get("directory") is True and evidence["document_root"].get("owned_by_effective_user") is True,
        "application_root_present": evidence["application_root"].get("directory") is True and not evidence["application_root"].get("symlink"),
        "home_owned_directory": evidence["home"].get("directory") is True and evidence["home"].get("owned_by_effective_user") is True,
        "publication_ancestry_safe": all(m.get("exists") is False or (m.get("directory") is True and m.get("owned_by_effective_user") is True and not m.get("symlink")) for m in ancestry_meta),
        "versioned_parent_safe": evidence["versioned_parent"].get("exists") is False or (evidence["versioned_parent"].get("directory") is True and evidence["versioned_parent"].get("owned_by_effective_user") is True and not evidence["versioned_parent"].get("symlink")),
        "zip_owner_regular": zip_meta.get("regular") is True and zip_meta.get("owned_by_effective_user") is True and not zip_meta.get("symlink"),
        "wsgi_regular": evidence["passenger_wsgi"].get("regular") is True and evidence["passenger_wsgi"].get("owned_by_effective_user") is True and not evidence["passenger_wsgi"].get("symlink"),
        "htaccess_regular": evidence["htaccess"].get("regular") is True and evidence["htaccess"].get("owned_by_effective_user") is True and not evidence["htaccess"].get("symlink"),
        "zip_hash_match": zip_meta["expected_sha256_matches"] is True,
        "versioned_target_absent": evidence["versioned_target"].get("exists") is False,
    }
    print(json.dumps({"classification": "MPW_C12_READONLY_RELEASE_PREFLIGHT",
                      "evidence": evidence, "conditions": conditions,
                      "all_local_gates": all(conditions.values()),
                      "backup_restorable_verified": False,
                      "public_worker_verified": False,
                      "release_permitted": False,
                      "limitation": "No deployment. Requires independent backup/rollback and public routing proof."}, sort_keys=True))
if __name__ == "__main__":
    main()
