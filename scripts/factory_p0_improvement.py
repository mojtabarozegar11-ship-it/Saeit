#!/usr/bin/env python3
"""P0 factory improvement loop: independent proof, bounded rework, no fake releases.

Reads only private factory evidence. Issues real, idempotent work-order-specific
remediation tickets. Never forges passports, changes live workers or publishes.
An increase in GitHub runs, generations, task counts or technical stock is NOT
a verified new product. Python 3.8+, stdlib only.
"""
import argparse
import fcntl
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
import tempfile
import zipfile

SCHEMA = "saeit.factory.p0.measured-improvement.v1"
LIFECYCLE = "saeit.factory.lifecycle.v1"
MASTER = "saeit.factory.family-master-dashboard.v1"
ORDER_RE = re.compile(r"^WO-[0-9]{8}$")
HEX = re.compile(r"^[a-f0-9]{64}$")
MAX_FINAL = 1000
MAX_TICKETS_PER_CYCLE = 3


def read(path, limit=5_000_000):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise RuntimeError("P0_INVALID_EVIDENCE_FILE:" + path.name)
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise RuntimeError("P0_EVIDENCE_NOT_OBJECT:" + path.name)
    return obj


def directory(path, create=False):
    if path.is_symlink():
        raise RuntimeError("P0_SYMLINK_DIRECTORY")
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(str(path), 0o700)
    if not path.is_dir() or path.is_symlink():
        raise RuntimeError("P0_MISSING_DIRECTORY")


def atomic(path, obj):
    directory(path.parent, True)
    raw = (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    fd, tmp = tempfile.mkstemp(prefix=".p0-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def nonnegative(value, field):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RuntimeError("P0_BAD_COUNT:" + field)
    return value


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def approved_goods(root):
    """Cross-check real immutable packages, final receipts and ten-stage records."""
    folder = root / "product-lifecycle" / "approved-finished-goods"
    directory(folder)
    goods = []
    for entry in sorted(folder.iterdir()):
        if entry.is_symlink() or not entry.is_dir() or not ORDER_RE.fullmatch(entry.name):
            raise RuntimeError("P0_UNSAFE_FINAL_STOCK_ENTRY")
        if len(goods) >= MAX_FINAL:
            raise RuntimeError("P0_FINAL_STOCK_LIMIT")
        order = entry.name
        receipt = read(entry / "receipt.json")
        record = read(root / "product-lifecycle" / "records" / (order + ".json"))
        product = entry / "product.zip"
        if product.is_symlink() or not product.is_file() or not 0 < product.stat().st_size <= 80 * 1024 * 1024:
            raise RuntimeError("P0_MISSING_FINAL_PACKAGE:" + order)
        if (receipt.get("schema") != LIFECYCLE or receipt.get("order") != order
                or receipt.get("stage_gates_passed") != 10
                or receipt.get("distributed") is not False
                or receipt.get("sites_contacted") != 0
                or receipt.get("artifact_sha256") != digest(product)
                or not isinstance(receipt.get("passport_sha256"), str)
                or not HEX.fullmatch(receipt["passport_sha256"])
                or receipt["passport_sha256"] != digest(root / "product-lifecycle" / "passports" / (order + ".json"))
                or record.get("id") != order
                or record.get("status") != "in_finished_goods_warehouse_not_distributed"
                or record.get("final_warehouse_id") != order
                or any(record.get("stage_status", {}).get(str(i)) != "passed" for i in range(1, 11))
                or any(d.get("status") != "resolved" for d in record.get("defects", []))):
            raise RuntimeError("P0_UNVERIFIED_FINAL_STOCK:" + order)
        with zipfile.ZipFile(product) as package:
            if package.testzip() is not None or len(package.namelist()) == 0:
                raise RuntimeError("P0_CORRUPT_ZIP:" + order)
        goods.append({"id": order, "sha256": receipt["artifact_sha256"]})
    return goods


def site_signals(root):
    """Private telemetry is optional, not a claim of site connectivity."""
    sources = root / "p0-improvement" / "site-telemetry"
    out = {}
    for slug in ("zomorodmelal", "mojplaywin"):
        path = sources / (slug + ".json")
        if not path.exists():
            out[slug] = {"status": "unobserved", "verified_new_products": None}
            continue
        obj = read(path, 100_000)
        if (obj.get("schema") != SCHEMA or obj.get("site") != slug
                or obj.get("trusted_collection") is not True):
            out[slug] = {"status": "unverified_telemetry", "verified_new_products": None}
            continue
        # A self-asserted counter never proves a public release or checkout.
        out[slug] = {"status": "telemetry_received_not_independently_verified",
                     "verified_new_products": None}
    return out


def passport_tickets(root, dest):
    """Queue only genuine missing-passport engineering work; cap at three per tick."""
    orders = root / "production-instructions" / "orders"
    directory(orders)
    directory(dest, True)
    created = []
    for file in sorted(orders.iterdir()):
        if len(created) >= MAX_TICKETS_PER_CYCLE:
            break
        if file.is_symlink() or not file.is_file() or not ORDER_RE.fullmatch(file.stem) or file.suffix != ".json":
            raise RuntimeError("P0_INVALID_ORDER_FILE")
        order = read(file, 150_000)
        ident = file.stem
        if order.get("id") != ident or order.get("phase") == "research_rework":
            continue
        if (root / "product-lifecycle" / "passports" / file.name).exists():
            continue
        ticket = dest / ("passport-" + ident + ".json")
        if ticket.exists():
            # Never overwrite an existing rework decision, including symlinks.
            if ticket.is_symlink():
                raise RuntimeError("P0_UNSAFE_TICKET")
            continue
        if not isinstance(order.get("fingerprint"), str) or not HEX.fullmatch(order["fingerprint"]):
            raise RuntimeError("P0_UNTRUSTED_ORDER_FINGERPRINT")
        atomic(ticket, {
            "schema": SCHEMA, "source_order": ident,
            "source_fingerprint": order["fingerprint"],
            "type": "missing_passport",
            "status": "requires_real_engineering_and_independent_review",
            "required_action": "Create a real product passport, prototype, tests, evidence and licensing review for this exact work order",
            "acceptance": ["reproducible source files", "measured functionality",
                           "verified rights and citations", "independent quality review"],
            "automatically_approved": False, "site_transfer_allowed": False,
        })
        created.append(ident)
    return created


def tick(private):
    root = Path(private).expanduser()
    directory(root)
    area = root / "p0-improvement"
    directory(area, True)
    with (area / ".p0.lock").open("a+b") as lock:
        os.chmod(str(area / ".p0.lock"), 0o600)
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status": "already_running"}
        lifecycle = read(root / "product-lifecycle" / "dashboard.json")
        families = read(root / "production-family-management" / "family-dashboard.json")
        stock = read(root / "production-warehouse" / "stock-register.json")
        if (lifecycle.get("schema") != LIFECYCLE or families.get("schema") != MASTER
                or families.get("registered_families") != 40
                or lifecycle.get("site_distribution_enabled") is not False
                or families.get("distribution_enabled") is not False
                or stock.get("sites_contacted") != 0):
            raise RuntimeError("P0_UNTRUSTED_OR_UNSAFE_FACTORY_BASELINE")
        approved = approved_goods(root)
        count = nonnegative(lifecycle.get("final_commercially_verified_stock"), "approved")
        if count != len(approved):
            raise RuntimeError("P0_DASHBOARD_GOODS_DISAGREE")
        technical = nonnegative(stock.get("finished_goods_versions"), "technical")
        defects = nonnegative(lifecycle.get("open_defects"), "defects")
        passports = nonnegative(lifecycle.get("workorder_status", {}).get("awaiting_complete_passport", 0), "passport")
        research = nonnegative(lifecycle.get("research_only_work_orders", 0), "research")
        previous_file = area / "state.json"
        previous = read(previous_file) if previous_file.exists() else None
        if previous is not None and previous.get("schema") != SCHEMA:
            raise RuntimeError("P0_UNKNOWN_PREVIOUS_STATE")
        now_ids = {x["id"] + ":" + x["sha256"] for x in approved}
        before = set(previous.get("verified_goods", [])) if previous else set()
        if any(not isinstance(s, str) or not re.fullmatch(r"WO-[0-9]{8}:[a-f0-9]{64}", s) for s in before):
            raise RuntimeError("P0_INVALID_PREVIOUS_GOODS")
        regressions = sorted(before - now_ids)
        new = sorted(now_ids - before) if previous else []
        defect_regression = bool(previous and defects > previous["open_defects"])
        breaker = bool(regressions or defect_regression)
        created = passport_tickets(root, area / "remediation")
        report = {
            "schema": SCHEMA,
            "evaluated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": "regression_freeze" if breaker else "observing_and_remediating",
            "baseline_established": previous is not None,
            "verified_goods": sorted(now_ids),
            "verified_approved_stock": len(now_ids),
            "new_verified_products_since_last_tick": len(new),
            "new_verified_product_ids": new,
            "lost_or_replaced_approved_goods": regressions,
            "open_defects": defects, "defect_regression": defect_regression,
            "awaiting_real_product_passports": passports,
            "research_only_evidence_orders": research,
            "technical_stock_not_automatically_certified": technical,
            "new_rework_tickets": created,
            "site_telemetry": site_signals(root),
            "measured_product_improvement": bool(new) and not breaker,
            "generation_auto_promotion": False,
            "production_code_self_edit": False,
            "auto_site_publish": False,
            "automatic_quality_approval": False,
            "rollback_or_human_review_required": breaker,
        }
        atomic(area / "state.json", report)
        atomic(area / "last-report.json", report)
        return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-private", required=True)
    args = parser.parse_args()
    report = tick(args.factory_private)
    print("P0_STATUS=" + report["status"])
    print("P0_VERIFIED_FINAL_PRODUCTS=" + str(report.get("verified_approved_stock", 0)))
    print("P0_NEW_VERIFIED_PRODUCTS=" + str(report.get("new_verified_products_since_last_tick", 0)))
    print("P0_NEW_REWORK_TICKETS=" + str(len(report.get("new_rework_tickets", []))))
    print("P0_GENERATION_AUTOPROMOTION=false")
    print("P0_SITE_PUBLICATION=false")


if __name__ == "__main__":
    main()
