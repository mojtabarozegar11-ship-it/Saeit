#!/usr/bin/env python3
"""Experimental resumable AES-256-GCM snapshot chunk staging (OFFLINE only).

Input MUST already be a consistent, durable snapshot captured separately.
Never connects to MySQL, SSH or Passenger; never moves data onto production.
Every chunk is independently authenticated and remains resumable. A final
signed manifest exists ONLY after the entire source has been checked.
No production activation or backups are inferred from using this utility.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import stat
import sys
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

FORMAT = "MJWP-CHUNK-AEAD-v1"
MAX_SOURCE = 12 * 1024**3
MIN_PART = 1024
MAX_PART = 32 * 1024**2


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _private_directory(root: Path, create=False):
    if create and not root.exists():
        root.mkdir(mode=0o700, parents=False)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Unsafe staging directory")
    s = root.stat()
    if s.st_uid != os.getuid() or bool(s.st_mode & 0o077):
        raise ValueError("Staging directory must be owned and mode 0700")
    return root.resolve()


def _private_key(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Private key file missing")
    s = path.stat()
    if s.st_uid != os.getuid() or (s.st_mode & 0o177) or s.st_size != 32:
        raise ValueError("Key must be exactly 32 bytes in mode 0600")
    return path.read_bytes()


def _signed(obj, key):
    payload = _canonical(obj)
    return dict(obj, mac=hmac.new(key, b"MJWP-manifest-v1:" + payload, hashlib.sha256).hexdigest())


def _load_signed(path, key):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2 * 1024**2:
        raise ValueError("Missing or malformed signed document")
    obj = json.loads(path.read_text(encoding="ascii"))
    if not isinstance(obj, dict):
        raise ValueError("Invalid metadata")
    mac = obj.pop("mac", None)
    if not isinstance(mac, str) or not hmac.compare_digest(_signed(obj, key)["mac"], mac):
        raise ValueError("Invalid metadata signature")
    return obj


def _atomic_new(path, data):
    if path.exists() or path.is_symlink():
        raise ValueError("Refusing to replace existing output")
    pending = path.with_suffix(path.suffix + ".pending")
    if pending.is_symlink():
        raise ValueError("Pending output symlink")
    if pending.exists():
        pending.unlink()  # Only this exact incomplete output, never a valid chunk.
    fd = os.open(str(pending), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, path)
    except Exception:
        try:
            pending.unlink()
        except OSError:
            pass
        raise


def _digest_source(source):
    if source.is_symlink() or not source.is_file():
        raise ValueError("Snapshot source must be a regular file")
    before = source.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size < 1 or before.st_size > MAX_SOURCE:
        raise ValueError("Unsafe or empty snapshot source")
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    after = source.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
    ):
        raise ValueError("Snapshot source changed during hashing")
    return {"size": before.st_size, "sha256": digest.hexdigest()}, after


def _key_and_aad(master, plan, index, plain_bytes):
    key = hmac.new(master, b"MJWP-chunk-encryption-v1", hashlib.sha256).digest()
    plan_digest = hashlib.sha256(_canonical(plan)).digest()
    aad = b"MJWP-chunk-v1:" + plan_digest + index.to_bytes(8, "big") + plain_bytes.to_bytes(8, "big")
    return key, aad


def _decrypt(blob, master, plan, index, length):
    if len(blob) < 29 or len(blob) > MAX_PART + 28:
        raise ValueError("Invalid ciphertext length")
    key, aad = _key_and_aad(master, plan, index, length)
    plain = AESGCM(key).decrypt(blob[:12], blob[12:], aad)
    if len(plain) != length:
        raise ValueError("Chunk plaintext size mismatch")
    return plain


def stage(source, root, name, keyfile, chunk_bytes=8 * 1024**2):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}", name):
        raise ValueError("Invalid snapshot identifier")
    if not MIN_PART <= chunk_bytes <= MAX_PART:
        raise ValueError("Chunk size outside bounded range")
    source, root = Path(source), Path(root)
    master = _private_key(keyfile)
    snapshot, initial_stat = _digest_source(source)
    if not root.exists():
        _private_directory(root, create=True)
    root = _private_directory(root)
    folder = root / name
    _private_directory(folder, create=not folder.exists())
    plan_path = folder / "plan.json"
    expected_plan = {
        "format": FORMAT, "snapshot_id": name, "source": snapshot,
        "chunk_bytes": chunk_bytes,
        "chunk_count": (snapshot["size"] + chunk_bytes - 1) // chunk_bytes,
    }
    if plan_path.exists():
        plan = _load_signed(plan_path, master)
        if plan != expected_plan:
            raise ValueError("Resume rejected: input or plan changed")
    else:
        _atomic_new(plan_path, _canonical(_signed(expected_plan, master)))
        plan = expected_plan
    final_path = folder / "manifest.json"
    if final_path.exists():
        verify(root, name, keyfile)
        return {"status": "verified_existing", "chunks": plan["chunk_count"], "release_permitted": False}
    entries = []
    whole = hashlib.sha256()
    with source.open("rb") as stream:
        for i in range(plan["chunk_count"]):
            plain = stream.read(chunk_bytes)
            if not plain:
                raise ValueError("Source ended early")
            whole.update(plain)
            path = folder / ("part-%06d.bin" % i)
            if path.is_symlink():
                raise ValueError("Chunk symlink not permitted")
            if path.exists():
                ciphertext = path.read_bytes()
                if _decrypt(ciphertext, master, plan, i, len(plain)) != plain:
                    raise ValueError("Existing chunk does not match immutable snapshot")
            else:
                key, aad = _key_and_aad(master, plan, i, len(plain))
                nonce = os.urandom(12)
                ciphertext = nonce + AESGCM(key).encrypt(nonce, plain, aad)
                _atomic_new(path, ciphertext)
            entries.append({
                "index": i, "plain_bytes": len(plain),
                "cipher_bytes": len(ciphertext),
                "cipher_sha256": hashlib.sha256(ciphertext).hexdigest(),
            })
        if stream.read(1):
            raise ValueError("Source exceeded declared length")
    if whole.hexdigest() != snapshot["sha256"]:
        raise ValueError("Source changed while encrypting")
    now_stat = source.stat()
    if (initial_stat.st_dev, initial_stat.st_ino, initial_stat.st_size, initial_stat.st_mtime_ns) != (
        now_stat.st_dev, now_stat.st_ino, now_stat.st_size, now_stat.st_mtime_ns
    ):
        raise ValueError("Source metadata changed")
    manifest = {"format": FORMAT, "plan_sha256": hashlib.sha256(_canonical(plan)).hexdigest(), "chunks": entries}
    _atomic_new(final_path, _canonical(_signed(manifest, master)))
    verify(root, name, keyfile)
    return {"status": "verified_complete", "chunks": len(entries), "release_permitted": False}


def _inspect(root, name, keyfile):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}", name):
        raise ValueError("Invalid snapshot identifier")
    folder = _private_directory(Path(root)) / name
    _private_directory(folder)
    master = _private_key(keyfile)
    plan = _load_signed(folder / "plan.json", master)
    manifest = _load_signed(folder / "manifest.json", master)
    if plan.get("format") != FORMAT or plan.get("snapshot_id") != name:
        raise ValueError("Unexpected backup format or snapshot ID")
    if manifest.get("format") != FORMAT or manifest.get("plan_sha256") != hashlib.sha256(_canonical(plan)).hexdigest():
        raise ValueError("Backup plan mismatch")
    if not isinstance(plan.get("chunk_count"), int) or not 1 <= plan["chunk_count"] <= 12582912:
        raise ValueError("Invalid chunk count")
    if not isinstance(manifest.get("chunks"), list) or len(manifest["chunks"]) != plan["chunk_count"]:
        raise ValueError("Incomplete backup manifest")
    return folder, master, plan, manifest


def verified_chunks(root, name, keyfile):
    folder, master, plan, manifest = _inspect(root, name, keyfile)
    running = hashlib.sha256()
    count = 0
    for i, entry in enumerate(manifest["chunks"]):
        if not isinstance(entry, dict) or entry.get("index") != i:
            raise ValueError("Unordered or incomplete chunk")
        expected_bytes = min(plan["chunk_bytes"], plan["source"]["size"] - i * plan["chunk_bytes"])
        if entry.get("plain_bytes") != expected_bytes:
            raise ValueError("Unexpected chunk length")
        path = folder / ("part-%06d.bin" % i)
        if path.is_symlink() or not path.is_file():
            raise ValueError("Missing protected ciphertext chunk")
        blob = path.read_bytes()
        if len(blob) != entry.get("cipher_bytes") or hashlib.sha256(blob).hexdigest() != entry.get("cipher_sha256"):
            raise ValueError("Ciphertext differs from committed manifest")
        plain = _decrypt(blob, master, plan, i, expected_bytes)
        running.update(plain)
        count += len(plain)
        yield plain
    if count != plan["source"]["size"] or running.hexdigest() != plan["source"]["sha256"]:
        raise ValueError("Recovered bytes differ from original snapshot")


def verify(root, name, keyfile):
    chunks = 0
    for _ in verified_chunks(root, name, keyfile):
        chunks += 1
    return {"verified": True, "chunks": chunks, "release_permitted": False}


def restore(root, name, keyfile, destination):
    destination = Path(destination)
    parent = _private_directory(destination.parent)
    if destination.is_symlink() or destination.exists():
        raise ValueError("Restoration refuses to overwrite an existing file")
    if not parent.is_absolute():
        raise ValueError("Restore destination must be absolute")
    fd = os.open(str(destination), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(fd, "wb") as out:
            for plain in verified_chunks(root, name, keyfile):
                out.write(plain)
            out.flush()
            os.fsync(out.fileno())
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return {"verified_restoration": True, "release_permitted": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["stage", "verify", "restore"])
    parser.add_argument("--root", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--key-file", required=True)
    parser.add_argument("--source")
    parser.add_argument("--chunk-bytes", type=int, default=8 * 1024**2)
    parser.add_argument("--restore-file")
    args = parser.parse_args()
    try:
        if args.command == "stage" and args.source:
            result = stage(args.source, args.root, args.name, args.key_file, args.chunk_bytes)
        elif args.command == "verify":
            result = verify(args.root, args.name, args.key_file)
        elif args.command == "restore" and args.restore_file:
            result = restore(args.root, args.name, args.key_file, args.restore_file)
        else:
            raise ValueError("Missing command arguments")
        print(json.dumps(result, sort_keys=True))
    except Exception:
        # Never disclose source paths, data, key, or cryptographic internals.
        print(json.dumps({"verified": False, "release_permitted": False, "error": "Integrity or safety gate failed"}))
        raise SystemExit(2)
