# Work-order IDs and revision filenames remain open-ended for ongoing rework.
#!/usr/bin/env python3
"""Stage 2: independent desk-research intake, source gap remediation and handoff.

Only source-linked, documented desk research advances to stage 3. Missing
evidence remains in *stage 2's own* research queue, never blocking stage 1.
Verified inputs are immutable stage-1 handoff packets, stage-1 hash receipts,
and explicitly curated source-to-claim evidence. This standard-library agent
cannot claim to have fetched web pages, independently tested science, generated
a bilingual manuscript, passed expert review, or certified goods for sale.
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
from urllib.parse import urlsplit
import ipaddress

HANDOFF_SCHEMA = "saeit.factory.stage-handoff.v1"
EVIDENCE_SCHEMA = "saeit.factory.stage2-source-evidence.v1"
RESEARCH_SCHEMA = "saeit.factory.stage2-desk-research.v1"
RETURN_SCHEMA = "saeit.factory.stage-return.v1"
ORDER_ID = re.compile(r"WO-[0-9]+\Z")
INBOX_FILE = re.compile(r"(WO-[0-9]+)--r([0-9]+)\.json\Z")
TOPIC_ID = re.compile(r"AGRI-[0-9]{3}\Z")
HEXDIGEST = re.compile(r"[0-9a-f]{64}\Z")
SOURCE_ID = re.compile(r"[a-z][a-z0-9_-]{1,39}\Z")
LOCALES = {"fa-IR", "en-US"}
MAX_FILE = 300_000


def sha(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode("utf8")).hexdigest()


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def directory(path):
    if path.is_symlink():
        raise RuntimeError("STAGE2_SYMLINK_DIRECTORY")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir() or path.is_symlink():
        raise RuntimeError("STAGE2_UNSAFE_DIRECTORY")
    os.chmod(path, 0o700)


def safe_file(path):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_FILE:
        raise RuntimeError("STAGE2_FILE_UNSAFE:" + path.name)


def read(path):
    safe_file(path)
    value = json.loads(path.read_text(encoding="utf8"))
    if not isinstance(value, dict):
        raise RuntimeError("STAGE2_EXPECTED_JSON_OBJECT")
    return value


def atomic(path, obj):
    directory(path.parent)
    fd, tmp = tempfile.mkstemp(prefix=".stage2-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf8") as out:
            json.dump(obj, out, ensure_ascii=False, indent=2, sort_keys=True)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def record_once(path, value, conflict):
    if path.exists() or path.is_symlink():
        if read(path) != value:
            raise RuntimeError(conflict + ":" + path.name)
        return False
    atomic(path, value)
    return True


def prioritize(packet):
    order = packet.get("work_order")
    if not isinstance(order, dict):
        return (2, 0, packet.get("order_id", ""))
    if (order.get("priority") == "P0"
            and order.get("origin") == "owner_requested_agri200_p0"):
        pos = order.get("priority_rank")
        return (0, pos if type(pos) is int and 1 <= pos <= 200 else 999999,
                packet.get("order_id", ""))
    return (1, 0, packet.get("order_id", ""))


def verified_stage1_packet(area, packet_name):
    match = INBOX_FILE.fullmatch(packet_name)
    if match is None:
        raise RuntimeError("STAGE2_BAD_INBOX_NAME")
    order_id, rev = match.group(1), int(match.group(2))
    packet = read(area / "stage-02" / "inbox" / packet_name)
    proof = read(area / "stage-01" / "receipts" / packet_name)
    order = packet.get("work_order")
    if (packet.get("schema") != HANDOFF_SCHEMA
            or packet.get("order_id") != order_id
            or packet.get("revision") != rev
            or packet.get("previous_stage") != 1
            or packet.get("next_stage") != 2
            or packet.get("public_distribution_allowed") is not False
            or packet.get("commercial_release") is not False
            or not isinstance(order, dict)
            or order.get("id") != order_id
            or packet.get("source_order_sha256") != sha(order)
            or proof.get("schema") != HANDOFF_SCHEMA
            or proof.get("order_id") != order_id
            or proof.get("revision") != rev
            or proof.get("stage_1_completed") is not True
            or proof.get("source_order_sha256") != sha(order)
            or proof.get("stage_2_packet_sha256") != sha(packet)):
        raise RuntimeError("STAGE2_HANDOFF_INTEGRITY_FAILED:" + packet_name)
    return packet, order


def verified_return(area, name):
    """Accept a research-specific return from a later stage, not a fake intake."""
    match = INBOX_FILE.fullmatch(name)
    if match is None or int(match.group(2)) < 2:
        raise RuntimeError("STAGE2_RETURN_FILENAME_INVALID")
    ident, version = match.group(1), int(match.group(2))
    item = read(area / "stage-02" / "return-inbox" / name)
    old_name = ident + "--r" + str(version - 1).zfill(3) + ".json"
    prior = read(area / "stage-02" / "completed-dossiers" / old_name)
    proof = read(area / "stage-02" / "receipts" / old_name)
    if (item.get("schema") != RETURN_SCHEMA
            or item.get("order_id") != ident
            or item.get("revision") != version
            or item.get("target_stage") != 2
            or type(item.get("source_stage")) is not int
            or item["source_stage"] not in range(3, 11)
            or not isinstance(item.get("reason"), str)
            or len(item["reason"].strip()) < 12
            or item.get("previous_research_sha256") != sha(prior)
            or proof.get("stage_2_completed") is not True
            or proof.get("research_sha256") != sha(prior)):
        raise RuntimeError("STAGE2_UNTRUSTED_RETURN")
    base, order = verified_stage1_packet(area, ident + "--r001.json")
    packet = dict(base, revision=version, returned_from_stage=item["source_stage"],
                  stage_1_original_packet_sha256=sha(base),
                  stage_2_return_sha256=sha(item),
                  stage_2_status="returned_for_research_rework")
    return packet, order


def validate_public_https(url):
    if not isinstance(url, str) or len(url) > 400:
        raise ValueError("STAGE2_INVALID_URL")
    parsed = urlsplit(url)
    host = parsed.hostname
    if (parsed.scheme != "https" or not host or parsed.username or parsed.password
            or parsed.port is not None or host in ("localhost", "localhost.localdomain")
            or parsed.fragment or any(c.isspace() for c in url)):
        raise ValueError("STAGE2_NONPUBLIC_SOURCE_URL")
    try:
        ipaddress.ip_address(host)
        raise ValueError("STAGE2_IP_SOURCE_URL_FORBIDDEN")
    except ValueError as exc:
        if str(exc) == "STAGE2_IP_SOURCE_URL_FORBIDDEN":
            raise
    if "." not in host or host.endswith((".internal", ".local", ".test")):
        raise ValueError("STAGE2_INVALID_PUBLIC_HOST")
    return host.lower()


def validate_evidence(evidence, order, revision):
    topic = order.get("source_product_id")
    if (evidence.get("schema") != EVIDENCE_SCHEMA
            or not isinstance(topic, str) or TOPIC_ID.fullmatch(topic) is None
            or evidence.get("source_product_id") != topic
            or evidence.get("revision") != revision
            or evidence.get("work_order_sha256") != sha(order)):
        raise ValueError("STAGE2_EVIDENCE_WRONG_ORDER_OR_REVISION")
    targets = evidence.get("locale_scopes")
    if not isinstance(targets, dict) or set(targets) != LOCALES:
        raise ValueError("STAGE2_MISSING_BILINGUAL_RESEARCH_SCOPE")
    for loc, description in targets.items():
        if not isinstance(description, str) or len(description.strip()) < 50:
            raise ValueError("STAGE2_INSUFFICIENT_LOCAL_RESEARCH:" + loc)
    raw_sources = evidence.get("sources")
    claims = evidence.get("claims")
    if not isinstance(raw_sources, list) or len(raw_sources) < 4 or len(raw_sources) > 16:
        raise ValueError("STAGE2_TOO_FEW_INDEPENDENT_SOURCES")
    if not isinstance(claims, list) or len(claims) < 5 or len(claims) > 60:
        raise ValueError("STAGE2_TOO_FEW_SOURCE_LINKED_CLAIMS")
    by_id = {}
    publishers = set()
    domains = set()
    for item in raw_sources:
        if not isinstance(item, dict):
            raise ValueError("STAGE2_BAD_SOURCE")
        ident, publisher = item.get("id"), item.get("publisher")
        if (not isinstance(ident, str) or not SOURCE_ID.fullmatch(ident)
                or ident in by_id or not isinstance(publisher, str)
                or len(publisher.strip()) < 6 or len(item.get("title", "")) < 15
                or not isinstance(item.get("evidence_note"), str)
                or len(item["evidence_note"].strip()) < 45
                or not re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}",
                                    str(item.get("checked_date", "")))):
            raise ValueError("STAGE2_SOURCE_PROVENANCE_INCOMPLETE")
        domain = validate_public_https(item.get("url"))
        by_id[ident] = item
        publishers.add(publisher.casefold().strip())
        domains.add(domain.removeprefix("www."))
    if len(publishers) < 3 or len(domains) < 3:
        raise ValueError("STAGE2_SOURCES_NOT_INDEPENDENT")
    used_sources = set()
    seen_claims = set()
    for item in claims:
        if not isinstance(item, dict):
            raise ValueError("STAGE2_BAD_CLAIM")
        ident, claim = item.get("id"), item.get("statement")
        support = item.get("source_ids")
        if (not isinstance(ident, str) or not SOURCE_ID.fullmatch(ident)
                or ident in seen_claims or not isinstance(claim, str)
                or len(claim.strip()) < 35
                or not isinstance(support, list) or not 1 <= len(support) <= 5
                or not all(isinstance(s, str) and s in by_id for s in support)):
            raise ValueError("STAGE2_UNTRACEABLE_CLAIM")
        seen_claims.add(ident)
        used_sources.update(support)
    if len(used_sources) < 4:
        raise ValueError("STAGE2_SOURCES_NOT_LINKED_TO_CLAIMS")
    if evidence.get("scientific_review_completed") is not False:
        raise ValueError("STAGE2_CANNOT_FAKE_SCIENTIFIC_REVIEW")
    if evidence.get("public_distribution_allowed") is not False:
        raise ValueError("STAGE2_CANNOT_PUBLISH")
    return {"claim_count": len(claims), "source_count": len(raw_sources),
            "publisher_count": len(publishers),
            "locale_count": len(targets), "source_ids": sorted(used_sources)}


def briefing(order, packet, reason):
    topic = order.get("source_product_id")
    editions = order.get("editions", [])
    localized = []
    if isinstance(editions, list):
        for value in editions:
            if isinstance(value, dict) and value.get("locale") in LOCALES:
                localized.append({
                    "locale": value["locale"],
                    "target_audience": value.get("audience"),
                    "local_title": value.get("title")
                })
    return {
        "schema": RESEARCH_SCHEMA, "order_id": packet["order_id"],
        "source_product_id": topic, "revision": packet["revision"],
        "status": "requires_verified_sources_in_stage2",
        "missing": reason, "stage_1_complete": True,
        "stage_2_research_completed": False, "stage_3_handoff": False,
        "research_workplan": [
            "Find a minimum of four relevant citable pages from at least three independent publishers.",
            "Document at least five specific, source-linked scientific or extension claims and inspect original context.",
            "Separately describe practical conditions, cautions and climate/units for fa-IR and en-US audiences.",
            "Flag unsupported assertions and safety-sensitive recommendations for real specialist verification.",
            "Submit source-to-claim bundle under stage-02/source-evidence; rerun worker to produce stage 3 receipt."
        ],
        "localized_research_scopes": localized,
        "rights_and_safety_notes": "Do not reproduce long copyrighted excerpts or prescribe regionally unapproved pesticides.",
        "scientific_review_approved": False, "commercial_release": False,
        "public_distribution_allowed": False
    }


def write_brief(area, packet, order, reason):
    path = area / "stage-02" / "research-needed" / (
        packet["order_id"] + "--r" + str(packet["revision"]).zfill(3) + ".json")
    b = briefing(order, packet, reason)
    if path.exists() and read(path) == b:
        return False
    atomic(path, b)
    return True


def research_output(packet, order, evidence, metrics):
    return {
        "schema": RESEARCH_SCHEMA, "stage": 2, "source_product_id": order["source_product_id"],
        "order_id": packet["order_id"], "revision": packet["revision"],
        "stage_1_handoff_sha256": packet.get("stage_1_original_packet_sha256", sha(packet)),
        "evidence_sha256": sha(evidence),
        "desk_research_status": "source_linked_desk_research_documented",
        "scope_note": "Documents research sources and claims; NOT a finished manuscript or independent expert attestation.",
        "locale_scopes": evidence["locale_scopes"],
        "sources": evidence["sources"], "claims": evidence["claims"],
        "quantitative_provenance_checks": metrics,
        "external_source_live_recheck": False,
        "independent_scientific_review": False,
        "stage2_documentation_complete": True,
        "manuscript_created": False, "quality1000_approved": False,
        "commercial_release": False, "public_distribution_allowed": False
    }


def write_completed(area, packet, order, evidence, metrics):
    name = packet["order_id"] + "--r" + str(packet["revision"]).zfill(3) + ".json"
    research = research_output(packet, order, evidence, metrics)
    output = area / "stage-02" / "completed-dossiers" / name
    record_once(output, research, "STAGE2_EXISTING_RESEARCH_CONFLICT")
    to_stage3 = {
        "schema": HANDOFF_SCHEMA, "order_id": packet["order_id"],
        "revision": packet["revision"], "previous_stage": 2,
        "next_stage": 3, "desk_research_sha256": sha(research),
        "desk_research_file": name, "stage_3_status": "received_pending_design",
        "source_to_claim_linkage_checked": True,
        "independent_source_facts_rechecked": False,
        "independent_expert_review": False, "quality1000_approved": False,
        "commercial_release": False, "public_distribution_allowed": False
    }
    next_file = area / "stage-03" / "inbox" / name
    created = record_once(next_file, to_stage3, "STAGE2_STAGE3_HANDOFF_CONFLICT")
    receipt = {
        "schema": HANDOFF_SCHEMA, "order_id": packet["order_id"],
        "revision": packet["revision"], "stage_2_completed": True,
        "stage_3_inbox_file": name,
        "research_sha256": sha(research),
        "stage_3_packet_sha256": sha(to_stage3),
        "scientific_review_completed": False, "quality1000_approved": False
    }
    record_once(area / "stage-02" / "receipts" / name, receipt,
                "STAGE2_RECEIPT_CONFLICT")
    return created


def safe_catalog_seed(root, bundle_file):
    doc = read(bundle_file)
    bundles = doc.get("bundles")
    if (doc.get("schema") != EVIDENCE_SCHEMA
            or not isinstance(bundles, list) or not 1 <= len(bundles) <= 200):
        raise RuntimeError("STAGE2_BAD_SOURCE_CATALOG")
    area = root / "production-instructions"
    index = read(area / "owner-agri200-p0-index.json")
    ids = index.get("order_ids_ranked", [])
    if len(ids) != 200:
        raise RuntimeError("STAGE2_P0_INDEX_INVALID")
    count = 0
    seen = set()
    for bundle in bundles:
        topic = bundle.get("source_product_id")
        if not isinstance(topic, str) or not TOPIC_ID.fullmatch(topic) or topic in seen:
            raise RuntimeError("STAGE2_DUPLICATE_BUNDLE")
        seen.add(topic)
        order_id = ids[int(topic.rsplit("-", 1)[1]) - 1]
        first, order = verified_stage1_packet(area, order_id + "--r001.json")
        prepared = dict(bundle, work_order_sha256=sha(order))
        validate_evidence(prepared, order, 1)
        src = area / "stage-02" / "source-evidence" / (topic + "--r001.json")
        if record_once(src, prepared, "STAGE2_EXISTING_EVIDENCE_CONFLICT"):
            count += 1
    return count


def stage2_loop(root, batch=100, only_order_id=None, excluded_orders=None):
    if only_order_id is not None and (not isinstance(only_order_id, str)
                                   or re.fullmatch(r"WO-[0-9]{8}", only_order_id) is None):
        raise ValueError("STAGE2_TARGET_ORDER_INVALID")
    if excluded_orders is not None and (not isinstance(excluded_orders, set)
                                        or any(not ORDER_ID.fullmatch(x) for x in excluded_orders)):
        raise ValueError("STAGE2_EXCLUSION_INVALID")
    root = Path(root).expanduser().resolve()
    area = root / "production-instructions"
    inbox = area / "stage-02" / "inbox"
    if not root.is_dir() or not inbox.is_dir() or inbox.is_symlink():
        raise RuntimeError("STAGE2_INBOX_MISSING")
    lock = area / "stage-02" / ".worker.lock"
    if lock.is_symlink():
        raise RuntimeError("STAGE2_UNSAFE_LOCK")
    with lock.open("a+b") as locked:
        os.chmod(lock, 0o600)
        fcntl.flock(locked.fileno(), fcntl.LOCK_EX)
        candidates = []
        for file in inbox.iterdir():
            if file.is_symlink() or not file.is_file() or INBOX_FILE.fullmatch(file.name) is None:
                raise RuntimeError("STAGE2_UNEXPECTED_INBOX_FILE:" + file.name)
            packet = read(file)
            candidates.append((prioritize(packet), 1, file.name, packet))
        returns = area / "stage-02" / "return-inbox"
        directory(returns)
        for file in returns.iterdir():
            if file.is_symlink() or not file.is_file() or INBOX_FILE.fullmatch(file.name) is None:
                raise RuntimeError("STAGE2_UNEXPECTED_RETURN_FILE:" + file.name)
            # Verify each return before ranking it; no unsourced return can override
            # original source order or bypass proven stage-2 research.
            packet, order = verified_return(area, file.name)
            candidates.append((prioritize(packet), 0, file.name, packet))
        candidates.sort(key=lambda x: (x[0][0], x[1], x[0][1], x[0][2]))
        if only_order_id is not None:
            candidates = [x for x in candidates if x[2].split("--r", 1)[0] == only_order_id]
        if excluded_orders:
            candidates = [x for x in candidates if x[2].split("--r", 1)[0] not in excluded_orders]

        total = len(candidates)
        completed = 0
        already = 0
        missing = 0
        invalid = 0
        attempted = 0
        for _priority, is_new, name, packet in candidates:
            if attempted >= batch:
                break
            key = name
            already_path = area / "stage-02" / "receipts" / key
            if already_path.exists():
                # Read and verify the durable receipt; do not simply trust existence.
                proof = read(already_path)
                if proof.get("schema") != HANDOFF_SCHEMA or proof.get("stage_2_completed") is not True:
                    raise RuntimeError("STAGE2_INVALID_EXISTING_RECEIPT:" + key)
                already += 1
                continue
            result_path = area / "stage-02" / "research-needed" / key
            evidence_file = area / "stage-02" / "source-evidence" / (
                str(packet.get("work_order", {}).get("source_product_id", "none")) +
                "--r" + str(packet.get("revision", 0)).zfill(3) + ".json")
            if result_path.exists() and not evidence_file.exists():
                already += 1
                continue
            attempted += 1
            try:
                packet, order = (verified_stage1_packet(area, name) if is_new == 1
                                 else verified_return(area, name))
                if not evidence_file.is_file():
                    if write_brief(area, packet, order, "INDEPENDENT_SOURCE_EVIDENCE_NOT_SUPPLIED"):
                        missing += 1
                    continue
                evidence = read(evidence_file)
                metrics = validate_evidence(evidence, order, packet["revision"])
                if write_completed(area, packet, order, evidence, metrics):
                    completed += 1
            except (RuntimeError, ValueError, OSError, TypeError) as exc:
                # Research or invalid inputs remain stage-2 responsibility.
                # Bad stage-1 packets cannot be silently promoted.
                if (isinstance(packet, dict) and isinstance(packet.get("work_order"), dict)
                        and isinstance(packet.get("order_id"), str)):
                    write_brief(area, packet, packet["work_order"],
                                type(exc).__name__ + ":" + str(exc)[:150])
                invalid += 1
        counters = {
            "schema": RESEARCH_SCHEMA, "stage": 2, "input_packet_count": total,
            "newly_completed_research_dossiers": completed,
            "newly_documented_missing_sources": missing,
            "blocked_invalid_inputs": invalid,
            "previously_handled": already,
            "scanned_new_or_changed_this_run": attempted,
            "stage_3_handoffs_total": len(list((area/"stage-02"/"receipts").glob("WO-*.json"))),
            "stage_2_research_briefs_total": len(list((area/"stage-02"/"research-needed").glob("WO-*.json"))),
            "scientific_review_independently_verified": False,
            "sites_modified": False, "quality1000_certified": 0, "checked_utc": utc()
        }
        atomic(area / "stage-02" / "status.json", counters)
        return counters


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-private", required=True)
    parser.add_argument("--seed-research")
    parser.add_argument("--batch", type=int, default=100)
    parser.add_argument("--only-order-id")
    parser.add_argument("--exclude-owner-agri200", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.batch <= 2000:
        raise ValueError("STAGE2_INVALID_BATCH")
    root = Path(args.factory_private)
    if args.seed_research:
        stage2 = root / "production-instructions" / "stage-02"
        directory(stage2)
        mutex = stage2 / ".worker.lock"
        with mutex.open("a+b") as locked:
            os.chmod(mutex, 0o600)
            fcntl.flock(locked.fileno(), fcntl.LOCK_EX)
            print("FACTORY_STAGE2_CURATED_EVIDENCE_INSTALLED=" +
                  str(safe_catalog_seed(root, Path(args.seed_research))))
    if args.only_order_id and args.exclude_owner_agri200:
        raise ValueError("STAGE2_CONFLICTING_SCOPE")
    if args.exclude_owner_agri200:
        from factory_strict_serial_scope_v1 import owner_agri200_ids
        excluded = owner_agri200_ids(root)
    else:
        excluded = None
    result = stage2_loop(root, args.batch, only_order_id=args.only_order_id,
                         excluded_orders=excluded)
    print("FACTORY_STAGE2_RESEARCH_DOSSIERS_NEW=" +
          str(result["newly_completed_research_dossiers"]))
    print("FACTORY_STAGE2_NEEDS_SOURCES_NEW=" +
          str(result["newly_documented_missing_sources"]))
    print("FACTORY_STAGE2_DOSSIERS_TOTAL=" +
          str(result["stage_3_handoffs_total"]))
    print("FACTORY_STAGE2_RESEARCH_REQUIRED_TOTAL=" +
          str(result["stage_2_research_briefs_total"]))
    print("FACTORY_STAGE2_INDEPENDENT_SCIENTIFIC_REVIEW=false")
    print("FACTORY_STAGE2_WEBSITES_MODIFIED=false")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("FACTORY_STAGE2_FATAL=" + type(exc).__name__ + ":" + str(exc)[:220],
              file=sys.stderr)
        raise SystemExit(1)
