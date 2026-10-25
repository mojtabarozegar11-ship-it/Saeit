#!/usr/bin/env python3
"""Safely merge an owner-proposed 500-product backlog into the EXISTING factory intake.

Does not manufacture, change sites, alter existing orders, mark QA success or
claim verified market demand. Idempotent; private SHA-receipted source archive.
Compatible with factory_continuous_production_orders.py offline snapshot reader.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

SCHEMA = "saeit.factory.production-instructions.v1"
KEY = re.compile(r"^[A-Za-z0-9_-]{4,64}$")
MAX_ITEMS = 1000
MAX_BYTES = 2_000_000
EXPECTED = 500

def sha(data):
    return hashlib.sha256(data).hexdigest()

def read(path):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_BYTES:
        raise ValueError("DEMAND_UNSAFE_OR_OVERSIZED_FILE")
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf8"))
    if not isinstance(value, dict):
        raise ValueError("DEMAND_JSON_OBJECT_REQUIRED")
    return raw, value

def validate(doc, required_count=None):
    rows = doc.get("items")
    if (doc.get("schema") != SCHEMA or not isinstance(rows, list)
            or not 0 <= len(rows) <= MAX_ITEMS
            or (required_count is not None and len(rows) != required_count)):
        raise ValueError("DEMAND_SCHEMA_OR_CARDINALITY")
    ids = set()
    titles = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("DEMAND_ENTRY_OBJECT_REQUIRED")
        identity, title, description = (row.get("id"), row.get("title"),
                                        row.get("specification"))
        if (not isinstance(identity, str) or not KEY.fullmatch(identity)
                or not isinstance(title, str) or not 8 <= len(title) <= 160
                or not isinstance(description, str) or not 30 <= len(description) <= 3000):
            raise ValueError("DEMAND_ENTRY_INVALID")
        if identity in ids or (required_count and title.casefold().strip() in titles):
            raise ValueError("DEMAND_DUPLICATE_PRODUCT")
        ids.add(identity)
        titles.add(title.casefold().strip())
    return rows

def atomic_bytes(path, data):
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("DEMAND_OUTPUT_SYMLINK")
    fd, tmp = tempfile.mkstemp(prefix=".demand-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def merge(root, catalog_path):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("DEMAND_FACTORY_ROOT_UNSAFE")
    source_bytes, supplied = read(Path(catalog_path))
    incoming = validate(supplied, EXPECTED)
    if supplied.get("market_demand_verified") is not False:
        raise ValueError("DEMAND_UNVERIFIED_MARKET_MUST_BE_EXPLICIT")
    folder = root / "production-order-inputs"
    if folder.is_symlink():
        raise ValueError("DEMAND_INPUT_DIRECTORY_SYMLINK")
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(folder, 0o700)
    history = folder / "owner-demand-history"
    if history.is_symlink():
        raise ValueError("DEMAND_HISTORY_SYMLINK")
    history.mkdir(mode=0o700, exist_ok=True)
    file = folder / "factory-invention-snapshot.json"
    lock_path = folder / ".owner-demand-500.lock"
    if lock_path.is_symlink():
        raise ValueError("DEMAND_LOCK_SYMLINK")
    with lock_path.open("a+b") as lock:
        os.fchmod(lock.fileno(), 0o600)
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        before_bytes = b""
        old_rows = []
        prior_metadata = {}
        if file.exists() or file.is_symlink():
            before_bytes, before = read(file)
            old_rows = validate(before)
            prior_metadata = {k:v for k,v in before.items() if k not in ("items",)}
        lookup = {x["id"]: x for x in old_rows}
        appended = []
        matching = 0
        for row in incoming:
            old = lookup.get(row["id"])
            if old is None:
                appended.append(row)
            elif (old["title"] != row["title"]
                  or old["specification"] != row["specification"]):
                raise ValueError("DEMAND_EXISTING_ID_CONFLICT")
            else:
                matching += 1
        merged = old_rows + appended
        if len(merged) > MAX_ITEMS:
            raise ValueError("DEMAND_FACTORY_SNAPSHOT_CAPACITY_1000")
        new_doc = dict(prior_metadata)
        new_doc.update({"schema": SCHEMA, "items": merged,
                        "market_demand_verified": False,
                        "owner_demand_snapshot_source_sha256": sha(source_bytes)})
        encoded = (json.dumps(new_doc, ensure_ascii=False, sort_keys=True,
                              indent=2) + "\n").encode("utf8")
        if len(encoded) > MAX_BYTES:
            raise ValueError("DEMAND_FACTORY_SNAPSHOT_EXCEEDS_2MB")
        # Keep an immutable original snapshot before any replacement.
        if before_bytes:
            previous = history / ("prior-" + sha(before_bytes) + ".json")
            if previous.exists():
                if previous.is_symlink() or previous.read_bytes() != before_bytes:
                    raise ValueError("DEMAND_OLD_BACKUP_MISMATCH")
            else:
                fd = os.open(str(previous), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(before_bytes)
                    stream.flush()
                    os.fsync(stream.fileno())
        if not file.exists() or file.read_bytes() != encoded:
            atomic_bytes(file, encoded)
        if sha(file.read_bytes()) != sha(encoded):
            raise RuntimeError("DEMAND_READBACK_HASH_FAILED")
        # Archive the original 500-item snapshot, separately from live merge.
        archived = history / ("owner-proposals-" + sha(source_bytes) + ".json")
        if archived.exists():
            if archived.is_symlink() or archived.read_bytes() != source_bytes:
                raise ValueError("DEMAND_ARCHIVE_TAMPERED")
        else:
            fd = os.open(str(archived), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(source_bytes)
                stream.flush()
                os.fsync(stream.fileno())
        return {
            "schema": "saeit.factory.owner-demand-intake-receipt.v1",
            "catalog_items": EXPECTED,
            "newly_added_to_factory_snapshot": len(appended),
            "already_present_exact_matches": matching,
            "previous_snapshot_items": len(old_rows),
            "current_snapshot_items": len(merged),
            "catalog_source_sha256": sha(source_bytes),
            "factory_snapshot_sha256": sha(encoded),
            "preserved_existing_input": True,
            "technical_products_built": 0,
            "quality1000_certifications_created": 0,
            "public_site_changes": 0
        }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--factory-private", type=Path, required=True)
    ap.add_argument("--catalog", type=Path, required=True)
    args = ap.parse_args()
    print("FACTORY_OWNER_500_INTAKE=" + json.dumps(
        merge(args.factory_private, args.catalog), ensure_ascii=False, sort_keys=True))

if __name__ == "__main__":
    main()
