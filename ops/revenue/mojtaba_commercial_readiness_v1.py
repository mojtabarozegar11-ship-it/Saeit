#!/usr/bin/env python3
"""Commercial offer registry & approval gates for the one canonical Mojtaba.bot.ai.
Source-only assessment; never creates a customer, invoice, transfer, sale, or bot.
"""
from __future__ import annotations

import argparse
import json
import re
import stat
from pathlib import Path

CANONICAL_BOT = "mojtaba.bot.ai"
SCHEMA = "mojtaba.bot.ai.commercial-offer-registry.v1"
MODELS = frozenset({
    "consulting_quote", "b2b_quote", "physical_catalogue",
    "digital_license", "game_license", "subscription", "free_acquisition"
})
STAGES = frozenset({"inquiry_candidate", "release_blocked", "free_acquisition"})
BANDS = frozenset({1, 2, 3, 4})
PUBLIC_HOSTS = frozenset({"zomorodmelal.ir", "mojplaywin.com", "mojtaba.bot.ai"})
FIELDS = frozenset({
    "offer_id", "title", "buyer", "value_proposition", "model", "stage",
    "channel", "source_files", "intake_path", "required_inputs", "deliverables",
    "exclusions", "priority_band", "canonical_bot_id", "price_irr",
    "payment_enabled", "public_live_verified", "delivery_verified",
    "owner_approved"
})
ID_RE = re.compile(r"^[a-z][a-z0-9_]{4,45}$")
RELPATH_RE = re.compile(r"^[A-Za-z0-9_./-]+$")


class ContractError(ValueError):
    pass


def unique_keys(pairs):
    output = {}
    for key, value in pairs:
        if key in output:
            raise ContractError("duplicate_json_key")
        output[key] = value
    return output


def read_registry(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
    if not isinstance(data, dict):
        raise ContractError("registry_not_object")
    return data


def exists_regular_inside(root: Path, rel: str) -> bool:
    if not isinstance(rel, str) or not RELPATH_RE.fullmatch(rel):
        return False
    p = Path(rel)
    if p.is_absolute() or not p.parts or "." in p.parts or ".." in p.parts:
        return False
    curr = root
    for component in p.parts:
        curr = curr / component
        try:
            mode = curr.lstat().st_mode
        except OSError:
            return False
        if stat.S_ISLNK(mode):
            return False
    return stat.S_ISREG(mode)


def clean_list(values, *, minimum=1, maximum=12) -> bool:
    return (isinstance(values, list) and minimum <= len(values) <= maximum
            and all(isinstance(s, str) and 5 <= len(s.strip()) <= 200
                    and "\n" not in s for s in values)
            and len(values) == len(set(values)))


def check_offer(offer: dict, root: Path) -> dict:
    if not isinstance(offer, dict) or set(offer) != FIELDS:
        raise ContractError("offer_contract_fields")
    ident = offer["offer_id"]
    if not isinstance(ident, str) or not ID_RE.fullmatch(ident):
        raise ContractError("invalid_offer_id")
    if offer["canonical_bot_id"] != CANONICAL_BOT:
        raise ContractError("noncanonical_bot")
    if offer["model"] not in MODELS or offer["stage"] not in STAGES:
        raise ContractError("invalid_business_model")
    if type(offer["priority_band"]) is not int or offer["priority_band"] not in BANDS:
        raise ContractError("invalid_priority")
    for key in ("title", "buyer", "value_proposition", "channel"):
        if not isinstance(offer[key], str) or not (6 <= len(offer[key].strip()) <= 220):
            raise ContractError("bad_offer_text_" + key)
    if not clean_list(offer["required_inputs"], minimum=2):
        raise ContractError("missing_buyer_qualification_fields")
    if not clean_list(offer["deliverables"], minimum=2):
        raise ContractError("missing_buyer_deliverables")
    if not clean_list(offer["exclusions"]):
        raise ContractError("missing_scope_exclusions")
    if not clean_list(offer["source_files"], maximum=5):
        raise ContractError("missing_source_provenance")
    if not all(exists_regular_inside(root, f) for f in offer["source_files"]):
        raise ContractError("unverifiable_source_file")
    route = offer["intake_path"]
    if not isinstance(route, str) or not route.startswith("/") or route.startswith("//"):
        raise ContractError("intake_path_not_local")
    if len(route) > 120 or any(x in route for x in ("#", "\\", "\r", "\n", "..")):
        raise ContractError("unsafe_intake_path")
    if offer["price_irr"] is not None:
        raise ContractError("price_not_owner_approved")
    for flag in ("payment_enabled", "public_live_verified", "delivery_verified", "owner_approved"):
        if offer[flag] is not False:
            raise ContractError("unverified_commercial_state_" + flag)
    if offer["stage"] == "free_acquisition" and offer["model"] != "free_acquisition":
        raise ContractError("free_stage_mismatch")
    if offer["model"] == "free_acquisition" and offer["stage"] != "free_acquisition":
        raise ContractError("free_model_mismatch")
    if offer["stage"] == "inquiry_candidate" and offer["model"] not in (
        "consulting_quote", "b2b_quote", "physical_catalogue"
    ):
        raise ContractError("automated_purchase_not_allowed")
    return {
        "id": ident,
        "model": offer["model"],
        "stage": offer["stage"],
        "priority_band": offer["priority_band"],
        "source_file_count": len(offer["source_files"]),
        "source_verified_in_repository": True,
        "buyer_qualification_defined": True,
        "deliverable_scope_defined": True,
        "commercial_release_authorized": False,
        "payment_available_verified": False,
        "live_lead_capture_verified": False,
        "customer_receipt_verified": False,
        "purchase_allowed": False,
    }


def assess(root: Path, registry: dict) -> dict:
    if not isinstance(registry, dict) or set(registry) != {"schema", "canonical_bot_id", "offers"}:
        raise ContractError("registry_schema_fields")
    if registry["schema"] != SCHEMA or registry["canonical_bot_id"] != CANONICAL_BOT:
        raise ContractError("registry_not_single_bot")
    offers = registry["offers"]
    if not isinstance(offers, list) or not 8 <= len(offers) <= 30:
        raise ContractError("offer_count_out_of_bounds")
    checked = [check_offer(x, root) for x in offers]
    ids = [item["id"] for item in checked]
    if len(ids) != len(set(ids)):
        raise ContractError("duplicate_offer_id")
    # Only source-level capability. No claim about public availability or revenue.
    source_prepared = sum(x["source_verified_in_repository"] for x in checked)
    inquiry_candidates = sum(x["stage"] == "inquiry_candidate" for x in checked)
    free_count = sum(x["stage"] == "free_acquisition" for x in checked)
    blocked = sum(x["stage"] == "release_blocked" for x in checked)
    ordered = sorted(checked, key=lambda x: (x["priority_band"], x["id"]))
    return {
        "schema": "mojtaba.bot.ai.commercial-readiness-report.v1",
        "canonical_bot_id": CANONICAL_BOT,
        "scope": "offline_repository_source_only_no_live_sales",
        "offer_count": len(checked),
        "repository_source_verified_count": source_prepared,
        "inquiry_candidates_source_only": inquiry_candidates,
        "free_acquisition_candidates_source_only": free_count,
        "release_blocked_offers": blocked,
        "commercial_releases_authorized_count": 0,
        "purchases_verified_count": None,
        "leads_verified_count": None,
        "revenue_received_irr": None,
        "customer_messages_sent": 0,
        "orders_created": 0,
        "transactions_created": 0,
        "cost_committed_irr": 0,
        "production_files_changed": 0,
        "priority_queue": [
            {"id": x["id"], "band": x["priority_band"], "next_gate": (
                "verify_public_inquiry_and_qualify_real_lead"
                if x["stage"] == "inquiry_candidate" else
                "verify_free_artifact_license_and_public_delivery"
                if x["stage"] == "free_acquisition" else
                "verify_rights_deliverable_price_payment_and_owner_approval"
            )}
            for x in ordered
        ],
        "offers": ordered,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--registry", type=Path, default=Path(__file__).with_name("mojtaba_commercial_offers_v1.json"))
    args = parser.parse_args(argv)
    try:
        report = assess(args.repo_root.resolve(), read_registry(args.registry))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        # Fail closed: never print uploaded offer text or private customer data.
        print(json.dumps({"scope": "source_only", "status": "blocked", "reason": type(exc).__name__},
                         sort_keys=True))
        return 2
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
