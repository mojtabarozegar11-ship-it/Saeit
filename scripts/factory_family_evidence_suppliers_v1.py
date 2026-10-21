#!/usr/bin/env python3
"""Build per-family, version-bound evidence supplier intake manifests.

This creates one distinct supplier identity and unlimited append-only evidence
requests per registered production family. It does not fabricate evidence or
claim that a supplier source is connected.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re

SCHEMA = "saeit.factory.family-evidence-suppliers.v1"
FAMILY_SCHEMA = "saeit.factory.family-registry.v1"
HEX = re.compile(r"^[a-f0-9]{64}$")
FAMILY_ID = re.compile(r"^F[0-9]{2}$")
COMMON_EVIDENCE = [
    "exact_version_artifact_and_sha256",
    "automated_test_logs",
    "license_and_provenance",
    "independent_domain_expert_review",
    "critical_defect_zero_review",
]
HUMAN_ONLY_TESTS = {
    "expert_peer_review", "independent_fact_and_clinical_safety_review",
    "blind_independent_player_sessions", "field_check", "full_playthrough",
    "real_gameplay", "full_listening", "classroom_feasibility",
}


def require(condition, code):
    if not condition:
        raise ValueError(code)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def load_json(path):
    p = Path(path)
    require(p.is_file() and not p.is_symlink() and p.stat().st_size <= 10_000_000,
            "FAMILY_SOURCE_UNSAFE")
    value = json.loads(p.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "FAMILY_SOURCE_INVALID")
    return value


def build_supplier_registry(family_catalog):
    profiles = family_catalog.get("profiles")
    require(family_catalog.get("schema") == FAMILY_SCHEMA and isinstance(profiles, list)
            and len(profiles) == 40, "FAMILY_CATALOG_CONTRACT_INVALID")
    expected = ["F%02d" % n for n in range(1, 41)]
    require([p.get("id") for p in profiles] == expected, "FAMILY_CATALOG_IDS_INVALID")
    seen_slugs = set()
    suppliers = []
    for profile in profiles:
        family_id, slug, adapter = profile.get("id"), profile.get("slug"), profile.get("producer_adapter")
        checks = profile.get("specialist_tests")
        require(FAMILY_ID.fullmatch(family_id or "") and isinstance(slug, str)
                and re.fullmatch(r"[a-z][a-z0-9_]{1,63}", slug)
                and slug not in seen_slugs and isinstance(adapter, str)
                and isinstance(checks, list) and checks
                and len(checks) == len(set(checks))
                and all(isinstance(item, str) and re.fullmatch(r"[a-z][a-z0-9_]{1,79}", item)
                        for item in checks), "FAMILY_PROFILE_INVALID")
        seen_slugs.add(slug)
        suppliers.append({
            "supplier_id": "evidence_supplier_" + family_id.lower(),
            "family_id": family_id,
            "family_slug": slug,
            "production_adapter": adapter,
            "supplier_state": "WAITING_FOR_CONNECTED_SOURCES",
            "evidence_request_capacity": "UNBOUNDED_APPEND_ONLY",
            "version_binding_required": True,
            "required_evidence": COMMON_EVIDENCE + checks,
            "independent_human_checks": [item for item in checks if item in HUMAN_ONLY_TESTS],
            "evidence_received_count": 0,
            "evidence_verified_count": 0,
            "release_authorized": False,
        })
    return {
        "schema": SCHEMA,
        "family_catalog_sha256": sha256(json.dumps(
            family_catalog, sort_keys=True, ensure_ascii=False,
            separators=(",", ":")).encode("utf-8")),
        "registered_family_count": len(suppliers),
        "supplier_count": len(suppliers),
        "connected_supplier_count": 0,
        "evidence_fabricated": False,
        "production_release_authorized": False,
        "suppliers": suppliers,
    }


def build_version_intake(registry, family_id, source_sha256, artifact_sha256):
    require(FAMILY_ID.fullmatch(family_id or "") and HEX.fullmatch(source_sha256 or "")
            and HEX.fullmatch(artifact_sha256 or ""), "VERSION_BINDING_INVALID")
    matches = [row for row in registry["suppliers"] if row["family_id"] == family_id]
    require(len(matches) == 1, "FAMILY_SUPPLIER_MISSING_OR_DUPLICATE")
    supplier = matches[0]
    return {
        "schema": "saeit.factory.family-evidence-intake.v1",
        "supplier_id": supplier["supplier_id"],
        "family_id": family_id,
        "family_slug": supplier["family_slug"],
        "source_sha256": source_sha256,
        "artifact_sha256": artifact_sha256,
        "evidence_request_capacity": "UNBOUNDED_APPEND_ONLY",
        "required_evidence": [
            {"evidence_type": item, "state": "MISSING", "items": []}
            for item in supplier["required_evidence"]
        ],
        "received_evidence_count": 0,
        "verified_evidence_count": 0,
        "professional_quality_points": None,
        "release_authorized": False,
    }


def write_new(path, value):
    target = Path(path)
    require(not target.exists() and not target.is_symlink(), "OUTPUT_ALREADY_EXISTS")
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    raw = (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return sha256(raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--families", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--family-id")
    parser.add_argument("--source-sha256")
    parser.add_argument("--artifact-sha256")
    args = parser.parse_args(argv)
    registry = build_supplier_registry(load_json(args.families))
    if args.family_id or args.source_sha256 or args.artifact_sha256:
        require(args.family_id and args.source_sha256 and args.artifact_sha256,
                "VERSION_BINDING_ARGUMENTS_INCOMPLETE")
        result = build_version_intake(registry, args.family_id, args.source_sha256,
                                      args.artifact_sha256)
    else:
        result = registry
    print("FACTORY_FAMILY_SUPPLIERS=" + str(registry["supplier_count"]))
    print("FACTORY_CONNECTED_SUPPLIERS=" + str(registry["connected_supplier_count"]))
    print("FACTORY_EVIDENCE_INVENTED=false")
    print("FACTORY_RELEASE_AUTHORIZED=false")
    print("FACTORY_SUPPLIER_RECEIPT_SHA256=" + write_new(args.output, result))


if __name__ == "__main__":
    main()
