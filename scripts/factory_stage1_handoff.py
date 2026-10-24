#!/usr/bin/env python3
"""Stage 1 owns only intake validation and a durable handoff to stage 2.

The next stage's queue length, result and availability are never consulted.
A handoff is NOT evidence that stage 2 has researched anything, nor is it
product QA, specialist approval, inventory or permission to publish.
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

ORDER_RE = re.compile(r"WO-[0-9]+\.json\Z")
ID_RE = re.compile(r"WO-[0-9]+\Z")
HASH_RE = re.compile(r"[a-f0-9]{64}\Z")
SCHEMA = "saeit.factory.production-instructions.v1"
HANDOFF_SCHEMA = "saeit.factory.stage-handoff.v1"
RETURN_SCHEMA = "saeit.factory.stage-return.v1"


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                    separators=(",", ":")).encode("utf8")).hexdigest()


def timestamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def safe_dir(path):
    if path.is_symlink():
        raise RuntimeError("STAGE1_SYMLINK_DIRECTORY")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir() or path.is_symlink():
        raise RuntimeError("STAGE1_UNSAFE_DIRECTORY")
    os.chmod(path, 0o700)


def read(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 200_000:
        raise RuntimeError("STAGE1_UNSAFE_INPUT:" + path.name)
    doc = json.loads(path.read_text(encoding="utf8"))
    if not isinstance(doc, dict):
        raise RuntimeError("STAGE1_EXPECTED_OBJECT")
    return doc


def save(path, document):
    safe_dir(path.parent)
    fd, tmp = tempfile.mkstemp(prefix=".stage1-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf8") as stream:
            json.dump(document, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def validate_order(order, required_id):
    if order.get("schema") != SCHEMA or order.get("id") != required_id:
        raise ValueError("STAGE1_BAD_ORDER_ID_OR_SCHEMA")
    if order.get("public_distribution_allowed") is not False:
        raise ValueError("STAGE1_PUBLICATION_NOT_LOCKED")
    if not HASH_RE.fullmatch(str(order.get("fingerprint", ""))):
        raise ValueError("STAGE1_BAD_FINGERPRINT")
    if not HASH_RE.fullmatch(str(order.get("source_sha256", ""))):
        raise ValueError("STAGE1_MISSING_SOURCE_HASH")
    if not isinstance(order.get("subject"), str) or len(order["subject"].strip()) < 8:
        raise ValueError("STAGE1_MISSING_SUBJECT")
    if not isinstance(order.get("instruction"), str) or len(order["instruction"].strip()) < 25:
        raise ValueError("STAGE1_MISSING_INSTRUCTION")
    if not isinstance(order.get("acceptance"), list) or not order["acceptance"]:
        raise ValueError("STAGE1_MISSING_ACCEPTANCE_CRITERIA")
    if not all(isinstance(x, str) and x.strip() for x in order["acceptance"]):
        raise ValueError("STAGE1_BAD_ACCEPTANCE")
    if order.get("manufacturing_qa_passed") is not False:
        raise ValueError("STAGE1_CANNOT_ASSUME_QA")
    if order.get("publication_approved") is not False:
        raise ValueError("STAGE1_CANNOT_ASSUME_PUBLICATION")
    return {
        "identity_checked": True, "private_distribution_locked": True,
        "source_fingerprint_present": True, "input_specification_checked": True,
        "acceptance_requirements_present": True,
        "research_completed": False, "technical_qa1000_certified": False
    }


def forward(root, order, revision=1, returned_from=None):
    ident = order.get("id")
    if not isinstance(ident, str) or not ID_RE.fullmatch(ident):
        raise ValueError("STAGE1_BAD_ORDER_ID")
    checks = validate_order(order, ident)
    area = root / "production-instructions"
    stage1 = area / "stage-01"
    inbox = area / "stage-02" / "inbox"
    receipts = stage1 / "receipts"
    safe_dir(inbox)
    safe_dir(receipts)
    name = ident + "--r" + str(revision).zfill(3) + ".json"
    handoff_file = inbox / name
    receipt_file = receipts / name
    source_hash = digest(order)
    if handoff_file.exists():
        packet = read(handoff_file)
        if (packet.get("schema") != HANDOFF_SCHEMA
                or packet.get("order_id") != ident
                or packet.get("revision") != revision
                or packet.get("source_order_sha256") != source_hash
                or packet.get("stage_1_checks") != checks):
            raise RuntimeError("STAGE1_EXISTING_HANDOFF_CONFLICT:" + name)
        created = False
    else:
        packet = {
            "schema": HANDOFF_SCHEMA, "order_id": ident, "revision": revision,
            "source_order_sha256": source_hash, "stage_1_checks": checks,
            "previous_stage": 1, "next_stage": 2,
            "stage_2_status": "received_pending_processing",
            "work_order": order, "returned_from": returned_from,
            "created_utc": timestamp(), "commercial_release": False,
            "quality1000_approved": False, "public_distribution_allowed": False
        }
        save(handoff_file, packet)
        created = True
    proof = {
        "schema": HANDOFF_SCHEMA, "order_id": ident, "revision": revision,
        "stage_1_completed": True, "stage_2_inbox_record": name,
        "source_order_sha256": source_hash, "stage_2_packet_sha256": digest(packet),
        "commercial_release": False, "research_completed": False
    }
    if receipt_file.exists():
        if read(receipt_file) != proof:
            raise RuntimeError("STAGE1_RECEIPT_CONFLICT:" + name)
    else:
        save(receipt_file, proof)
    return created


def blocked(root, name, error):
    path = root / "production-instructions" / "stage-01" / "blocked" / name
    doc = {"schema": HANDOFF_SCHEMA, "item": name, "stage": 1,
           "status": "needs_stage1_correction", "reason": str(error)[:180],
           "commercial_release": False}
    if path.exists() and read(path) == doc:
        return
    save(path, doc)


def rank(order):
    # Preserve established agriculture P0 order, then explicitly serve all
    # owner-directed education titles before lower-priority generic work.
    if order.get("priority") == "P0":
        if order.get("origin") == "owner_requested_agri200_p0":
            return (0, 0, int(order.get("priority_rank", 999999)), order.get("id", ""))
        if order.get("origin") == "owner_requested_education700_p0":
            return (0, 1, int(order.get("priority_rank", 999999)), order.get("id", ""))
        if order.get("origin") == "owner_requested_jobs300_iran_p0":
            return (0, 2, int(order.get("priority_rank", 999999)), order.get("id", ""))
        if order.get("origin") == "owner_requested_women_home200_iran_p0":
            return (0, 3, int(order.get("priority_rank", 999999)), order.get("id", ""))
    return (1, 0, 0, order.get("id", ""))


def run(root, batch=1000):
    root = Path(root).expanduser().resolve()
    area = root / "production-instructions"
    orders = area / "orders"
    if not root.is_dir() or not orders.is_dir() or orders.is_symlink():
        raise RuntimeError("STAGE1_QUEUE_MISSING")
    lockfile = area / ".orders.lock"
    if lockfile.is_symlink():
        raise RuntimeError("STAGE1_UNSAFE_LOCK")
    with lockfile.open("a+b") as mutex:
        os.chmod(lockfile, 0o600)
        fcntl.flock(mutex.fileno(), fcntl.LOCK_EX)
        sources = []
        for file in orders.iterdir():
            if not ORDER_RE.fullmatch(file.name) or file.is_symlink() or not file.is_file():
                raise RuntimeError("STAGE1_BAD_QUEUE_FILE:" + file.name)
            order = read(file)
            if order.get("status") != "issued":
                continue  # downstream engineering/rework/completion is NOT stage 1
            sources.append(order)
        # Previously forwarded 'issued' orders retain their stage-one receipts.
        # Move them behind orders without a receipt, or >1000 older P0 items
        # could starve every newly approved owner P0 order indefinitely.
        receipts = area / "stage-01" / "receipts"
        sources.sort(key=lambda order: (
            (receipts / (str(order.get("id", "")) + "--r001.json")).exists(),
            rank(order)))
        sent = 0
        bad = 0
        attempted = 0
        for order in sources:
            ident = order.get("id", "unknown")
            if attempted >= batch:
                break
            attempted += 1
            try:
                if forward(root, order):
                    sent += 1
            except (ValueError, RuntimeError) as exc:
                blocked(root, str(ident) + "--r001.json", str(exc))
                bad += 1

        # Explicit returns addressed to stage 1 are independently validated.
        # They require a corrected work order; stage 1 cannot invent a repair.
        returns = area / "stage-01" / "return-inbox"
        safe_dir(returns)
        returned_sent = 0
        for path in sorted(returns.iterdir()):
            if attempted >= batch:
                break
            if not path.name.endswith(".json") or path.is_symlink() or not path.is_file():
                raise RuntimeError("STAGE1_BAD_RETURN_FILE")
            attempted += 1
            try:
                item = read(path)
                order = item.get("corrected_work_order")
                version = item.get("revision")
                if (item.get("schema") != RETURN_SCHEMA
                        or item.get("target_stage") != 1
                        or item.get("source_stage") not in range(2, 11)
                        or not isinstance(version, int) or isinstance(version, bool)
                        or not 2 <= version <= 999
                        or not isinstance(item.get("reason"), str)
                        or not item["reason"].strip()
                        or not isinstance(order, dict)
                        or item.get("order_id") != order.get("id")
                        or not ID_RE.fullmatch(str(item.get("order_id", "")))):
                    raise ValueError("STAGE1_INVALID_RETURN")
                if forward(root, order, version, item["source_stage"]):
                    returned_sent += 1
            except (ValueError, RuntimeError) as exc:
                blocked(root, path.name, str(exc))
                bad += 1
        stat = {
            "schema": HANDOFF_SCHEMA, "stage": 1,
            "new_handoffs": sent, "returned_handoffs": returned_sent,
            "blocked_items_this_run": bad, "scanned_this_run": attempted,
            "still_unscanned": max(0, len(sources) - min(batch, len(sources))),
            "stage_2_worker_verified": False,
            "product_qa1000_certified": False,
            "sites_modified": False, "checked_utc": timestamp()
        }
        save(area / "stage-01" / "status.json", stat)
        return stat


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-private", required=True)
    parser.add_argument("--batch", type=int, default=1000)
    args = parser.parse_args()
    if not 1 <= args.batch <= 2000:
        raise RuntimeError("STAGE1_INVALID_BATCH")
    result = run(args.factory_private, args.batch)
    print("FACTORY_STAGE1_NEW_HANDOFFS=" + str(result["new_handoffs"]))
    print("FACTORY_STAGE1_RETURNED_HANDOFFS=" + str(result["returned_handoffs"]))
    print("FACTORY_STAGE1_BLOCKED=" + str(result["blocked_items_this_run"]))
    print("FACTORY_STAGE2_RESEARCH_COMPLETED=false")
    print("FACTORY_STAGE1_WEBSITES_UNMODIFIED=true")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("FACTORY_STAGE1_ERROR=" + type(exc).__name__ + ":" + str(exc)[:200], file=sys.stderr)
        raise SystemExit(1)
