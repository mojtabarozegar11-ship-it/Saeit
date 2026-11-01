#!/usr/bin/env python3
"""One-time encrypted MojPlayWin recovery drill: decrypt on VPS, stream over pinned SSH.

Only the two fixed, manifest-verified GPGv2 primary-backup archives are eligible.
Never exposes the VPS recovery key, database identifier, SQL rows, file paths,
customer content or SHA hashes in logs. stdout in mysql/files modes is BINARY
PRIVATE DATA: route to isolated restore subprocess, never GitHub logs/artifacts.
Authenticated GPG verification and source footer + SHA256 must ALL succeed.
No VPS / cPanel site writes, SQL import, Passenger or production restart.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

STEM = "mojplaywin_20261017"
VERSION = "gpgv2"
# One owner-approved run; newer archives get independent timestamp/nonce stems.
NEW_RUN_DAY = "20261021"
STEM_RE = re.compile(r"^mojplaywin_(?:20261017|[0-9]{8}T[0-9]{6}Z_[0-9a-f]{16})$")
EXPLICIT_STEM_RE = re.compile(r"^mojplaywin_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{16}$")
NEW_MANIFEST_RE = re.compile(r"^(mojplaywin_20261021T[0-9]{6}Z_[0-9a-f]{16})_(mysql|files)_gpgv2[.]manifest[.]json$")
MARKER = b"\n-- MJWP-RECOVERY-20261017-COMPLETE-F91D7C40 --\n"
MAX_PLAINTEXT_BYTES = 12 * 1024**3


def safe_regular(path, *, private=False):
    if path.is_symlink():
        return False
    try:
        s = path.stat()
        return (stat.S_ISREG(s.st_mode) and s.st_uid == os.getuid() and
                (not private or not bool(s.st_mode & 0o177)))
    except OSError:
        return False


def load(kind, home=None, stem=None):
    if kind not in ("mysql", "files"):
        raise ValueError("invalid kind")
    stem = STEM if stem is None else stem
    if not STEM_RE.fullmatch(stem):
        raise RuntimeError("unsafe backup identity")
    home = Path.home() if home is None else home
    root = home / ".private-mojplaywin-offhost-backups"
    keyroot = home / ".config" / "mojplaywin-backup-recovery"
    ciphertext = root / (stem + "_" + kind + "_" + VERSION + ".gpg")
    manifest = root / (stem + "_" + kind + "_" + VERSION + ".manifest.json")
    keyfile = keyroot / "recovery-key.bin"
    for parent in (root, keyroot, keyroot / "gnupg-v2"):
        if parent.is_symlink() or not parent.is_dir():
            raise RuntimeError("private backup prerequisite absent")
    if not all(safe_regular(x, private=True) for x in (ciphertext, manifest, keyfile)):
        raise RuntimeError("complete encrypted source or private key absent")
    meta = json.loads(manifest.read_text(encoding="ascii"))
    if (meta.get("kind") != kind or meta.get("archive_name", ciphertext.name) != ciphertext.name or
            meta.get("format") != "OpenPGP-AES256-GPGv2" or
            meta.get("ciphertext_roundtrip_integrity_verified") is not True or
            meta.get("source_completion_footer_verified") is not True or
            meta.get("encrypted_bytes") != ciphertext.stat().st_size or
            not isinstance(meta.get("plaintext_sha256"), str) or
            len(meta["plaintext_sha256"]) != 64 or
            not isinstance(meta.get("plaintext_bytes"), int) or
            not (1024 <= meta["plaintext_bytes"] <= MAX_PLAINTEXT_BYTES)):
        raise RuntimeError("backup manifest incomplete or invalid")
    key = keyfile.read_bytes()
    if len(key) != 32:
        raise RuntimeError("invalid private recovery key")
    return ciphertext, meta, keyroot / "gnupg-v2", key


def discover(home=None):
    """Fail closed unless exactly one valid, owner-approved 2026-10-21 pair exists."""
    home = Path.home() if home is None else home
    root = home / ".private-mojplaywin-offhost-backups"
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("private backup directory missing")
    found = {"mysql": [], "files": []}
    for p in root.iterdir():
        match = NEW_MANIFEST_RE.fullmatch(p.name)
        if match:
            found[match.group(2)].append(match.group(1))
    if any(len(found[k]) != 1 for k in found):
        raise RuntimeError("missing or ambiguous independent backup pair")
    stems = {k: found[k][0] for k in found}
    for kind, stem in stems.items():
        load(kind, home=home, stem=stem)
    return stems


def discover_explicit_pair(stem, home=None):
    """Select exactly the two manifests from the one explicitly named new set.

    No silent fallback to the historical 2026-10-21 discovery is permitted.
    This checks metadata, not yet authenticated stream restore.
    """
    if not isinstance(stem, str) or not EXPLICIT_STEM_RE.fullmatch(stem):
        raise RuntimeError("invalid explicit backup-set identity")
    chosen = {}
    for kind in ("mysql", "files"):
        _, meta, _, _ = load(kind, home=home, stem=stem)
        if (meta.get("backup_set_stem") != stem or
                meta.get("explicit_backup_set_id") is not True or
                meta.get("archive_name") != f"{stem}_{kind}_{VERSION}.gpg" or
                meta.get("release_permitted") is not False):
            raise RuntimeError("backup set provenance mismatch")
        chosen[kind] = stem
    return chosen


def explicit_pair_readiness(stem, home=None):
    try:
        discover_explicit_pair(stem, home=home)
        selectable = True
    except Exception:
        selectable = False
    return {"classification": "EXPLICIT_BACKUP_PAIR_MANIFEST_READINESS",
            "both_manifests_selectable": selectable,
            "gpg_stream_reverified": False,
            "isolated_restore_performed": False,
            "passenger_effective_database_proven": False,
            "release_permitted": False}


def decrypt_to_stdout(kind, *, home=None, out=None, stem=None):
    path, meta, ghome, key = load(kind, home=home, stem=stem)
    passphrase = hashlib.sha256(key + b":MJWP:GPG-AES256:20261017:v2").hexdigest().encode()+b"\n"
    r, w = os.pipe()
    try:
        os.write(w, passphrase)
    finally:
        os.close(w)
    try:
        proc = subprocess.Popen([
            "gpg", "--homedir", str(ghome), "--batch", "--no-tty",
            "--pinentry-mode", "loopback", "--passphrase-fd", str(r),
            "--no-options", "--decrypt", "--output", "-", str(path)
        ],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
           pass_fds=(r,))
    finally:
        os.close(r)
    size=0
    digest=hashlib.sha256()
    tail=b""
    stream=out if out is not None else sys.stdout.buffer
    try:
        assert proc.stdout is not None
        for block in iter(lambda:proc.stdout.read(131072),b""):
            size+=len(block)
            if size>MAX_PLAINTEXT_BYTES:
                raise RuntimeError("stream too large")
            digest.update(block)
            tail=(tail+block)[-len(MARKER):]
            stream.write(block)
        stream.flush()
        if proc.wait(timeout=60)!=0:
            raise RuntimeError("GPG integrity verification failed")
        if (size!=meta["plaintext_bytes"] or
                digest.hexdigest()!=meta["plaintext_sha256"] or
                tail!=MARKER):
            raise RuntimeError("source archive footer or checksum mismatch")
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    return size


def readiness(home=None):
    try:
        discover(home)
        return {"classification":"ONE_PASS_RECOVERY_SOURCE_READINESS",
                "both_primary_archives_complete":True,
                "isolated_restore_performed":False,
                "all_unknown_subsites_covered":False,
                "release_permitted":False}
    except Exception:
        return {"classification":"ONE_PASS_RECOVERY_SOURCE_READINESS",
                "both_primary_archives_complete":False,
                "isolated_restore_performed":False,
                "all_unknown_subsites_covered":False,
                "release_permitted":False}


if __name__=="__main__":
    if len(sys.argv) not in (2, 3):
        raise SystemExit(2)
    mode = sys.argv[1]
    if mode == "check" and len(sys.argv) == 2:
        report = readiness()  # Historical, date-pinned API only.
        print(json.dumps(report, sort_keys=True))
        raise SystemExit(0 if report["both_primary_archives_complete"] else 1)
    if mode == "check-pair" and len(sys.argv) == 3:
        report = explicit_pair_readiness(sys.argv[2])
        print(json.dumps(report, sort_keys=True))
        raise SystemExit(0 if report["both_manifests_selectable"] else 1)
    try:
        if mode in ("mysql-pair", "files-pair") and len(sys.argv) == 3:
            kind = mode.removesuffix("-pair")
            stems = discover_explicit_pair(sys.argv[2])
        elif mode in ("mysql", "files") and len(sys.argv) == 2:
            kind = mode
            stems = discover()  # Historical, date-pinned API only.
        else:
            raise RuntimeError("unsupported operation")
        size = decrypt_to_stdout(kind, stem=stems[kind])
        print(json.dumps({"classification": "PRIVATE_STREAM_VERIFIED",
                          "source_kind": kind, "source_verified": True,
                          "plaintext_bytes": size, "release_permitted": False},
                         sort_keys=True), file=sys.stderr)
    except Exception:
        print("PRIVATE_RESTORE_STREAM_INTEGRITY_FAILURE", file=sys.stderr)
        raise SystemExit(1)
