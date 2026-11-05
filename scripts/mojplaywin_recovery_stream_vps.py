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
MAX_PLAINTEXT_BYTES = 12 * 1024**3  # Scoped files only.
MAX_MYSQL_PLAINTEXT_BYTES = 48 * 1024**3  # Matches the producer SQL hard cap.


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
            not (1024 <= meta["plaintext_bytes"] <= (
                 MAX_MYSQL_PLAINTEXT_BYTES if kind == "mysql" else MAX_PLAINTEXT_BYTES))):
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


def estimate_restore_budget(stem, home=None):
    """Manifest-only, fail-closed runner disk admission floor; no decryption.

    SQL is a logical dump, not the size of a restored MariaDB datadir. Twice
    the plaintext SQL plus 6 GiB is a conservative screening threshold, not
    a guarantee of successful restore. It can reject undersized runners
    before an expensive isolated import without ever exposing private data.
    """
    discover_explicit_pair(stem, home=home)
    _, mysql_meta, _, _ = load("mysql", home=home, stem=stem)
    _, files_meta, _, _ = load("files", home=home, stem=stem)
    gib = 1024 ** 3
    mysql_bytes = mysql_meta["plaintext_bytes"]
    files_bytes = files_meta["plaintext_bytes"]
    required_bytes = max(9 * gib, 2 * mysql_bytes + 6 * gib,
                         2 * files_bytes + 6 * gib)
    ceil_gib = lambda value: (value + gib - 1) // gib
    return {
        "classification": "ISOLATED_RESTORE_DISK_ADMISSION_FLOOR",
        "mysql_plaintext_gib_ceiling": ceil_gib(mysql_bytes),
        "files_plaintext_gib_ceiling": ceil_gib(files_bytes),
        "required_free_gib": ceil_gib(required_bytes),
        "budget_is_sufficiency_proof": False,
        "gpg_stream_reverified": False,
        "isolated_restore_performed": False,
        "release_permitted": False,
    }


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
            if size>(MAX_MYSQL_PLAINTEXT_BYTES if kind == "mysql" else MAX_PLAINTEXT_BYTES):
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


class _VerifyOnlySink:
    """Discard decrypted bytes in-process; never print or persist SQL rows."""
    def write(self, payload):
        return len(payload)

    def flush(self):
        pass


def verify_resumable_sql(stem, home=None):
    """Reverify the existing immutable SQL archive before a files-only resume."""
    if not isinstance(stem, str) or not EXPLICIT_STEM_RE.fullmatch(stem):
        raise RuntimeError("invalid explicit backup-set identity")
    _, meta, _, _ = load("mysql", home=home, stem=stem)
    if (meta.get("backup_set_stem") != stem or
            meta.get("explicit_backup_set_id") is not True or
            meta.get("archive_name") != f"{stem}_mysql_{VERSION}.gpg" or
            meta.get("release_permitted") is not False):
        raise RuntimeError("backup set provenance mismatch")
    size = decrypt_to_stdout("mysql", home=home, stem=stem, out=_VerifyOnlySink())
    return {"classification": "EXISTING_SQL_BACKUP_REVERIFIED_FOR_FILES_RESUME",
            "source_verified": True, "plaintext_bytes": size,
            "isolated_restore_performed": False, "release_permitted": False}


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


def pair_mode_to_kind(mode):
    """Compatible with the older Python 3 interpreters on the private VPS.

    str.removesuffix is unavailable until Python 3.9. An AttributeError at
    this point previously appeared as a generic private restore failure.
    """
    if mode not in ("mysql-pair", "files-pair"):
        raise ValueError("invalid private stream mode")
    return mode[:-len("-pair")]


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
    if mode == "estimate-pair" and len(sys.argv) == 3:
        try:
            report = estimate_restore_budget(sys.argv[2])
        except Exception:
            print("RESTORE_BUDGET_UNAVAILABLE_NO_RELEASE", file=sys.stderr)
            raise SystemExit(1)
        print(json.dumps(report, sort_keys=True))
        raise SystemExit(0)
    if mode == "verify-resume-sql" and len(sys.argv) == 3:
        try:
            report = verify_resumable_sql(sys.argv[2])
        except Exception:
            print("SQL_RESUME_SOURCE_REJECTED_NO_RELEASE", file=sys.stderr)
            raise SystemExit(1)
        print(json.dumps(report, sort_keys=True))
        raise SystemExit(0)
    try:
        if mode in ("mysql-pair", "files-pair") and len(sys.argv) == 3:
            kind = pair_mode_to_kind(mode)
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
    except BrokenPipeError:
        # The isolated SQL consumer closed stdout. This does not implicate
        # the already verified GPG archive; never log private SQL bytes.
        print("PRIVATE_RESTORE_DOWNSTREAM_CLOSED_NO_RELEASE", file=sys.stderr)
        raise SystemExit(1)
    except Exception as error:
        # Exception messages can contain private filesystem paths or SQL;
        # disclose only a fixed type category, never the exception text.
        category = type(error).__name__
        if category not in (
                "AttributeError", "FileNotFoundError", "PermissionError",
                "BrokenPipeError", "OSError", "RuntimeError", "ValueError",
                "TimeoutExpired", "TypeError", "KeyError"):
            category = "OTHER"
        print("PRIVATE_RESTORE_STREAM_INTEGRITY_FAILURE category=" + category,
              file=sys.stderr)
        raise SystemExit(1)
