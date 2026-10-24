#!/usr/bin/env python3
"""Autonomous evidence workpaper agents; never impersonate people or issue certifications."""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import zipfile

HEX = re.compile(r"^[a-f0-9]{64}$")
PRODUCT = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
SCHEMA = "saeit.factory.ai-evidence-workpapers.v1"
OWNER_DELEGATION = {
    "schema": "saeit.factory.owner-delegation.v1",
    "principal_role": "factory_owner",
    "authorization_basis": "owner_explicitly_authorized_in_chat",
    "authorized_agent": "saeit-autonomous-evidence-analyst",
    "scope": "generate, organize, attribute, hash, and preserve preliminary factory evidence workpapers",
    "attribution": "owner-directed agent work product; technical author remains the AI agent",
    "digital_signature_created": False,
    "owner_signature_or_private_key_used": False,
    "human_expert_or_licensed_counsel_replaced": False,
    "legal_certification_created": False,
}
ROLE_KEYWORDS = {
    "market_benchmark_supplier": ("market", "competitor", "benchmark", "pricing", "price", "industry"),
    "innovation_provenance_supplier": ("patent", "provenance", "origin", "author", "copyright", "novelty"),
    "engineering_test_supplier": ("test", "build", "integration", "requirement", "coverage", "deploy", "source"),
    "domain_specialist_supplier": ("research", "scientific", "calibration", "agronomy", "crop", "domain", "data"),
    "customer_research_supplier": ("customer", "user", "feedback", "survey", "interview", "persona", "usability"),
    "ux_accessibility_supplier": ("accessibility", "a11y", "wcag", "keyboard", "alt", "locale", "responsive"),
    "adversarial_qa_supplier": ("test", "fault", "failure", "recovery", "security", "integrity", "crc"),
    "security_rights_supplier": ("license", "licence", "terms", "privacy", "security", "copyright", "contract", "permit"),
    "commerce_operations_supplier": ("product", "invoice", "order", "payment", "support", "delivery", "refund", "commerce"),
    "independent_review_supplier": ("review", "audit", "approval", "report", "signature", "certificate", "certification"),
}
LIMITS = {
    "identity": "Software agent output; no human identity, signature, expert qualification, legal opinion, or third-party connection.",
    "market_benchmark_supplier": "No live market or competitor data is fetched; candidate filenames are not market measurements.",
    "innovation_provenance_supplier": "No independent prior-art search or chain-of-title verification is performed.",
    "engineering_test_supplier": "Static source inspection only; arbitrary product code is never executed.",
    "domain_specialist_supplier": "No field observation, calibration, or qualified professional review is performed.",
    "customer_research_supplier": "No real customer or user sessions are conducted.",
    "ux_accessibility_supplier": "No browser, assistive technology, or real-device session is performed.",
    "adversarial_qa_supplier": "ZIP integrity is tested; no product runtime or penetration test is performed.",
    "security_rights_supplier": "Document names and static metadata do not establish rights, licenses, security, or legal compliance.",
    "commerce_operations_supplier": "No live orders, payments, delivery, refunds, or support cases are executed.",
    "independent_review_supplier": "This agent is not independent of the factory and cannot approve or certify its own product.",
}



# Operational remediation campaigns convert preliminary observations into a bounded
# next-action queue.  They never turn filename matches into quality approvals.
ROLE_REMEDIATION = {
    "market_benchmark_supplier": ("P2", "external",
        "Obtain dated, attributed market comparisons for the exact product and target region."),
    "innovation_provenance_supplier": ("P2", "external",
        "Request independent prior-art, authorship and chain-of-title review."),
    "engineering_test_supplier": ("P1", "factory_engineering",
        "Add executable, isolated contract tests for the version-pinned source and record results."),
    "domain_specialist_supplier": ("P2", "qualified_specialist",
        "Validate scientific assumptions and field applicability with a qualified reviewer."),
    "customer_research_supplier": ("P2", "real_users",
        "Collect consented usability evidence from actual target customers."),
    "ux_accessibility_supplier": ("P1", "factory_qa",
        "Run browser, keyboard and accessibility checks; retain reproducible evidence."),
    "adversarial_qa_supplier": ("P1", "factory_security_qa",
        "Run isolated negative-path and recovery tests; preserve failure reproductions."),
    "security_rights_supplier": ("P2", "security_and_rights_review",
        "Obtain verified license provenance, privacy review and security assessment."),
    "commerce_operations_supplier": ("P1", "staging_operations",
        "Test the staged order-to-delivery contract without live payments or customer data."),
    "independent_review_supplier": ("P2", "independent_reviewer",
        "Collect independent expert findings; this software agent cannot self-certify."),
}
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}


def build_remediation_plan(routes, members):
    """Deduplicate 100 workpapers into actionable, bounded evidence campaigns."""
    campaigns = []
    failed_parses = sorted(
        [{"path": item["path"], "sha256": item["sha256"],
          "reason": "static_parse_rejected"}
         for item in members if item["static_parse"] == "invalid_or_non_utf8"],
        key=lambda item: (item["path"], item["sha256"]))
    if failed_parses:
        campaigns.append({
            "campaign_id": "parse-repair",
            "priority": "P0",
            "executor_class": "factory_engineering",
            "criterion_ids": sorted(key for key, row in routes.items()
                                   if row["possible_supplier_role"] in
                                   ("engineering_test_supplier", "adversarial_qa_supplier")),
            "action": "Repair or quarantine rejected source files, rerun isolated parsing and tests.",
            "source_findings": failed_parses[:32],
            "source_findings_total": len(failed_parses),
            "automated_completion_means_independent_qc": False,
            "status": "OPEN",
        })
    for role in sorted(ROLE_REMEDIATION):
        priority, executor, action = ROLE_REMEDIATION[role]
        criteria = sorted(key for key, row in routes.items()
                          if row["possible_supplier_role"] == role)
        if not criteria:
            continue
        matched = sorted({item["path"] for key in criteria
                          for item in routes[key]["observations"][0]["candidate_members"]})
        campaigns.append({
            "campaign_id": "role-" + role,
            "priority": priority,
            "executor_class": executor,
            "criterion_ids": criteria,
            "action": action,
            "filename_leads_unverified": matched[:32],
            "filename_leads_total": len(matched),
            "missing_filename_leads": not matched,
            "automated_completion_means_independent_qc": False,
            "status": "OPEN",
        })
    campaigns.sort(key=lambda task:
                   (PRIORITY_ORDER[task["priority"]], task["campaign_id"]))
    return {
        "schema": "saeit.factory.ai-evidence-remediation.v1",
        "campaigns": campaigns,
        "distinct_criteria_routed": len(routes),
        "static_parse_failures": len(failed_parses),
        "priority_counts": {key: sum(task["priority"] == key for task in campaigns)
                            for key in ("P0", "P1", "P2")},
        "all_campaigns_are_preliminary": True,
        "independent_qc_decisions_added": 0,
        "commercial_release_allowed": False,
    }


def load_supplier(path):
    spec = importlib.util.spec_from_file_location("factory_quality_evidence_supplier_v1", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("AI_AGENT_SUPPLIER_MODULE_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inspect_members(archive, supplier, recipe):
    proof = supplier.zip_proof(archive, recipe)
    rows = []
    with zipfile.ZipFile(str(archive)) as bundle:
        for member in proof["members"]:
            path = member["path"]
            item = bundle.getinfo(path)
            row = dict(member)
            suffix = Path(path).suffix.lower()
            row["file_type"] = suffix or "extensionless"
            row["static_parse"] = "not_attempted"
            if suffix in (".py", ".json", ".md", ".txt", ".rst", ".html", ".css", ".js", ".yml", ".yaml") and item.file_size <= 500000:
                raw = bundle.read(item)
                try:
                    source = raw.decode("utf-8")
                    if suffix == ".py":
                        tree = ast.parse(source, filename=path)
                        tests = [node.name for node in ast.walk(tree)
                                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                                 and node.name.startswith("test")]
                        row["static_parse"] = "python_ast_valid"
                        row["test_function_count"] = len(tests)
                    elif suffix == ".json":
                        json.loads(source)
                        row["static_parse"] = "json_valid"
                    else:
                        row["static_parse"] = "utf8_text_readable"
                        row["text_line_count"] = source.count("\n") + (1 if source else 0)
                        row["word_count"] = len(re.findall(r"\b[\w'-]+\b", source))
                        row["heading_count"] = sum(1 for line in source.splitlines()
                                                   if line.lstrip().startswith("#"))
                except (UnicodeDecodeError, SyntaxError, ValueError):
                    row["static_parse"] = "invalid_or_non_utf8"
            rows.append(row)
    return rows


def build_dossier(root, policy, recipe, source_sha, artifact_sha, supplier):
    if not PRODUCT.fullmatch(recipe) or not HEX.fullmatch(source_sha) or not HEX.fullmatch(artifact_sha):
        raise RuntimeError("AI_AGENT_VERSION_ID_INVALID")
    version = Path(root) / "production-warehouse" / "finished" / recipe / source_sha
    manifest = supplier.read_json(version / "warehouse_manifest.json")
    archive = version / "product.zip"
    if (manifest.get("schema") != "saeit.factory.production-warehouse.v1"
            or manifest.get("product_id") != recipe or manifest.get("source_sha256") != source_sha
            or manifest.get("artifact_sha256") != artifact_sha
            or manifest.get("manufacturing_qc") != "passed"
            or manifest.get("commercial_release") is not False
            or manifest.get("site_transfer_state") != "not_transferred"
            or not archive.is_file() or archive.is_symlink()
            or manifest.get("bytes") != archive.stat().st_size):
        raise RuntimeError("AI_AGENT_WAREHOUSE_BINDING_OR_POLICY_INVALID")
    if supplier.hash_bytes(archive.read_bytes()) != artifact_sha:
        raise RuntimeError("AI_AGENT_ARTIFACT_HASH_MISMATCH")
    members = inspect_members(archive, supplier, recipe)
    routes = {}
    for criterion, detail in policy.items():
        route = supplier.supplier_route(criterion, detail, measured={"Q068"})
        role = route["possible_supplier_role"]
        keys = ROLE_KEYWORDS[role]
        candidates = [m for m in members if any(k in m["path"].lower() for k in keys)]
        # Baseline metadata stays traceable to the exact archived artifact.
        routes[criterion] = {
            "criterion_id": criterion,
            "criterion_name": detail["name"],
            "possible_supplier_role": role,
            "agent_type": "autonomous_static_evidence_analyst",
            "workpaper_state": "AI_PRELIMINARY_ONLY",
            "observations": [
                {"kind": "artifact_member_inventory", "member_count": len(members),
                 "candidate_member_count": len(candidates),
                 "candidate_members": [{"path": x["path"], "sha256": x["sha256"],
                                        "bytes": x["bytes"], "file_type": x["file_type"],
                                        "static_parse": x["static_parse"],
                                        "test_function_count": x.get("test_function_count"),
                                        "text_line_count": x.get("text_line_count"),
                                        "word_count": x.get("word_count"),
                                        "heading_count": x.get("heading_count")}
                                       for x in candidates[:8]]}
            ],
            "conclusion": ("Potential source files found by filename; their relevance and truth are unverified."
                           if candidates else
                           "No role-matched source filename found; this is a documented evidence gap."),
            "limits": LIMITS[role],
            "professional_points_awarded": None,
            "human_or_external_approval": False,
        }
    remediation = build_remediation_plan(routes, members)
    return {
        "schema": SCHEMA,
        "product_id": recipe,
        "source_sha256": source_sha,
        "artifact_sha256": artifact_sha,
        "warehouse_manifest_sha256": supplier.hash_bytes(
            (version / "warehouse_manifest.json").read_bytes()),
        "owner_delegation": dict(OWNER_DELEGATION),
        "owner_directed_agent_work_product": True,
        "receipt_integrity": "SHA256_CONTENT_INTEGRITY_ONLY_NOT_DIGITAL_SIGNATURE",
        "evidence_agent": {
            "name": "saeit-autonomous-evidence-analyst",
            "agent_identity": "saeit-autonomous-evidence-analyst",
            "acting_capacity": "authorized_automated_agent_for_factory_owner",
            "version": 1,
            "roles_run": sorted(ROLE_KEYWORDS),
            "agent_generated_workpapers": len(routes),
            "source_files_static_inspected": len(members),
            "source_file_inventory": members,
            "external_network_used": False,
            "product_code_executed": False,
            "limits": ["not a human", "not an independent reviewer", "not a licensed professional",
                       "does not create licenses, market measurements, user studies, or legal authority"],
        },
        "criteria_total": len(routes),
        "ai_workpapers": routes,
        "remediation_plan": remediation,
        "ai_evidence_is_not_human_or_independent_certification": True,
        "professional_quality_1000_points": None,
        "professional_quality_1000_certified": False,
        "sale_or_publication_allowed": False,
    }


def persist(root, dossier, supplier):
    raw = (json.dumps(dossier, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()
    folder = (Path(root) / "quality-excellence" / "ai-evidence-workpapers"
              / dossier["product_id"] / dossier["source_sha256"])
    if folder.is_symlink() or (folder.parent.exists() and folder.parent.is_symlink()):
        raise RuntimeError("AI_AGENT_OUTPUT_SYMLINK")
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    receipt = folder / ("workpaper-" + supplier.hash_bytes(raw) + ".json")
    if receipt.exists():
        if receipt.is_symlink() or receipt.read_bytes() != raw:
            raise RuntimeError("AI_AGENT_IMMUTABLE_RECEIPT_CONFLICT")
    else:
        flags = os.O_CREAT | os.O_WRONLY | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(str(receipt), flags, 0o600)
        with os.fdopen(fd, "wb") as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
    saved = supplier.read_json(receipt, size=10_000_000)
    if supplier.hash_bytes(receipt.read_bytes()) != supplier.hash_bytes(raw) or len(saved["ai_workpapers"]) != 100:
        raise RuntimeError("AI_AGENT_READBACK_FAILED")
    return {"product_id": dossier["product_id"], "source_sha256": dossier["source_sha256"],
            "artifact_sha256": dossier["artifact_sha256"],
            "receipt_sha256": supplier.hash_bytes(raw), "criteria_workpaper_count": 100,
            "agent_roles": len(ROLE_KEYWORDS), "professional_points_awarded": None,
            "receipt": str(receipt)}


def run(root, catalog_path, supplier_path):
    supplier = load_supplier(supplier_path)
    policy = supplier.catalog(catalog_path)
    warehouse = Path(root) / "production-warehouse"
    base = warehouse / "finished"
    if warehouse.is_symlink() or base.is_symlink() or not base.is_dir():
        raise RuntimeError("AI_AGENT_WAREHOUSE_UNAVAILABLE")
    results, rejected = [], []
    for product in sorted(base.iterdir()):
        if product.is_symlink() or not product.is_dir() or not PRODUCT.fullmatch(product.name):
            continue
        for version in sorted(product.iterdir()):
            if version.is_symlink() or not version.is_dir() or not HEX.fullmatch(version.name):
                continue
            try:
                manifest = supplier.read_json(version / "warehouse_manifest.json")
                proof = build_dossier(root, policy, product.name, version.name,
                                      manifest.get("artifact_sha256"), supplier)
                results.append(persist(root, proof, supplier))
            except Exception as exc:
                rejected.append({"product_id": product.name, "source_sha256": version.name,
                                 "reason": str(exc) or type(exc).__name__})
    summary = {"schema": "saeit.factory.ai-evidence-agent-run.v1",
               "versions_with_ai_workpapers": len(results),
               "versions_rejected": len(rejected),
               "criteria_workpapers": sum(x["criteria_workpaper_count"] for x in results),
               "agent_roles": len(ROLE_KEYWORDS), "receipts": results,
               "rejected": rejected,
               "release_decision": "HUMAN_AND_EXTERNAL_EVIDENCE_STILL_REQUIRED",
               "owner_delegation": dict(OWNER_DELEGATION),
               "owner_directed_agent_work_product": True,
               "professional_certification": False}
    print("FACTORY_AI_EVIDENCE_AGENT=" + json.dumps(summary, sort_keys=True))
    if not results:
        raise SystemExit("AI_AGENT_NO_VERSION_WORKPAPERS_CREATED")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-root", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--supplier", required=True)
    args = parser.parse_args()
    run(args.factory_root, args.catalog, args.supplier)


if __name__ == "__main__":
    main()
