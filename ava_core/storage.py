"""Explicit, encrypted SQLite persistence for AVA's owner-consented memories.

The host supplies the database path and a 32-byte secret. Neither is generated,
persisted, or transmitted by AVA. The default AvaRuntime memory is still RAM-only.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path
import sqlite3
import stat
from typing import Sequence

from .core import MemoryItem


class MemoryIntegrityError(ValueError):
    """A stored record was damaged or authenticated metadata was changed."""


class MemoryKeyError(PermissionError):
    """The supplied secret cannot unlock this memory database."""


class EncryptedSQLiteMemory:
    """Owner-scoped encrypted MemoryStore using AES-256-GCM.

    Requires the optional ``cryptography`` package. The host must provision and
    protect the key independently of the SQLite file, authenticate the owner,
    and establish any backup, rotation and access-control policies.
    """

    _CHECK = b"ava-encrypted-memory-v1"

    def __init__(self, path: str | Path, *, key: bytes) -> None:
        if not isinstance(key, bytes) or len(key) != 32:
            raise ValueError("A 32-byte private encryption key is required")
        from cryptography.exceptions import InvalidTag
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF

        self._invalid_tag = InvalidTag
        if not isinstance(path, (str, Path)) or not str(path):
            raise ValueError("An explicit database path is required")
        self._path = Path(path)
        self._prepare_private_file(self._path)
        derived = HKDF(
            algorithm=hashes.SHA256(), length=64, salt=None,
            info=b"ava-memory-store-v1",
        ).derive(key)
        self._cipher = AESGCM(derived[:32])
        self._lookup_key = derived[32:]
        self._db = sqlite3.connect(str(self._path), timeout=5)
        try:
            self._db.execute("PRAGMA trusted_schema=OFF")
            self._db.execute("PRAGMA secure_delete=ON")
            self._db.execute("PRAGMA journal_mode=DELETE")
            self._db.execute("PRAGMA synchronous=FULL")
            with self._db:
                self._db.execute(
                    "CREATE TABLE IF NOT EXISTS memory ("
                    "id TEXT PRIMARY KEY, owner_tag BLOB NOT NULL, "
                    "created_at TEXT NOT NULL, nonce BLOB NOT NULL, "
                    "ciphertext BLOB NOT NULL)"
                )
                self._db.execute(
                    "CREATE INDEX IF NOT EXISTS memory_owner "
                    "ON memory(owner_tag, created_at, id)"
                )
                self._db.execute(
                    "CREATE TABLE IF NOT EXISTS key_check ("
                    "id INTEGER PRIMARY KEY CHECK (id = 1), "
                    "nonce BLOB NOT NULL, ciphertext BLOB NOT NULL)"
                )
                record = self._db.execute(
                    "SELECT nonce, ciphertext FROM key_check WHERE id=1"
                ).fetchone()
                if record is None:
                    if self._db.execute("SELECT 1 FROM memory LIMIT 1").fetchone():
                        raise MemoryKeyError("Database has records but no key verifier")
                    nonce = os.urandom(12)
                    sealed = self._cipher.encrypt(nonce, self._CHECK, b"ava:key-check")
                    self._db.execute(
                        "INSERT INTO key_check(id, nonce, ciphertext) VALUES(1, ?, ?)",
                        (nonce, sealed),
                    )
                else:
                    try:
                        check = self._cipher.decrypt(record[0], record[1], b"ava:key-check")
                    except (InvalidTag, ValueError) as exc:
                        raise MemoryKeyError("Incorrect key or invalid key verifier") from exc
                    if check != self._CHECK:
                        raise MemoryKeyError("Unsupported memory database key verifier")
        except Exception:
            self._db.close()
            raise

    @staticmethod
    def _prepare_private_file(path: Path) -> None:
        if path.is_symlink():
            raise PermissionError("Symlink memory paths are not allowed")
        flags = os.O_CREAT | os.O_RDWR
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(path, flags, 0o600)
        try:
            mode = os.fstat(fd).st_mode
            if not stat.S_ISREG(mode) or stat.S_IMODE(mode) & 0o077:
                raise PermissionError("Memory database must be a private regular file (0600)")
        finally:
            os.close(fd)

    def _tag(self, owner_id: str) -> bytes:
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise ValueError("owner_id is required")
        return hmac.new(self._lookup_key, owner_id.encode("utf-8"), hashlib.sha256).digest()

    @staticmethod
    def _aad(owner_tag: bytes, memory_id: str, created_at: str) -> bytes:
        return b"ava:memory:v1\0" + owner_tag + b"\0" + memory_id.encode() + b"\0" + created_at.encode()

    def add(self, item: MemoryItem) -> None:
        if not isinstance(item, MemoryItem) or not isinstance(item.text, str):
            raise TypeError("MemoryItem with textual content required")
        if not item.id or not item.created_at or not item.text.strip():
            raise ValueError("Memory id, timestamp and nonblank content are required")
        tag = self._tag(item.owner_id)
        nonce = os.urandom(12)
        sealed = self._cipher.encrypt(
            nonce, item.text.encode("utf-8"), self._aad(tag, item.id, item.created_at)
        )
        with self._db:
            self._db.execute(
                "INSERT INTO memory(id, owner_tag, created_at, nonce, ciphertext) "
                "VALUES(?, ?, ?, ?, ?)",
                (item.id, tag, item.created_at, nonce, sealed),
            )

    def list_for_owner(self, owner_id: str) -> Sequence[MemoryItem]:
        tag = self._tag(owner_id)
        records = self._db.execute(
            "SELECT id, created_at, nonce, ciphertext FROM memory "
            "WHERE owner_tag=? ORDER BY created_at, id", (tag,)
        ).fetchall()
        result = []
        for memory_id, created_at, nonce, sealed in records:
            try:
                text = self._cipher.decrypt(
                    nonce, sealed, self._aad(tag, memory_id, created_at)
                ).decode("utf-8")
            except (self._invalid_tag, UnicodeDecodeError, ValueError) as exc:
                raise MemoryIntegrityError("Memory authentication failed") from exc
            result.append(MemoryItem(memory_id, owner_id, text, created_at))
        return tuple(result)

    def delete(self, owner_id: str, memory_id: str) -> bool:
        tag = self._tag(owner_id)
        with self._db:
            result = self._db.execute(
                "DELETE FROM memory WHERE owner_tag=? AND id=?", (tag, memory_id)
            )
        return result.rowcount == 1

    def close(self) -> None:
        """Release the SQLite connection; the host retains the secret."""
        self._db.close()

    def __enter__(self) -> EncryptedSQLiteMemory:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
