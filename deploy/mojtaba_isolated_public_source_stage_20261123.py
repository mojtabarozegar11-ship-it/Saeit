"""Isolated, fail-closed staging of an exact reviewed 14-file Mojtaba source bundle.

Run only on the scoped cPanel account via the already-authorized GitHub VPS
runner. Never modifies the Passenger tree, database, cron or public website.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
from datetime import datetime, timezone

MAIN_SHA = "f33269ff19dccd70131c93df04068618b65bb18e"
BASE = Path("/home/zomorod2/separated-backups/mojtaba-canonical-content-20261123")
APP = Path("/home/zomorod2/Saeit-mojprop-candidate-20261122")
OLD_STAGE = BASE / "release-candidate-2952-shared-fast-health"
NEW_STAGE = BASE / "release-candidate-main-f33269ff-public-help"
PORTAL_FILES = (
    "core/mojtaba_bot_portal.py",
    "templates/core/mojtaba_bot_portal.html",
)


def digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def run(inbox: Path) -> None:
    assert inbox.parent == BASE and inbox.is_dir() and not inbox.is_symlink()
    assert APP.is_dir() and not APP.is_symlink()
    assert OLD_STAGE.is_dir() and not OLD_STAGE.is_symlink()
    old = json.loads((OLD_STAGE / "candidate_manifest.json").read_text(encoding="utf8"))
    request = json.loads((inbox / "pins.json").read_text(encoding="utf8"))
    pins = request["source_files"]
    assert request["main_commit"] == MAIN_SHA and len(pins) == 14
    assert len(old["candidate_files"]) == 12
    assert set(old["candidate_files"]) | set(PORTAL_FILES) == set(pins)

    for rel, prior in old["candidate_files"].items():
        src = OLD_STAGE / rel
        assert src.is_file() and not src.is_symlink(), rel
        assert digest(src.read_bytes()) == prior["sha256"] == pins[rel]["sha256"], rel
    for rel, prior in old["original_files"].items():
        src = APP / rel
        assert src.is_file() and not src.is_symlink(), rel
        assert digest(src.read_bytes()) == prior["sha256"], rel

    source = {}
    with tarfile.open(inbox / "source.tar.gz", "r:gz") as tar:
        members = tar.getmembers()
        assert len(members) == len(pins)
        assert {m.name for m in members} == set(pins)
        for member in members:
            assert member.isfile() and member.size <= 1_000_000
            stream = tar.extractfile(member)
            assert stream is not None
            blob = stream.read()
            assert digest(blob) == pins[member.name]["sha256"], member.name
            assert len(blob) == pins[member.name]["bytes"], member.name
            if member.name.endswith(".py"):
                compile(blob, member.name, "exec")
            source[member.name] = blob

    if NEW_STAGE.exists():
        mf = NEW_STAGE / "candidate_manifest.json"
        prior = json.loads(mf.read_text(encoding="utf8"))
        assert prior["source_main_commit"] == MAIN_SHA
        assert len(prior["candidate_files"]) == 14
        assert all(digest((NEW_STAGE / rel).read_bytes()) == record["sha256"]
                   for rel, record in prior["candidate_files"].items())
        print("EXACT_MAIN_STAGE_REUSED_AND_HASH_CHECKED=YES")
        print("EXACT_STAGE_MANIFEST_SHA256=" + digest(mf.read_bytes()))
        return

    os.umask(0o077)
    tmp = Path(tempfile.mkdtemp(dir=BASE, prefix=".stage-f332-"))
    completed = False
    try:
        originals = dict(old["original_files"])
        for rel, blob in source.items():
            target = tmp / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(blob)
        for rel in PORTAL_FILES:
            live = APP / rel
            assert live.is_file() and not live.is_symlink(), rel
            original = live.read_bytes()
            originals[rel] = {"sha256": digest(original), "bytes": len(original)}

        backup = tmp / "public-portal-prechange.tar.gz"
        with tarfile.open(backup, "w:gz") as tar:
            for rel in PORTAL_FILES:
                tar.add(APP / rel, arcname=rel, recursive=False)
        with tarfile.open(backup, "r:gz") as tar:
            for rel in PORTAL_FILES:
                stream = tar.extractfile(rel)
                assert stream is not None
                assert digest(stream.read()) == originals[rel]["sha256"]

        assert len(originals) == 10
        manifest = {
            "schema": "mojtaba-isolated-public-helper-exact-main-v1",
            "source_main_commit": MAIN_SHA,
            "candidate_files": pins,
            "original_files": originals,
            "original_public_portal_rollback_verified": True,
            "original_public_portal_archive_sha256": digest(backup.read_bytes()),
            "production_code_modified": False,
            "customer_database_modified": False,
            "release_approved": False,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        mf = tmp / "candidate_manifest.json"
        mf.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf8")
        for path in tmp.rglob("*"):
            if path.is_file():
                path.chmod(0o600)
        tmp.rename(NEW_STAGE)
        completed = True
        print("NEW_ISOLATED_EXACT_MAIN_STAGE=CREATED")
        print("SOURCE_FILES_VALIDATED=14")
        print("PRECHANGE_SOURCE_PINS_VERIFIED=10")
        print("PUBLIC_PORTAL_BACKUP_RESTORE=VERIFIED")
        print("EXACT_STAGE_MANIFEST_SHA256=" + digest((NEW_STAGE / "candidate_manifest.json").read_bytes()))
    finally:
        if not completed and tmp.exists():
            shutil.rmtree(tmp)


def package(root: Path, out: Path) -> None:
    """Construct a hash-verified, 14-file bundle from pinned reviewed main."""
    import io
    import subprocess
    assert subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip() == MAIN_SHA
    paths = [
        "core/canonical_content_owner.py",
        "core/company_activity_agent.py",
        "core/knowledge_agent.py",
        "core/management/commands/company_activity_agent_cycle.py",
        "core/management/commands/knowledge_agent_generate.py",
        "core/management/commands/mojtaba_capability_status.py",
        "core/newsletter_engine.py",
        "core/weather_agent.py",
        "core/chat_runtime.py",
        "core/customer_sales_faq.py",
        "core/task_health_sample.py",
        "core/mojtaba_readonly_status.py",
        *PORTAL_FILES,
    ]
    out.mkdir(mode=0o700, parents=True, exist_ok=True)
    pins = {}
    with tarfile.open(out / "source.tar.gz", "w:gz") as tar:
        for rel in paths:
            p = root / rel
            assert p.is_file() and not p.is_symlink()
            blob = p.read_bytes()
            assert len(blob) < 1_000_000
            if rel.endswith(".py"):
                compile(blob, rel, "exec")
            pins[rel] = {"sha256": digest(blob), "bytes": len(blob)}
            entry = tarfile.TarInfo(rel)
            entry.size = len(blob)
            entry.mode = 0o600
            tar.addfile(entry, io.BytesIO(blob))
    (out / "pins.json").write_text(
        json.dumps({"main_commit": MAIN_SHA, "source_files": pins}, indent=2),
        encoding="utf8",
    )
    print("EXACT_MERGED_SOURCE_FILES_PINNED=14")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "package":
        package(Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve())
    elif len(sys.argv) == 2:
        run(Path(sys.argv[1]).resolve())
        print("PASSENGER_LIVE_FILES_CHANGED=NO")
        print("DATABASE_WRITES=NO")
        print("PRODUCTION_DEPLOYED=NO")
    else:
        raise SystemExit("Usage: stage.py package PINNED_SOURCE OUT | stage.py ABSOLUTE_SCOPED_INBOX")
