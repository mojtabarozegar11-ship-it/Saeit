#!/usr/bin/env python3
"""Real bounded self-repair cycles with independent machine reinspection receipts.

Consumes the existing 40-family QA workorders and native source-backed builder.
Technical evidence is verified on the *new* private candidate; no human/legal
signature, claimed independent certification, gate bypass or site publication.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import zipfile
def active_product_allowlist(path):
    """Read the authoritative single active line or the legacy five-slot set."""
    state_path = Path(path)
    if state_path.is_symlink() or not state_path.is_file() or state_path.stat().st_size > 2000000:
        raise ValueError("ACTIVE_PRODUCT_SLOTS_REQUIRED")
    state = json.loads(state_path.read_text(encoding="utf8"))
    if not isinstance(state, dict):
        raise ValueError("ACTIVE_PRODUCT_SLOTS_SCHEMA_INVALID")
    active = state.get("active")
    capacity = state.get("capacity")
    if (state.get("schema") != "saeit.factory.product-slots.v1"
            or type(capacity) is not int or capacity not in (1, 5)
            or not isinstance(active, list) or len(active) != capacity):
        raise ValueError("ACTIVE_PRODUCT_SLOT_CAPACITY_MISMATCH")
    recipes = [item.get("recipe") if isinstance(item, dict) else None for item in active]
    if (len(set(recipes)) != capacity or any(not isinstance(recipe, str)
            or not re.fullmatch(r"[a-z][a-z0-9_]{1,65}", recipe) for recipe in recipes)):
        raise ValueError("ACTIVE_PRODUCT_SLOT_ENTRIES_INVALID")
    return set(recipes)


SCHEMA = "saeit.factory.autonomous-jump-repair.v1"
HEX = re.compile(r"^[0-9a-f]{64}$")
RECIPE = re.compile(r"^[a-z][a-z0-9_]{1,65}$")


def require(condition, code):
    if not condition:
        raise ValueError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and
            0 < path.stat().st_size <= 2_000_000, "UNSAFE_REPAIR_EVIDENCE")
    data = json.loads(path.read_text(encoding="utf8"))
    require(isinstance(data, dict), "REPAIR_EVIDENCE_NOT_OBJECT")
    return data


def load_bridge(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "PINNED_BRIDGE_REQUIRED")
    spec = importlib.util.spec_from_file_location("factory_jump_verified_bridge", str(path))
    require(spec is not None and spec.loader is not None, "BRIDGE_IMPORT_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def families(path):
    data = read(path)
    profiles = data.get("profiles")
    require(data.get("schema") == "saeit.factory.family-registry.v1"
            and isinstance(profiles, list) and len(profiles) == 40
            and [item.get("id") for item in profiles] ==
                ["F%02d" % n for n in range(1, 41)],
            "FORTY_REGISTERED_FAMILIES_REQUIRED")
    return {item["id"] for item in profiles}


def validate_zip(path, expected):
    require(path.is_file() and not path.is_symlink()
            and 0 < path.stat().st_size <= 25 * 1024 * 1024,
            "CANDIDATE_ARCHIVE_INVALID")
    require(HEX.fullmatch(str(expected)) and sha(path.read_bytes()) == expected,
            "CANDIDATE_ARTIFACT_HASH_MISMATCH")
    with zipfile.ZipFile(path) as bundle:
        members = bundle.infolist()
        require(0 < len(members) <= 256
                and sum(member.file_size for member in members) <= 100 * 1024 * 1024
                and bundle.testzip() is None, "CANDIDATE_ZIP_CRC_INVALID")
        names = set()
        for item in members:
            parts = item.filename.split("/")
            require(not item.is_dir() and not (item.flag_bits & 1)
                    and not stat.S_ISLNK(item.external_attr >> 16)
                    and not item.filename.startswith("/")
                    and "\\" not in item.filename
                    and all(part not in ("", ".", "..") for part in parts)
                    and item.filename not in names, "CANDIDATE_ZIP_MEMBER_UNSAFE")
            names.add(item.filename)
    return len(names)


def immutable_receipt(root, product, record):
    folder = root / "quality-excellence" / "autonomous-repair-verifications" / product
    require(not folder.is_symlink() and not folder.parent.is_symlink(),
            "REPAIR_RECEIPT_DIRECTORY_UNSAFE")
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    raw = (json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) +
           "\n").encode("utf8")
    digest = sha(raw)
    target = folder / ("candidate-" + digest + ".json")
    require(not target.is_symlink(), "REPAIR_RECEIPT_SYMLINK")
    if target.exists():
        require(target.read_bytes() == raw, "REPAIR_RECEIPT_IMMUTABILITY_CONFLICT")
    else:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(str(target), flags, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    require(target.read_bytes() == raw, "REPAIR_RECEIPT_READBACK_FAILED")
    return digest


def reinspect(root, valid_families, active_products=None):
    """Only native receipts for CURRENT still-open quality orders are eligible."""
    base = root / "quality-excellence"
    orders = base / "production-workorders"
    repairs = base / "native-rebuild-receipts"
    output = base / "rebuilt-technical-candidates"
    require(orders.is_dir() and not orders.is_symlink(), "REAL_REWORK_ORDERS_REQUIRED")
    details = {"workorders_checked": 0, "machine_candidates_reverified": 0,
               "genuinely_changed_candidates": 0, "queued_for_independent_reinspection": 0,
               "family_provenance_pending": 0, "invalid_candidate_receipts": 0,
               "superseded_candidates": 0, "family_ids_with_verified_candidates": []}
    used = set()
    for folder in sorted(orders.iterdir()):
        if not folder.is_dir() or folder.is_symlink() or not RECIPE.fullmatch(folder.name):
            continue
        product = folder.name
        if active_products is not None and product not in active_products:
            continue
        order_path = folder / "current.json"
        if not order_path.is_file() or order_path.is_symlink():
            continue
        order = read(order_path)
        if order.get("schema") != "saeit.factory.production-rework-order.v1" or order.get("recipe") != product:
            continue
        details["workorders_checked"] += 1
        digest = order.get("source_quality_receipt_sha256")
        if not HEX.fullmatch(str(digest)):
            continue
        qa = base / "rework" / product / "current.json"
        if (not qa.is_file() or qa.is_symlink() or sha(qa.read_bytes()) != digest
                or read(qa).get("artifact_sha256") != order.get("artifact_sha256")):
            continue
        receipt_dir = repairs / product
        if not receipt_dir.exists():
            continue
        require(receipt_dir.is_dir() and not receipt_dir.is_symlink(),
                "UNSAFE_NATIVE_RECEIPT_DIRECTORY")
        original = root / "digital-products" / product / "manufacturing_manifest.json"
        family = None
        if original.is_file() and not original.is_symlink():
            family = read(original).get("family_id")
        for marker in sorted(receipt_dir.glob("source-*.json")):
            try:
                receipt = read(marker)
                if receipt.get("source_order_sha256") != digest:
                    details["superseded_candidates"] += 1
                    continue
                require(receipt.get("schema") ==
                        "saeit.factory.qa-native-rebuild-bridge.v1"
                        and receipt.get("recipe") == product
                        and receipt.get("status") == "technical_candidate_verified"
                        and receipt.get("independent_quality_1000_passed") is False
                        and receipt.get("commercial_release_authorized") is False
                        and receipt.get("original_stock_mutated") is False,
                        "NATIVE_RECEIPT_UNTRUSTED")
                source_hash = receipt.get("source_sha256")
                expected = receipt.get("artifact_sha256")
                require(HEX.fullmatch(str(source_hash)) and HEX.fullmatch(str(expected)),
                        "NATIVE_RECEIPT_HASH_INVALID")
                basis = sha((product + source_hash + digest).encode("utf8"))
                require(marker.name == "source-" + basis[:24] + ".json",
                        "NATIVE_RECEIPT_IDENTITY_INVALID")
                candidate = output / product
                require(candidate.is_dir() and not candidate.is_symlink(),
                        "PRIVATE_CANDIDATE_MISSING")
                meta_path = candidate / "manufacturing_manifest.json"
                meta = read(meta_path)
                # An older immutable receipt is historical, not a corrupt
                # current candidate: retain it without invalidating this run.
                if meta.get("artifact_sha256") != expected:
                    details["superseded_candidates"] += 1
                    continue
                require(meta.get("recipe") == product
                        and meta.get("qa_status") == "passed"
                        and meta.get("source_sha256") == source_hash
                        and meta.get("professional_quality_approved") is False
                        and meta.get("public_listing_enabled") is False
                        and meta.get("owner_publication_approval") is False,
                        "PRIVATE_CANDIDATE_MANIFEST_INVALID")
                member_count = validate_zip(candidate / (product + "-internal-qa.zip"),
                                            expected)
                changed = expected != order.get("artifact_sha256")
                classified = family if family in valid_families else None
                record = {"schema": SCHEMA, "recipe": product,
                          "family_id": classified, "family_provenance_verified": bool(classified),
                          "source_quality_receipt_sha256": digest,
                          "original_assessed_artifact_sha256": order.get("artifact_sha256"),
                          "candidate_source_sha256": source_hash,
                          "candidate_artifact_sha256": expected,
                          "candidate_manifest_sha256": sha(meta_path.read_bytes()),
                          "native_rebuild_receipt_sha256": sha(marker.read_bytes()),
                          "zip_member_crc_verified": True, "zip_members_checked": member_count,
                          "private_tested_technical_candidate": True,
                          "genuinely_changed_artifact": changed,
                          "queued_for_independent_reinspection": bool(changed and classified),
                          "quality_defect_closed": False,
                          "professional_quality_1000_certified": False,
                          "external_independent_assessment_claimed": False,
                          "owner_signature_claimed": False,
                          "commercial_release_allowed": False, "original_stock_mutated": False}
                immutable_receipt(root, product, record)
                details["machine_candidates_reverified"] += 1
                if changed:
                    details["genuinely_changed_candidates"] += 1
                if not classified:
                    details["family_provenance_pending"] += 1
                if changed and classified:
                    details["queued_for_independent_reinspection"] += 1
                    used.add(classified)
            except (OSError, ValueError, RuntimeError, KeyError, TypeError,
                    zipfile.BadZipFile, EOFError, json.JSONDecodeError):
                details["invalid_candidate_receipts"] += 1
    details["family_ids_with_verified_candidates"] = sorted(used)
    return details


def run(root, registry, source_root, maker, bridge, *, limit=3, rounds=2,
        additional_source_roots=(), products_file=None):
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), "PRIVATE_FACTORY_ROOT_REQUIRED")
    valid_families = families(registry)
    active_products = active_product_allowlist(products_file) if products_file else None
    require(type(limit) is int and 1 <= limit <= 3
            and type(rounds) is int and 1 <= rounds <= 2, "BOUNDED_REPAIR_CAP_REQUIRED")
    require((root / "quality-excellence").is_dir(), "QUALITY_EXCELLENCE_ROOT_REQUIRED")
    lock_path = root / "quality-excellence" / ".autonomous-jump-repair.lock"
    require(not lock_path.is_symlink(), "AUTONOMOUS_REPAIR_LOCK_UNSAFE")
    module = load_bridge(bridge)
    with lock_path.open("a+b") as handle:
        os.fchmod(handle.fileno(), 0o600)
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("AUTONOMOUS_REPAIR_ALREADY_RUNNING")
        completed = []
        for _ in range(rounds):
            bridge_options = {"limit": limit,
                              "additional_source_roots": additional_source_roots}
            if products_file:
                bridge_options["products_file"] = products_file
            result = module.execute(root, source_root, maker, **bridge_options)
            require(isinstance(result, dict)
                    and result.get("professional_quality_1000_verified") is False
                    and result.get("commercial_release_authorized") is False,
                    "NATIVE_BRIDGE_AUTHORITY_BREACH")
            completed.append(result)
            if result.get("rebuild_attempted") == 0:
                break
        audit = reinspect(root, valid_families, active_products)
        status = {"schema": SCHEMA, "registered_family_lines": len(valid_families),
                  "repair_rounds_executed": len(completed),
                  "rebuild_attempted": sum(row.get("rebuild_attempted", 0) for row in completed),
                  "technical_candidates_built": sum(row.get("technical_candidates_verified", 0)
                                                    for row in completed),
                  "rebuild_failures": sum(row.get("failed", 0) for row in completed),
                  "repair_cap_per_round": limit, "repair_round_limit": rounds,
                  **audit, "quality_1000_certifications": 0, "human_signatures_forged": 0,
                  "publications_authorized": 0, "release_gate_modified": False}
        print("FACTORY_AUTONOMOUS_JUMP_REPAIR=" + json.dumps(status, sort_keys=True))
        return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("private-root", "families", "source-root", "maker", "bridge"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--additional-source-root", action="append", default=[])
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--products-file", default=None)
    args = parser.parse_args()
    result = run(args.private_root, args.families, args.source_root, args.maker,
                 args.bridge, limit=args.limit, rounds=args.rounds,
                 additional_source_roots=args.additional_source_root,
                 products_file=args.products_file)
    if result["invalid_candidate_receipts"]:
        raise SystemExit("AUTONOMOUS_REPAIR_UNVERIFIED_CANDIDATES")


if __name__ == "__main__":
    main()
