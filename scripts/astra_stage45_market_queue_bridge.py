#!/usr/bin/env python3
"""Read-only Astra 0049 queue -> independent market-research *triage* bridge.

Never guesses a historical product's identity from its title, ID or source.
An explicit local sidecar can express a provisional queue/packet association,
but cannot independently attest that association, buyer demand or retail QA.
No database mutations, storefront access, HTTP or payment calls.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile

HERE = Path(__file__).resolve().parent
MAX_PACKET_FILES = 50
MAX_PACKET_BYTES = 200_000
MAX_BINDINGS_BYTES = 80_000
MAX_OUTPUT_BYTES = 4_000_000
QUEUE_KEY = re.compile(r"[A-Za-z0-9_.:-]{1,100}\Z")
PACKET_KEY = re.compile(r"[a-z][a-z0-9_]{2,79}\Z")
FILE_NAME = re.compile(r"[A-Za-z0-9_.-]{1,100}\.json\Z")


def _load_module(name):
    path = HERE / (name + ".py")
    if not path.is_file() or path.is_symlink():
        raise ValueError("missing trusted research module")
    spec = importlib.util.spec_from_file_location("astra_bridge_" + name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_json(path, maximum):
    given = Path(path).expanduser()
    if given.is_symlink() or not given.is_file():
        raise ValueError("invalid or symlinked private JSON source")
    if given.stat().st_size > maximum:
        raise ValueError("research JSON outside size limit")
    return json.loads(given.read_text(encoding="utf-8"))


def _market_packets(folder):
    root = Path(folder).expanduser()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("research directory missing or symlinked")
    entries = sorted(root.iterdir())
    packets = {}
    gate = _load_module("astra_market_readiness_gate")
    count = 0
    for file in entries:
        if file.suffix != ".json":
            continue
        count += 1
        if count > MAX_PACKET_FILES or not FILE_NAME.fullmatch(file.name):
            raise ValueError("too many or invalid packet files")
        packet = _read_json(file, MAX_PACKET_BYTES)
        result = gate.assess(packet)
        key = result["product_key"]
        if key in packets:
            raise ValueError("duplicate market product key")
        if (result["build_authorized"] or result["publish_authorized"]
                or result["payment_authorized"]
                or result["sources_independently_attested"] != 0):
            raise ValueError("market gate violated research-only boundary")
        packets[key] = result
    return packets


def _bindings(file, queue_keys, product_keys):
    if file is None:
        return {}
    document = _read_json(file, MAX_BINDINGS_BYTES)
    if not isinstance(document, dict) or set(document) != {"bindings"}:
        raise ValueError("exact bindings schema required")
    values = document["bindings"]
    if not isinstance(values, list) or len(values) > min(2000, len(queue_keys)):
        raise ValueError("bounded bindings list required")
    mapped = {}
    seen_products = set()
    for binding in values:
        if not isinstance(binding, dict) or set(binding) != {"queue_key", "product_key"}:
            raise ValueError("exact binding fields required")
        q, p = binding["queue_key"], binding["product_key"]
        if (not isinstance(q, str) or not QUEUE_KEY.fullmatch(q)
                or not isinstance(p, str) or not PACKET_KEY.fullmatch(p)):
            raise ValueError("invalid binding identifiers")
        if q not in queue_keys or p not in product_keys:
            raise ValueError("cannot bind unknown queue or market packet")
        if q in mapped or p in seen_products:
            raise ValueError("duplicate or ambiguous market binding")
        mapped[q] = p
        seen_products.add(p)
    return mapped


def evaluate(db, market_dir, now_utc, bindings=None):
    backlog_module = _load_module("astra_stage45_research_backlog")
    queue = backlog_module.analyze(db, now_utc)
    if (queue["factory_mutations"] != 0 or queue["commercially_released_products"] != 0
            or queue["verified_market_demand_topics"] != 0):
        raise ValueError("non-research queue report")
    packets = _market_packets(market_dir)
    rows = queue["backlog"]
    keys = {entry["key"] for entry in rows}
    if len(keys) != len(rows):
        raise ValueError("duplicate queue identity")
    linked = _bindings(bindings, keys, set(packets))
    assigned = set(linked.values())
    work = []
    for item in rows:
        key = item["key"]
        product = linked.get(key)
        market = packets.get(product)
        if (item["build_authorized"] or item["publish_authorized"]
                or item["payment_authorized"]
                or item["market_demand_independently_verified"]):
            raise ValueError("untrusted queue commercial flags")
        extra = market["next_research_actions"] if market else [
            "ESTABLISH_EXPLICIT_REVIEWED_QUEUE_TO_PRODUCT_PROVENANCE",
            "COMPILE_PRODUCT_SPECIFIC_PRIMARY_MARKET_PACKET",
        ]
        actions = list(dict.fromkeys(item["next_research_actions"] + extra))
        work.append({
            "queue_key": key,
            "research_status": "RESEARCH_REQUIRED",
            "market_packet_key": product,
            "market_packet_present": bool(market),
            "linkage_independently_verified": False,
            "queue_preliminary_unique_documents": item["preliminary_unique_references"],
            "market_reference_urls_listed": market["sources_listed"] if market else 0,
            "market_competitors_listed": market["competitors_listed"] if market else 0,
            "independently_attested_market_sources": 0,
            "validated_real_buyer_interviews": 0,
            "commercial_quality_score": None,
            "fair_price_assessed": False,
            "next_research_actions": actions,
            "build_authorized": False,
            "publish_authorized": False,
            "payment_authorized": False,
        })
    return {
        "mode": "private_read_only_0049_queue_market_triage",
        "observed_utc": queue["observed_utc"],
        "queue_items_examined": queue["queue_items_examined"],
        "discovery_topics": len(rows),
        "market_packets_examined": len(packets),
        "explicit_unverified_packet_links": len(linked),
        "unlinked_market_product_keys": sorted(set(packets) - assigned),
        "topics_without_market_packets": len(rows) - len(linked),
        "commercially_qualified_products": 0,
        "unassessed_demand_topics": len(rows),
        "network_requests": 0,
        "factory_mutations": 0,
        "site_mutations": 0,
        "payment_attempts": 0,
        "build_authorized": False,
        "publish_authorized": False,
        "payment_authorized": False,
        "research_queue": work,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="existing 0049 SQLite, read only")
    parser.add_argument("--market-dir", required=True, help="local JSON research packets")
    parser.add_argument("--bindings", help="optional, explicit unverified binding sidecar")
    parser.add_argument("--now-utc", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    dest = Path(args.output).expanduser()
    if (dest.is_symlink() or not dest.parent.is_dir()
            or dest.suffix != ".json"):
        raise ValueError("unsafe triage output")
    target = dest.resolve()
    inputs = [args.db]
    inputs.extend(str(x) for x in Path(args.market_dir).glob("*.json"))
    if args.bindings:
        inputs.append(args.bindings)
    if any(target == Path(p).expanduser().resolve() for p in inputs):
        raise ValueError("cannot overwrite input or database")
    report = evaluate(args.db, args.market_dir, args.now_utc, args.bindings)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if len(payload.encode("utf-8")) > MAX_OUTPUT_BYTES:
        raise ValueError("bounded triage output exceeded")
    fd, scratch = tempfile.mkstemp(prefix=".astra45-triage-", dir=str(dest.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(scratch, 0o600)
        os.replace(scratch, target)
    finally:
        if os.path.exists(scratch):
            os.unlink(scratch)
    print("ASTRA_STAGE45_MARKET_QUEUE_BRIDGE=RESEARCH_ONLY")
    print("ASTRA_STAGE45_MATCHED_UNVERIFIED_LINKS=" +
          str(report["explicit_unverified_packet_links"]))
    print("ASTRA_STAGE45_MARKET_PUBLICATION=false")


if __name__ == "__main__":
    main()
