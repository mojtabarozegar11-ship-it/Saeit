#!/usr/bin/env python3
"""Run one independent, on-VPS factory preparation and manufacturing cycle.

Production begins from a local opportunity/product inventory and versioned
product recipes, NEVER an order event. No API tokens, network calls, sales,
publication or financial commitments. The factory's independent research loop
can update the DB at any time; next iteration detects changed products.
"""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import sys


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if not spec or not spec.loader:
        raise RuntimeError("MODULE_NOT_FOUND:" + name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCRIPTS = Path(__file__).resolve().parent


def run_cycle(database, output, recipes, *, max_products=25, max_recipes=2):
    root = Path(output).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(str(root), 0o700)
    lock = root / ".production-cycle.lock"
    with lock.open("a+b") as file:
        os.chmod(str(lock), 0o600)
        try:
            fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status": "already_running", "processed": 0, "manufactured": 0}
        portfolio = load("saeit_factory_portfolio_cycle",
                         SCRIPTS / "factory_autonomous_portfolio.py")
        maker = load("saeit_factory_manufacturer_cycle",
                     SCRIPTS / "factory_product_maker.py")
        # Product ideas and their pre-publication QA evidence are read-only DB inputs.
        dossier = portfolio.build(database, str(root / "research-dossiers"), max_products)
        repair = load("saeit_factory_rework_cycle",
                      SCRIPTS / "factory_product_rework.py")
        selected = sorted(maker.RECIPES)[:max_recipes]
        if not Path(recipes).is_dir():
            raise RuntimeError("PRODUCT_RECIPE_DIRECTORY_MISSING")
        produced = []
        failures = []
        for recipe in selected:
            source = Path(recipes) / recipe
            # When an individual product fails, don't lose the prior verified
            # ZIP or prevent another unrelated recipe from being built.
            try:
                result = maker.manufacture(recipe, recipes, root / "digital-products")
            except RuntimeError as failure:
                # Unexpected runtime failures are not considered successful,
                # and are not swallowed: only known QA/recipe failures enter
                # documented rework.
                code = repair.classify_error(failure)
                if code == "OTHER_PRODUCTION_ERROR":
                    raise
                recorded = repair.record_failure(
                    root, recipe, failure,
                    str(source) if source.is_dir() else "recipe_missing")
                failures.append(recorded)
                continue
            produced.append(result)
            manifest = root / "digital-products" / recipe / "manufacturing_manifest.json"
            if manifest.is_file():
                repair.record_technical_recovery(
                    root, recipe, json.loads(manifest.read_text(encoding="utf-8")))
        rework_counts = repair.summarize(root)
        for candidate in dossier.get("entries", []):
            repair.record_research_gaps(root, candidate)
        research_rework_counts = repair.summarize_research(root)
        # The outbox is a PRIVATE staging manifest, not a request to a shop.
        # It deliberately does not carry a publish=true flag.
        state = {
            "schema_version": 1,
            "mode": "autonomous_supply_led",
            "depends_on_orders": False,
            "api_usage": "none",
            "product_candidates_processed": dossier["processed_count"],
            "research_dossiers_updated": dossier["updated_count"],
            "built_product_count": len(produced),
            "built_product_recipes": [p["recipe"] for p in produced],
            "artifact_qa_passed": bool(produced) and not failures and all(
                p["qa_status"] == "passed" for p in produced),
            "quality_failures_this_cycle": [
                {"recipe": item["recipe"], "code": item["code"],
                 "status": item["status"], "round": item["issue_round"]}
                for item in failures
            ],
            "private_rework_queue": rework_counts,
            "research_correction_queue": research_rework_counts,
            "manufacturing_failed_recipe_count": len(failures),
            "technical_zip_checks_only": True,
            "research_coverage_policy": "saeit.factory.research-readiness.v1",
            "research_review_candidate_count": dossier.get("research_review_candidates", 0),
            "research_evidence_thresholds_satisfied_for_all_scanned": bool(
                dossier["processed_count"] and dossier.get("research_review_candidates", 0) == dossier["processed_count"]
            ),
            "commercial_quality_review_completed": False,
            "publishable_product_count": 0,
            "publication_locked_until_owner_approval": True,
            "store_distribution_state": "not_connected",
        }
        maker.atomic_text(root / "production-state.json",
                          json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        fcntl.flock(file.fileno(), fcntl.LOCK_UN)
        return {"status": "needs_rework" if failures else "ok",
                "processed": dossier["processed_count"],
                "manufactured": len(produced), "updated": dossier["updated_count"],
                "failed": len(failures), "rework_queue": rework_counts,
                "research_rework_queue": research_rework_counts}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--recipes", required=True)
    p.add_argument("--max-products", type=int, default=25)
    p.add_argument("--max-recipes", type=int, default=2)
    options = p.parse_args(argv)
    if not 1 <= options.max_products <= 100 or not 1 <= options.max_recipes <= 20:
        raise ValueError("BOUNDED_LIMIT_REQUIRED")
    result = run_cycle(options.db, options.out, options.recipes,
                       max_products=options.max_products,
                       max_recipes=options.max_recipes)
    print("VPS_FACTORY_CYCLE_STATUS=" + result["status"])
    print("VPS_FACTORY_ORDERS_REQUIRED=false")
    print("VPS_FACTORY_PRIVATE_PRODUCT_PACKAGES=" + str(result["manufactured"]))
    print("VPS_FACTORY_PRODUCT_CANDIDATES_SCANNED=" + str(result["processed"]))
    print("VPS_FACTORY_QA_REWORK_NEW_OR_OPEN=" + str(result.get("failed", 0)))
    print("VPS_FACTORY_PRIVATE_QA_REWORK=" + json.dumps(result.get("rework_queue", {}), sort_keys=True))
    print("VPS_FACTORY_RESEARCH_REWORK=" + json.dumps(result.get("research_rework_queue", {}), sort_keys=True))
    print("VPS_FACTORY_STORE_PUBLICATION_ENABLED=false")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print("VPS_FACTORY_CYCLE_ERROR=" + type(error).__name__ + ":" + str(error)[:400], file=sys.stderr)
        sys.exit(1)
