#!/usr/bin/env python3
"""Start ten existing P0 agriculture projects on the private VPS, without publication.

Real stage-1 handoff and stage-2 research evidence are required.  A project
kickoff is not a claim that its booklet, expert review, or QA1000 is complete.
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys

import factory_stage1_handoff as s1
import factory_stage2_research as s2

SCHEMA = "saeit.factory.ten-project-launch.v1"
INDEX_SCHEMA = "saeit.factory.owner-agri200-p0-index.v1"
LOCALES = ("fa-IR", "en-US")


def read(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        raise RuntimeError("TEN_PROJECT_UNSAFE_FILE:" + path.name)
    data = json.loads(path.read_text(encoding="utf8"))
    if not isinstance(data, dict):
        raise RuntimeError("TEN_PROJECT_OBJECT_EXPECTED")
    return data


def once(path, value):
    if path.exists() or path.is_symlink():
        if read(path) != value:
            raise RuntimeError("TEN_PROJECT_IMMUTABLE_CONFLICT:" + path.name)
        return False
    s2.atomic(path, value)
    return True


def plan(order):
    # Concrete manufacturing tasks, but no unverified factual assertions.
    localized = []
    for edition in order["editions"]:
        if edition["locale"] not in LOCALES:
            raise RuntimeError("TEN_PROJECT_BAD_LOCALE")
        localized.append({
            "locale": edition["locale"], "title": edition["title"],
            "destination_after_independent_approval": edition["site"],
            "audience": edition["audience"],
            "chapters": [
                "Who this guide helps / مخاطب و هدف",
                "Diagnosis and context / تشخیص و شرایط",
                "Practical method / دستورالعمل عملی",
                "Worked examples and local decision table / مثال و جدول تصمیم",
                "Troubleshooting and safety / عیب‌یابی و ایمنی",
                "Worksheet, checklist and references / کاربرگ، چک‌لیست و منابع",
            ],
            "required_artifacts": [
                "Original edited manuscript in target language",
                "Evidence-linked citations for material claims",
                "Practical checklist and independently localized worked example",
                "Accessible rendered PDF inspected page-by-page",
                "Source SHA256, PDF SHA256, independent expert QA",
            ],
        })
    if len(localized) != 2 or {x["locale"] for x in localized} != set(LOCALES):
        raise RuntimeError("TEN_PROJECT_BILINGUAL_SPEC_MISSING")
    return {
        "schema": SCHEMA, "project_id": order["source_product_id"],
        "work_order_id": order["id"], "work_order_sha256": s1.digest(order),
        "priority": "P0", "workstream": "original_localized_agriculture_booklet",
        "manufacturing_checklist": list(order["acceptance"]),
        "editions": localized, "quality_1000_certified": False,
        "publication_allowed": False, "sales_ready": False,
    }


def stage3_seed(area, order, receipt_name):
    receipt = read(area / "stage-02" / "receipts" / receipt_name)
    research = read(area / "stage-02" / "completed-dossiers" / receipt_name)
    stage3 = read(area / "stage-03" / "inbox" / receipt_name)
    if (receipt.get("stage_2_completed") is not True
            or receipt.get("research_sha256") != s2.sha(research)
            or stage3.get("desk_research_sha256") != s2.sha(research)
            or stage3.get("order_id") != order["id"]
            or research.get("source_product_id") != order["source_product_id"]
            or research.get("stage2_documentation_complete") is not True
            or research.get("public_distribution_allowed") is not False):
        raise RuntimeError("TEN_PROJECT_STAGE3_PROOF_FAILED")
    return {
        "schema": SCHEMA, "project_id": order["source_product_id"],
        "work_order_id": order["id"], "stage": 3,
        "status": "source_linked_design_seed_created",
        "research_sha256": s2.sha(research),
        "research_claims_for_author_review": research["claims"],
        "bibliography_for_author_review": research["sources"],
        "target_editions": plan(order)["editions"],
        "fact_check_and_translation_required": True,
        "manuscript_complete": False, "quality_1000_certified": False,
        "commercial_release": False, "public_distribution_allowed": False,
    }


def run(root, activate=False):
    root = Path(root).expanduser().resolve()
    area = root / "production-instructions"
    index = read(area / "owner-agri200-p0-index.json")
    ids = index.get("order_ids_ranked")
    if (index.get("schema") != INDEX_SCHEMA or index.get("topic_count") != 200
            or not isinstance(ids, list) or len(ids) != 200
            or len(set(ids[:10])) != 10):
        raise RuntimeError("TEN_PROJECT_INVALID_P0_INDEX")
    project_root = area / "ten-projects"
    s2.directory(project_root)
    lock = project_root / ".launcher.lock"
    if lock.is_symlink():
        raise RuntimeError("TEN_PROJECT_UNSAFE_LOCK")
    with lock.open("a+b") as handle:
        os.fchmod(handle.fileno(), 0o600)
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        orders = []
        for position, ident in enumerate(ids[:10], 1):
            if not s1.ID_RE.fullmatch(str(ident)):
                raise RuntimeError("TEN_PROJECT_BAD_ORDER_ID")
            order = read(area / "orders" / (ident + ".json"))
            s1.validate_order(order, ident)
            if (order.get("origin") != "owner_requested_agri200_p0"
                    or order.get("priority_rank") != position
                    or order.get("priority") != "P0"
                    or order.get("source_product_id") != "AGRI-%03d" % position):
                raise RuntimeError("TEN_PROJECT_WRONG_PRIORITY_ORDER")
            orders.append(order)

        if activate:
            # Coordinate with the independent stage-1 minute worker: two first
            # writers must not produce different timestamped handoff receipts.
            order_lock = area / ".orders.lock"
            if order_lock.is_symlink():
                raise RuntimeError("TEN_PROJECT_UNSAFE_STAGE1_LOCK")
            with order_lock.open("a+b") as order_handle:
                os.fchmod(order_handle.fileno(), 0o600)
                fcntl.flock(order_handle.fileno(), fcntl.LOCK_EX)
                for order in orders:
                    s1.forward(root, order)
            s2.stage2_loop(root, batch=40)  # only researched items advance

        projects = []
        for position, order in enumerate(orders, 1):
            topic, ident = order["source_product_id"], order["id"]
            name = ident + "--r001.json"
            s2.verified_stage1_packet(area, name)
            folder = project_root / topic
            s2.directory(folder)
            kickoff_file = folder / "kickoff.json"
            if not kickoff_file.exists():
                once(kickoff_file, {
                    "schema": SCHEMA, "project_id": topic, "rank": position,
                    "work_order_id": ident, "work_order_sha256": s1.digest(order),
                    "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                    "stage_1_handoff_verified": True,
                    "owner_priority": "P0", "editions_requested": 2,
                    "qa_1000_certified": False, "public_distribution_allowed": False,
                })
            kickoff = read(kickoff_file)
            if (kickoff.get("work_order_sha256") != s1.digest(order)
                    or kickoff.get("project_id") != topic):
                raise RuntimeError("TEN_PROJECT_KICKOFF_INTEGRITY_FAILED")
            once(folder / "manufacturing-plan.json", plan(order))

            receipt_file = area / "stage-02" / "receipts" / name
            research_file = area / "stage-02" / "research-needed" / name
            if receipt_file.exists():
                design = stage3_seed(area, order, name)
                once(folder / ("stage3-design-" + design["research_sha256"] + ".json"), design)
                phase = "STAGE3_DESIGN_STARTED"
            elif research_file.exists():
                needs = read(research_file)
                if (needs.get("order_id") != ident
                        or needs.get("source_product_id") != topic
                        or needs.get("stage_2_research_completed") is not False):
                    raise RuntimeError("TEN_PROJECT_RESEARCH_BRIEF_INVALID")
                once(folder / "research-workplan.json", {
                    "schema": SCHEMA, "project_id": topic, "work_order_id": ident,
                    "scope": needs["localized_research_scopes"],
                    "source_collection_actions": needs["research_workplan"],
                    "evidence_location": "stage-02/source-evidence/" + topic + "--r001.json",
                    "verified_source_claims_yet": False,
                    "stage_2_completed": False,
                })
                phase = "STAGE2_RESEARCH_STARTED_SOURCES_NEEDED"
            else:
                raise RuntimeError("TEN_PROJECT_STAGE2_NOT_ACCOUNTED:" + ident)
            status = {"schema": SCHEMA, "project_id": topic,
                      "work_order_id": ident, "phase": phase,
                      "stage_1_verified": True, "editions": 2,
                      "manuscript_complete": False,
                      "quality_1000_certified": False,
                      "public_distribution_allowed": False}
            state_file = folder / "status.json"
            if not state_file.exists() or read(state_file) != status:
                s2.atomic(state_file, status)
            projects.append(status)

        summary = {
            "schema": SCHEMA, "selected_rank_range": [1, 10],
            "projects_kicked_off": len(projects),
            "bilingual_editions_planned": 2 * len(projects),
            "research_started_needs_sources": sum(
                p["phase"] == "STAGE2_RESEARCH_STARTED_SOURCES_NEEDED" for p in projects),
            "design_started_with_sources": sum(
                p["phase"] == "STAGE3_DESIGN_STARTED" for p in projects),
            "project_ids": [p["project_id"] for p in projects],
            "quality_1000_certified": 0, "website_deployments": 0,
            "commercial_release": False,
        }
        destination = project_root / "status.json"
        if not destination.exists() or read(destination) != summary:
            s2.atomic(destination, summary)
        return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-private", required=True)
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()
    result = run(args.factory_private, activate=args.activate)
    print("FACTORY_TEN_PROJECTS_STARTED=" + str(result["projects_kicked_off"]))
    print("FACTORY_TEN_PROJECTS_DESIGN_STARTED=" + str(result["design_started_with_sources"]))
    print("FACTORY_TEN_PROJECTS_RESEARCH_STARTED=" + str(result["research_started_needs_sources"]))
    print("FACTORY_TEN_PROJECTS_EDITION_GOAL=" + str(result["bilingual_editions_planned"]))
    print("FACTORY_TEN_PROJECT_IDS=" + ",".join(result["project_ids"]))
    print("FACTORY_TEN_QA1000_CERTIFIED=0")
    print("FACTORY_TEN_SITES_MODIFIED=0")


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print("FACTORY_TEN_LAUNCH_ERROR=" + type(err).__name__ + ":" + str(err)[:200],
              file=sys.stderr)
        raise SystemExit(1)
