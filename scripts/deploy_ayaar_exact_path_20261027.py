#!/usr/bin/env python3
"""One-directory MojPlayWin AYAR static release, without shared runtime changes.

Usage (from trusted pinned SSH account):
  python3 - preflight RUN_ID SOURCE_SHA
  python3 - install   RUN_ID SOURCE_SHA
  python3 - rollback  RUN_ID SOURCE_SHA

Never writes .htaccess, Django, Passenger, databases or another subsite.
"""
from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
import stat
import sys
from pathlib import Path

HOME = Path("/home/zomorod2")
ROOT = HOME / "mojplaywin.com"
TARGET = ROOT / "ayaar"
FILES = {
    "index.html", "methodology.html", "styles.css", "hero.css",
    "app.js", "favicon.svg", "hero-art.svg",
}
META = {"manifest.sha256", "deployment.json"}


def stop(reason: str) -> None:
    raise RuntimeError(reason)


def validated_args():
    if len(sys.argv) != 4:
        stop("usage: MODE RUN_ID SOURCE_SHA")
    mode, run_id, sha = sys.argv[1:]
    if mode not in {"preflight", "install", "rollback"}:
        stop("unexpected_mode")
    if re.fullmatch(r"[0-9]{5,25}_[0-9]{1,3}", run_id) is None:
        stop("invalid_run_id")
    if re.fullmatch(r"[0-9a-f]{40}", sha) is None:
        stop("invalid_source_sha")
    return mode, run_id, sha


def shared_preflight():
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        stop("unexpected_cpanel_account")
    if not ROOT.is_dir() or ROOT.is_symlink() or ROOT.resolve() != ROOT:
        stop("unexpected_document_root")
    for name in (".htaccess", "passenger_wsgi.py"):
        path = ROOT / name
        if not path.is_file() or path.is_symlink():
            stop("missing_or_unsafe_document_root_contract")
    rules = (ROOT / ".htaccess").read_text(encoding="utf-8", errors="replace")
    # A pre-existing AYAR routing rule or alias needs an independent decision.
    if re.search(r"ayaar", rules, re.IGNORECASE):
        stop("ayaar_route_conflict_in_existing_htaccess")
    # Never overwrite a child site, even if it happens to have our chosen name.
    if TARGET.exists() or TARGET.is_symlink():
        stop("ayaar_target_already_exists")


def stage_for(run_id: str) -> Path:
    return HOME / (".mpw-ayaar-stage-" + run_id)


def quarantine_for(run_id: str) -> Path:
    return HOME / (".mpw-ayaar-quarantine-" + run_id)


def inspect_payload(stage: Path, run_id: str, sha: str):
    if not stage.is_dir() or stage.is_symlink():
        stop("missing_or_symlink_stage")
    if stage.resolve() != stage:
        stop("unexpected_stage_path")
    children = {p.name for p in stage.iterdir()}
    if children != FILES | META:
        stop("unexpected_payload_file_set")
    for path in stage.iterdir():
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or path.is_symlink():
            stop("unsafe_nonregular_payload")
        if info.st_size > 350_000 or info.st_size == 0:
            stop("unexpected_payload_file_size")
    metadata = json.loads((stage / "deployment.json").read_text("utf-8"))
    if metadata != {"run_id": run_id, "source_sha": sha, "identity": "MPW_AYAAR_EXACT_PATH_V1"}:
        stop("unmatched_release_identity")
    expected = {}
    for row in (stage / "manifest.sha256").read_text("utf-8").splitlines():
        match = re.fullmatch(r"([a-f0-9]{64})  ([a-z0-9.-]+)", row)
        if match is None:
            stop("invalid_hash_manifest")
        digest, name = match.groups()
        if name in expected or name not in FILES:
            stop("invalid_hash_manifest_members")
        expected[name] = digest
    if set(expected) != FILES:
        stop("missing_hash_entries")
    for name in FILES:
        actual = hashlib.sha256((stage / name).read_bytes()).hexdigest()
        if actual != expected[name]:
            stop("asset_hash_mismatch")
    if "AYAR — Digital Product Review" not in (stage / "index.html").read_text("utf-8"):
        stop("homepage_identity_not_found")
    if "AYAR-PREASSESSMENT-v1" not in (stage / "app.js").read_text("utf-8"):
        stop("review_engine_identity_not_found")


def install(run_id: str, sha: str):
    shared_preflight()
    stage = stage_for(run_id)
    inspect_payload(stage, run_id, sha)
    # HOME and document root are on the same cPanel account volume.
    # We refuse to replace any existing target; no shared app reload.
    stage.rename(TARGET)
    if not (TARGET / "index.html").is_file():
        stop("release_moved_without_index")
    print("AYAAR_STATIC_DIR_INSTALLED=TRUE")
    print("AYAAR_SHARED_RUNTIME_RESTART=FALSE")
    print("AYAAR_DOCUMENT_ROOT_REWRITE=FALSE")


def rollback(run_id: str, sha: str):
    if not TARGET.is_dir() or TARGET.is_symlink():
        stop("target_not_a_directory")
    if quarantine_for(run_id).exists():
        stop("quarantine_target_exists")
    inspect_payload(TARGET, run_id, sha)
    TARGET.rename(quarantine_for(run_id))
    print("AYAAR_EXACT_RELEASE_QUARANTINED=TRUE")


def main():
    mode, run_id, sha = validated_args()
    if mode == "preflight":
        shared_preflight()
        print("AYAAR_DOCROOT_AND_ROUTE_PREFLIGHT=PASS")
    elif mode == "install":
        install(run_id, sha)
    else:
        rollback(run_id, sha)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Surface only our bounded error classifier, not private filesystem data.
        print("AYAAR_RELEASE_ABORTED=" + str(exc), file=sys.stderr)
        sys.exit(1)
