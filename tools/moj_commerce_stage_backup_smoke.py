"""Offline cPanel staging ONLY: synthetic SQLite backup/restore acceptance.

Never point this script at live files. It refuses paths outside its dedicated
versioned staging root, refuses overwrite, and contains no production credentials.
This is NOT a PostgreSQL restore certification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

STAGE_BASE = Path("/home/zomorod2/Saeit-staging/moj-commerce-v11-synthetic-restore")


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(path), timeout=10)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _logical_receipt(path: Path) -> tuple[str, int, int]:
    with _connect(path) as connection:
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Synthetic database integrity check failed")
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise RuntimeError("Synthetic foreign-key integrity check failed")
        orders = connection.execute(
            "SELECT id, reference, amount_sun, status FROM orders ORDER BY id"
        ).fetchall()
        entitlements = connection.execute(
            "SELECT id, order_id, file_key FROM entitlements ORDER BY id"
        ).fetchall()
    payload = json.dumps(
        {"orders": orders, "entitlements": entitlements},
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest(), len(orders), len(entitlements)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sandbox", required=True)
    arguments = parser.parse_args()

    base = STAGE_BASE.resolve(strict=True)
    sandbox_arg = Path(arguments.sandbox)
    if sandbox_arg.is_symlink():
        raise RuntimeError("Symlink sandbox forbidden")
    sandbox = sandbox_arg.resolve(strict=True)
    if (
        sandbox.parent != base
        or not sandbox.is_dir()
        or not sandbox.name.startswith("mc11-")
    ):
        raise RuntimeError("Refusing operation outside dedicated staging sandbox")

    seed = sandbox / "synthetic_orders.sqlite3"
    snapshot = sandbox / "synthetic_backup.sqlite3"
    restored = sandbox / "synthetic_restored.sqlite3"
    tampered = sandbox / "synthetic_tampered_test.sqlite3"
    if any(path.exists() or path.is_symlink() for path in (seed, snapshot, restored, tampered)):
        raise RuntimeError("Refusing overwrite of existing database or backup")

    with _connect(seed) as connection:
        connection.execute(
            "CREATE TABLE orders "
            "(id INTEGER PRIMARY KEY, reference TEXT UNIQUE NOT NULL, "
            "amount_sun INTEGER NOT NULL, status TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE entitlements "
            "(id INTEGER PRIMARY KEY, order_id INTEGER UNIQUE NOT NULL, "
            "file_key TEXT NOT NULL, FOREIGN KEY(order_id) REFERENCES orders(id))"
        )
        connection.executemany(
            "INSERT INTO orders VALUES (?, ?, ?, ?)",
            [
                (1, "synthetic-pending", 1000000, "pending"),
                (2, "synthetic-paid", 2500000, "delivered"),
                (3, "synthetic-expired", 3000000, "expired"),
            ],
        )
        connection.execute(
            "INSERT INTO entitlements VALUES (1, 2, ?)",
            ("test-only-file-key-" + "a" * 32,),
        )
        connection.commit()
        with _connect(snapshot) as backup_connection:
            connection.backup(backup_connection)

    with _connect(snapshot) as backup_connection:
        with _connect(restored) as restored_connection:
            backup_connection.backup(restored_connection)

    seed_receipt = _logical_receipt(seed)
    backup_receipt = _logical_receipt(snapshot)
    restored_receipt = _logical_receipt(restored)
    if seed_receipt != backup_receipt or backup_receipt != restored_receipt:
        raise RuntimeError("Backup/restore logical receipt mismatch")
    if seed_receipt[1:] != (3, 1):
        raise RuntimeError("Unexpected synthetic counts")

    # Independently exercise fail-closed checksum mismatch detection, keeping
    # the verified snapshot and restoration unchanged for later inspection.
    with _connect(snapshot) as backup_connection:
        with _connect(tampered) as tampered_connection:
            backup_connection.backup(tampered_connection)
    with _connect(tampered) as tampered_connection:
        tampered_connection.execute(
            "UPDATE orders SET status = ? WHERE id = ?", ("pending", 2)
        )
        tampered_connection.commit()
    if _logical_receipt(tampered) == seed_receipt:
        raise RuntimeError("Deliberately altered backup passed logical verification")

    print("V11_SYNTHETIC_BACKUP_RESTORE_PASS")
    print("V11_TAMPERED_DATA_HASH_MISMATCH_DETECTED")
    print("V11_SYNTHETIC_ORDERS=3 ENTITLEMENTS=1")
    print("V11_LOGICAL_SHA256=" + seed_receipt[0])
    print("V11_SQLITE_ONLY_NO_PRODUCTION_DATABASE_NO_REAL_PAYMENTS")


if __name__ == "__main__":
    main()
