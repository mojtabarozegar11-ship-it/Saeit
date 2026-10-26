#!/usr/bin/env python3
"""Run one independent, on-VPS factory preparation and manufacturing cycle.

Production begins from a local opportunity/product inventory and versioned
product recipes, NEVER an order event. No API tokens, network calls, sales,
publication or financial commitments. The factory's independent research loop
can update the DB at any time; next iteration detects changed products.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import tempfile
from pathlib import Path
import sys
import sqlite3
import time
from datetime import datetime, timezone


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if not spec or not spec.loader:
        raise RuntimeError("MODULE_NOT_FOUND:" + name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCRIPTS = Path(__file__).resolve().parent



PRODUCT_SLOT_CAPACITY = 1
PRODUCT_LINE_ID = 41
SLOT_SCHEMA = "saeit.factory.product-slots.v1"
CLEARANCE_SCHEMA = "saeit.factory.signed-quality-clearance.v1"
PRODUCT_SLUG = re.compile(r"^[a-z][a-z0-9_]{1,65}$")
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _read_private_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        return None
    try:
        value = json.loads(path.read_text(encoding="utf8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, UnicodeError):
        return None


def _write_private_json(path, value):
    path = Path(path)
    parent = path.parent
    if parent.is_symlink():
        raise RuntimeError("PRODUCT_SLOT_STATE_PATH_UNSAFE")
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(parent, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=".product-slots-", dir=str(parent))
    try:
        with os.fdopen(fd, "w", encoding="utf8") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _verified_quality_exit(root, recipe):
    """Only a current, signed 1000/1000 clearance frees a production slot."""
    manifest_path = root / "digital-products" / recipe / "manufacturing_manifest.json"
    archive_path = root / "digital-products" / recipe / (recipe + "-internal-qa.zip")
    clearance_path = root / "quality-excellence" / "signed-clearances" / recipe / "current.json"
    manifest = _read_private_json(manifest_path)
    clearance = _read_private_json(clearance_path)
    if (not manifest or not clearance or archive_path.is_symlink()
            or not archive_path.is_file()):
        return None
    artifact_sha = manifest.get("artifact_sha256")
    if (manifest.get("recipe") != recipe or manifest.get("qa_status") != "passed"
            or not isinstance(artifact_sha, str) or not HEX_SHA256.fullmatch(artifact_sha)):
        return None
    digest = hashlib.sha256()
    try:
        with archive_path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError:
        return None
    roles = clearance.get("valid_signed_roles")
    roles = set(roles) if isinstance(roles, list) and all(isinstance(x, str) for x in roles) else set()
    independent_roles = {"domain_specialist", "independent_quality_auditor", "rights_reviewer"}
    if (digest.hexdigest() != artifact_sha
            or clearance.get("schema") != CLEARANCE_SCHEMA
            or clearance.get("eligible") is not True
            or clearance.get("verified_grade_total") != 1000
            or clearance.get("artifact_sha256") != artifact_sha
            or not independent_roles.issubset(roles)
            or clearance.get("owner_authorization_kind") not in ("direct_owner", "verified_delegated_agent")
            or clearance.get("publication_executed") is not False
            or clearance.get("payment_activated") is not False):
        return None
    return {"artifact_sha256": artifact_sha,
            "clearance_sha256": hashlib.sha256(clearance_path.read_bytes()).hexdigest()}


def _cleanup_completed_product_extras(root, recipe):
    """Free per-product working files only after exact signed 1000 clearance.

    Keep the certified deliverable, its manufacturing manifest, exact-version
    clearance and exit receipt. Remove disposable source/rework candidates.
    """
    import shutil
    root = Path(root)
    if root.is_symlink():
        raise RuntimeError("PRODUCT_CLEANUP_ROOT_UNSAFE")
    targets = [
        root / "generated-product-recipes" / recipe,
        root / "quality-excellence" / "evolved-source-technical-products" / recipe,
        root / "quality-excellence" / "rework" / recipe,
        root / "qa-rework" / recipe,
        root / "research-dossiers" / recipe,
        root / "engineering-workorders" / recipe,
    ]
    revisions = root / "generated-source-revisions"
    if revisions.exists():
        if revisions.is_symlink() or not revisions.is_dir():
            raise RuntimeError("PRODUCT_CLEANUP_REVISION_ROOT_UNSAFE")
        targets.extend(p for p in revisions.iterdir()
                       if p.name.startswith(recipe + "-") and p.is_dir())
    for target in targets:
        if target.is_symlink():
            raise RuntimeError("PRODUCT_CLEANUP_SYMLINK_BLOCKED")
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            raise RuntimeError("PRODUCT_CLEANUP_NON_DIRECTORY_BLOCKED")


def _maintain_product_slots(root, recipe_names):
    """Line 41 runs one product at a time; exact signed 1000 exits the line."""
    state_path = (Path(root) / "quality-excellence" / "product-flow"
                  / "active-slots" / "current.json")
    if state_path.is_symlink():
        raise RuntimeError("PRODUCT_SLOT_STATE_SYMLINK")
    state = _read_private_json(state_path)
    if state is None and state_path.exists():
        raise RuntimeError("PRODUCT_SLOT_STATE_INVALID")
    if state is None:
        state = {"schema": SLOT_SCHEMA, "active": [], "waiting": [],
                 "exited": {}, "last_admitted_recipe": ""}
    if state.get("schema") != SLOT_SCHEMA or not isinstance(state.get("active"), list):
        raise RuntimeError("PRODUCT_SLOT_STATE_SCHEMA_INVALID")
    active = []
    seen = set()
    for item in state["active"]:
        if (not isinstance(item, dict) or not isinstance(item.get("recipe"), str)
                or not PRODUCT_SLUG.fullmatch(item["recipe"])):
            raise RuntimeError("PRODUCT_SLOT_ENTRY_INVALID")
        if item["recipe"] not in seen:
            active.append(item)
            seen.add(item["recipe"])
    if len(active) > 100:
        raise RuntimeError("PRODUCT_SLOT_MIGRATION_LIMIT_EXCEEDED")
    exited = state.get("exited", {})
    waiting = state.get("waiting", [])
    if not isinstance(exited, dict) or not isinstance(waiting, list):
        raise RuntimeError("PRODUCT_SLOT_QUEUE_INVALID")
    queue = []
    queued = set()
    for recipe in waiting:
        if not isinstance(recipe, str) or not PRODUCT_SLUG.fullmatch(recipe):
            raise RuntimeError("PRODUCT_SLOT_WAITING_ENTRY_INVALID")
        if recipe not in seen and recipe not in queued:
            queue.append(recipe)
            queued.add(recipe)
    # Migrate the former five-slot roster into one active item plus a FIFO queue.
    for item in active[1:]:
        recipe = item["recipe"]
        if recipe not in queued:
            queue.append(recipe)
            queued.add(recipe)
    retained = []
    for item in active[:1]:
        recipe = item["recipe"]
        clearance = _verified_quality_exit(root, recipe)
        if clearance:
            exited[recipe] = dict(clearance)
            _cleanup_completed_product_extras(root, recipe)
        else:
            retained.append(item)
    active = retained
    candidates = sorted({name for name in recipe_names
                         if isinstance(name, str) and PRODUCT_SLUG.fullmatch(name)})
    cursor = state.get("last_admitted_recipe", "")
    if not isinstance(cursor, str):
        cursor = ""
    rotated = [name for name in candidates if name > cursor] + [
        name for name in candidates if name <= cursor]
    for recipe in rotated:
        if recipe in seen or recipe in queued or any(x["recipe"] == recipe for x in active):
            continue
        clearance = _verified_quality_exit(root, recipe)
        if clearance:
            exited[recipe] = dict(clearance)
            continue
        manifest = _read_private_json(Path(root) / "digital-products" / recipe
                                      / "manufacturing_manifest.json")
        current_artifact = manifest.get("artifact_sha256") if manifest else None
        prior_exit = exited.get(recipe)
        if isinstance(prior_exit, dict) and prior_exit.get("artifact_sha256") == current_artifact:
            continue
        queue.append(recipe)
        queued.add(recipe)
    if not active and queue:
        next_recipe = queue.pop(0)
        active = [{"recipe": next_recipe, "status": "active"}]
        cursor = next_recipe
    state = {"schema": SLOT_SCHEMA, "line_id": 41, "capacity": 1,
             "active": active, "waiting": queue, "exited": exited,
             "last_admitted_recipe": cursor,
             "exit_rule": "exact passed artifact with valid signed 1000/1000 clearance",
             "cleanup_rule": "remove per-product intermediates only; retain certified artifact and proof"}
    _write_private_json(state_path, state)
    return [item["recipe"] for item in active]


def run_cycle(database, output, recipes, *, max_products=25, max_recipes=None,
              enable_designer=False, enable_design_intake=False, design_capacity=1,
              enable_invention_supply=False):
    if (type(max_products) is not int or not 1<=max_products<=100
            or max_recipes is not None and (type(max_recipes) is not int or max_recipes<1)):
        raise ValueError('BOUNDED_LIMIT_REQUIRED')
    if type(design_capacity) is not int or not 1 <= design_capacity <= 20:
        raise ValueError('DESIGN_CAPACITY_INVALID')
    started=time.time()
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
        genetics = load("saeit_factory_master_agent_genetics", SCRIPTS / "factory_master_agent_genetics_v1.py")
        master_genome = genetics.begin_cycle(root)
        portfolio = load("saeit_factory_portfolio_cycle",
                         SCRIPTS / "factory_autonomous_portfolio.py")
        maker = load("saeit_factory_manufacturer_cycle",
                     SCRIPTS / "factory_product_maker.py")
        # Product ideas and their pre-publication QA evidence are read-only DB inputs.
        research_failures=[]
        try:
            dossier = portfolio.build(database, str(root / "research-dossiers"), max_products)
        except (RuntimeError,ValueError,OSError,sqlite3.Error) as error:
            research_failures.append({'type':type(error).__name__,'reason':str(error)[:400]})
            dossier={'processed_count':0,'updated_count':0,'entries':[]}

        repair = load("saeit_factory_rework_cycle",
                      SCRIPTS / "factory_product_rework.py")
        customer = load("saeit_factory_real_customer_acceptance",
                        SCRIPTS / "factory_verified_customer_cycle_20261021.py")
        quality_return_state = repair.quality_returns(root)
        quality_return_orders = {x['recipe']: x for x in quality_return_state['orders']}
        quality_return_candidates = []
        engineering_state={"enabled":False,"enqueued":0}
        design_state = {"enabled": False, "new_recipes": 0}
        designer_failures = []
        active_recipe_names = None
        source_recoveries = []
        source_evolutions = []
        evolution_attempt_defects = []
        evolution_attempted_count = 0
        invention_state={"enabled":False,"new_technical_briefs_this_tick":0}
        if enable_designer:
            designer = load("saeit_factory_recipe_designer", SCRIPTS / "factory_recipe_designer.py")
            if enable_design_intake and enable_invention_supply:
                try:
                    inventor=load('saeit_factory_continuous_invention',SCRIPTS/'factory_continuous_invention.py')
                    invention_state=inventor.propose(root,max_new=1,max_pending=5)
                    invention_state['enabled']=True
                except (ValueError,RuntimeError,OSError,ArithmeticError) as error:
                    designer_failures.append({'type':'invention_supply','reason':str(error)[:400]})
            if enable_design_intake:
                try:
                    intake=load('saeit_factory_design_intake',SCRIPTS/'factory_design_intake.py')
                    engineering_state=intake.cycle(root,supply=SCRIPTS.parent/'factory_config/internal_design_supply.json')
                    engineering_state['enabled']=True
                    blocked=sum(x['blocked']+x['deferred'] for x in engineering_state.get('channels',{}).values())
                    if blocked:designer_failures.append({'type':'engineering_rework','source_revisions':blocked})
                except (ValueError,OSError,RuntimeError) as error:
                    designer_failures.append({'type':'engineering_intake','reason':str(error)[:400]})
            try:
                design_state = designer.cycle(root, seed_file=SCRIPTS.parent / "factory_config" / "design_opportunities.json",
                                              database=database, max_designs=design_capacity)
            except (ValueError, OSError, ArithmeticError, sqlite3.Error) as error:
                designer_failures.append({"type": type(error).__name__, "reason": str(error)[:400]})
                design_state["status"] = "needs_rework"
            designer_failures.extend(design_state.get("intake_failures",[]))
            designer_failures.extend(design_state.get("rework",[]))
            if design_state.get("deferred_rework_requests",0):
                designer_failures.append({'type':'deferred_rework',
                    'count':design_state['deferred_rework_requests']})
            design_state["enabled"] = True
        admission_failures = []
        recipe_catalog = maker.discover_recipes(recipes, errors=admission_failures)
        recipe_roots = {key: Path(recipes) for key in recipe_catalog}
        generated_root = root / "generated-product-recipes"
        if enable_designer and generated_root.is_dir():
            generated_failures = []
            generated = maker.discover_recipes(generated_root, errors=generated_failures)
            # Admission defects (e.g. missing tests) used to bypass source repair.
            # Repair only compiler-owned sources with intact, verified provenance.
            for item in generated_failures:
                recipe = item["recipe"]
                try:
                    recovered = designer.recover_recipe(recipe, generated_root)
                except (RuntimeError, ValueError, OSError, ArithmeticError) as error:
                    item["recovery_error"] = str(error)[:400]
                    admission_failures.append(item)
                else:
                    repair.record_failure(root, recipe, RuntimeError(item["reason"]),
                                          str(generated_root / recipe))
                    source_recoveries.append(recovered)
                    generated[recipe] = maker.inspect_recipe(generated_root / recipe)
            if set(generated) & set(recipe_catalog):
                raise RuntimeError("GENERATED_RECIPE_COLLIDES_WITH_STATIC_SOURCE")
            recipe_catalog.update(generated)
            recipe_roots.update({key: generated_root for key in generated})
            active_recipe_names = _maintain_product_slots(root, recipe_catalog)
            # Quality-driven product evolution: compiler-owned goods really gain
            # a bounded customer batch API, with holdout and real unit tests.
            # Rotate the bounded queue across ticks; never leave later product
            # revisions permanently behind a fixed first-N selection.
            evolution_cursor_file=root/'source-evolution-cursor.json'
            try:
                last=json.loads(evolution_cursor_file.read_text(encoding='utf8')).get('last_recipe','')
                if not isinstance(last,str):last=''
            except (OSError,ValueError,AttributeError):
                last=''
            pending_evolution=sorted(r for r in generated if r in active_recipe_names)
            pending_evolution=[r for r in pending_evolution if r>last]+[
                r for r in pending_evolution if r<=last]
            # The master-agent genome can only prioritize genuine QA returns
            # and choose a bounded quota inside the five active product slots.
            if master_genome["quality_return_priority"]:
                pending_evolution.sort(key=lambda r: r not in quality_return_orders)
            evolution_attempted_count = 0
            for candidate_recipe in pending_evolution[:master_genome["source_evolution_quota"]]:
                evolution_attempted_count += 1
                try:
                    outcome=designer.evolve_recipe(candidate_recipe,generated_root)
                    if outcome.get('changed') is True:
                        # The revised files are actual new manufacturer inputs;
                        # commercial approval is still a separate signed gate.
                        generated[candidate_recipe]=maker.inspect_recipe(
                            generated_root/candidate_recipe)
                        source_evolutions.append(outcome)
                except (RuntimeError,ValueError,OSError,ArithmeticError) as error:
                    # The manufacturing defect handler further below may
                    # recompile this same source and prove it technically
                    # recovered. Do not permanently mark that same repaired
                    # version as failed due to a pre-repair observation.
                    evolution_attempt_defects.append({'type':'source_evolution',
                        'recipe':candidate_recipe,'reason':str(error)[:240]})
                maker.atomic_text(evolution_cursor_file,
                                  json.dumps({'last_recipe':candidate_recipe})+'\n')
            recipe_catalog.update(generated)
            recipe_roots.update({key: generated_root for key in generated})
        for item in admission_failures:
            repair.record_failure(root,item['recipe'],RuntimeError(item['reason']),
                                  str(recipe_roots.get(item['recipe'],Path(recipes))/item['recipe']))
        if active_recipe_names is None:
            active_recipe_names = _maintain_product_slots(root, recipe_catalog)
        selected = [recipe for recipe in active_recipe_names if recipe in recipe_catalog]
        # Persist rotation: bounded cycles must not starve later recipe names.
        cursor_file = root / "recipe-cursor.json"
        try:
            cursor = json.loads(cursor_file.read_text(encoding="utf-8")).get("last_recipe", "")
        except (OSError, ValueError, AttributeError):
            cursor = ""
        if max_recipes is not None:
            selected = [r for r in selected if r > cursor] + [r for r in selected if r <= cursor]
        if max_recipes is not None:
            selected = selected[:max_recipes]
        if not Path(recipes).is_dir():
            raise RuntimeError("PRODUCT_RECIPE_DIRECTORY_MISSING")
        produced = []
        new_product_ids = []
        updated_product_ids = []
        failures = []
        customer_acceptances = []
        customer_repairs = []
        fresh_customer_checks = 0
        cached_customer_checks = 0
        for recipe in selected:
            source = recipe_roots[recipe] / recipe
            previous_product = root / 'digital-products' / recipe
            already_manufactured = ((previous_product / (recipe + '-internal-qa.zip')).is_file()
                                    or (previous_product / 'manufacturing_manifest.json').is_file())
            # When an individual product fails, don't lose the prior verified
            # ZIP or prevent another unrelated recipe from being built.
            try:
                result = maker.manufacture(recipe, recipe_roots[recipe], root / "digital-products")
            except (RuntimeError,ValueError,OSError,ArithmeticError) as failure:
                # Every product runtime failure enters durable rework; healthy
                # recipes continue. Infrastructure/import errors still propagate.
                recorded = repair.record_failure(
                    root, recipe, failure,
                    str(source) if source.is_dir() else "recipe_missing")
                if enable_designer and recipe_roots[recipe] == generated_root:
                    try:
                        recovered = designer.recover_recipe(recipe, generated_root)
                        result = maker.manufacture(recipe, generated_root, root / "digital-products")
                        source_recoveries.append(recovered)
                    except (RuntimeError, ValueError, OSError, ArithmeticError) as recovery_error:
                        recorded["recovery_error"] = str(recovery_error)[:200]
                        failures.append(recorded)
                        continue
                else:
                    failures.append(recorded)
                    continue
            # Test the actual bytes delivered to a customer, from a fresh ZIP
            # extraction. Manufacturer test counts alone cannot pass this gate.
            try:
                customer_receipt, customer_fresh = customer.inspect_product_scheduled(root, recipe)
                fresh_customer_checks += int(customer_fresh)
                cached_customer_checks += int(not customer_fresh)
            except (RuntimeError, ValueError, OSError, ArithmeticError) as customer_error:
                recorded = repair.record_failure(root, recipe, customer_error, str(source))
                reason = str(customer_error)
                # One mechanical repair attempt, never a self-awarded score.
                # Functional regressions stay in the durable rework queue.
                if any(code in reason for code in (
                        "CUSTOMER_ZIP_HASH_MISMATCH", "CUSTOMER_ZIP_CRC_FAILED",
                        "CUSTOMER_ZIP_UNUSABLE", "CUSTOMER_ZIP_FILE_INDEX_MISMATCH")):
                    try:
                        result = maker.manufacture(recipe, recipe_roots[recipe],
                                                   root / "digital-products")
                        customer_receipt, customer_fresh = customer.inspect_product_scheduled(root, recipe)
                        fresh_customer_checks += int(customer_fresh)
                        cached_customer_checks += int(not customer_fresh)
                        customer_repairs.append({"recipe": recipe,
                            "artifact_sha256": customer_receipt["artifact_sha256"],
                            "technical_repair_verified": True})
                    except (RuntimeError, ValueError, OSError, ArithmeticError) as retry_error:
                        recorded["repair_error"] = str(retry_error)[:250]
                        failures.append(recorded)
                        continue
                else:
                    failures.append(recorded)
                    continue
            customer_acceptances.append(customer_receipt)
            produced.append(result)
            if result.get('changed'):
                (updated_product_ids if already_manufactured else new_product_ids).append(recipe)
            manifest = root / "digital-products" / recipe / "manufacturing_manifest.json"
            if manifest.is_file():
                # Bind recovery to fresh recipe bytes and the exact customer-bound ZIP.
                source_name, source_files = maker.inspect_recipe(source)
                repair.record_technical_recovery(
                    root, recipe, json.loads(manifest.read_text(encoding="utf-8")),
                    archive_path=previous_product / (recipe + "-internal-qa.zip"),
                    source_digest=maker.source_digest(source, source_files))
                if recipe in quality_return_orders:
                    try:
                        quality_return_candidates.append(repair.record_quality_candidate(
                            root, quality_return_orders[recipe],
                            json.loads(manifest.read_text(encoding='utf-8')),
                            archive_path=previous_product / (recipe + '-internal-qa.zip')))
                    except (RuntimeError, ValueError, OSError) as error:
                        designer_failures.append({'type': 'quality_return_reinspection',
                            'recipe': recipe, 'reason': str(error)[:200]})
        recovered_source_ids={entry['recipe'] for entry in source_recoveries}
        designer_failures.extend(
            issue for issue in evolution_attempt_defects
            if issue['recipe'] not in recovered_source_ids
        )
        if enable_design_intake and engineering_state.get('enabled'):
            try:engineering_state['production_results']=intake.reconcile(root)
            except (ValueError,OSError) as error:
                designer_failures.append({'type':'engineering_reconciliation','reason':str(error)[:400]})
        if selected:
            maker.atomic_text(cursor_file, json.dumps({"last_recipe": selected[-1]}))
        rework_counts = repair.summarize(root)
        for candidate in dossier.get("entries", []):
            repair.record_research_gaps(root, candidate)
        research_rework_counts = repair.summarize_research(root)
        # The outbox is a PRIVATE staging manifest, not a request to a shop.
        # It deliberately does not carry a publish=true flag.
        state = {
            "schema_version": 1,
            "cycle_status": "needs_rework" if failures or admission_failures or designer_failures or research_failures else "ok",
            "mode": "autonomous_supply_led",
            "depends_on_orders": False,
            "api_usage": "none",
            "token_usage": 0,
            "build_policy": "line_41_single_product_signed-1000-gated",
            "active_product_slot_capacity": PRODUCT_SLOT_CAPACITY,
            "active_production_line_id": PRODUCT_LINE_ID,
            "active_product_slot_recipes": active_recipe_names,
            "registered_recipe_count": len(recipe_catalog),
            "recipe_designer": design_state,
            "engineering_intake":engineering_state,
            "continuous_invention":invention_state,
            "designer_failures": designer_failures,
            "research_failures": research_failures,
            "source_recoveries": source_recoveries,
            "source_evolutions": source_evolutions,
            "source_evolution_attempted_count": evolution_attempted_count if enable_designer else 0,
            "genuinely_evolved_source_count": len(source_evolutions),
            "source_evolution_policy": "bounded_compiler_owned_verified_sources_only",
            "master_agent_genome_generation": master_genome["generation"],
            "master_agent_genome_policy": {k:v for k,v in master_genome.items() if k != "generation"},
            "recipe_admission_failures": admission_failures,
            "product_candidates_processed": dossier["processed_count"],
            "research_dossiers_updated": dossier["updated_count"],
            "built_product_count": len(produced),
            "new_or_updated_product_count": sum(bool(p.get("changed")) for p in produced),
            "truly_new_product_count": len(new_product_ids),
            "updated_existing_product_count": len(updated_product_ids),
            "truly_new_product_ids": new_product_ids,
            "updated_existing_product_ids": updated_product_ids,
            "functional_prototype_only": True,
            "designs_processed_per_cycle_limit": design_capacity,
            "unchanged_product_rechecks": sum(not bool(p.get("changed")) for p in produced),
            "built_product_recipes": [p["recipe"] for p in produced],
            "real_customer_zip_checks_passed": len(customer_acceptances),
            "fresh_extracted_customer_checks_passed": fresh_customer_checks,
            "exact_sha_cached_customer_checks_passed": cached_customer_checks,
            "real_customer_zip_technical_receipts": customer_acceptances,
            "mechanical_customer_zip_repairs_verified": customer_repairs,
            "professional_quality_1000_customer_checks_cannot_approve": True,
            "artifact_qa_passed": bool(produced) and not failures and not admission_failures and all(
                p["qa_status"] == "passed" for p in produced),
            "quality_failures_this_cycle": [
                {"recipe": item["recipe"], "code": item["code"],
                 "status": item["status"], "round": item["issue_round"]}
                for item in failures
            ],
            "private_rework_queue": rework_counts,
            "quality_returns_to_production": quality_return_state,
            "quality_return_build_candidates": quality_return_candidates,
            "quality_returns_unresolved": len(quality_return_orders),
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
        # Select the next master-agent policy genome from measured private-cycle
        # QA outcomes; this optimizer never scores products or grants clearance.
        state["master_agent_evolution"] = genetics.finish_cycle(root, master_genome, state)
        # Persist actual activity, not merely a configured cron or a cached ZIP.
        health_path=root/'production-health.json'
        try:
            health=json.loads(health_path.read_text(encoding='utf8'))
            if not isinstance(health,dict):health={}
        except (OSError,ValueError):health={}
        def counter(key):
            value=health.get(key,0)
            return value if type(value) is int and value>=0 else 0
        healthy=state['cycle_status']=='ok'
        fresh=state['new_or_updated_product_count']>0
        reason=None if fresh else 'blocked_design_or_research' if not healthy else 'waiting_for_new_validated_need_or_design'
        state['zero_new_products_reason_code']=reason
        finished=time.time()
        state['cycle_started_at_utc']=datetime.fromtimestamp(started,timezone.utc).isoformat()
        state['cycle_finished_at_utc']=datetime.fromtimestamp(finished,timezone.utc).isoformat()
        state['cycle_duration_seconds']=max(0,finished-started)
        activity={'schema':'saeit.factory.production-health.v1',
                  'last_cycle_finished_at_utc':state['cycle_finished_at_utc'],
                  'last_healthy_cycle_at_utc':state['cycle_finished_at_utc'] if healthy else health.get('last_healthy_cycle_at_utc'),
                  'cycle_status':state['cycle_status'],'completed_cycles':counter('completed_cycles')+1,
                  'consecutive_degraded_cycles':0 if healthy else counter('consecutive_degraded_cycles')+1,
                  'new_or_updated_artifacts_total':counter('new_or_updated_artifacts_total')+state['new_or_updated_product_count'],
                  'new_or_updated_artifacts_this_cycle':state['new_or_updated_product_count'],
                  'new_distinct_product_ids_total':counter('new_distinct_product_ids_total')+len(new_product_ids),
                  'updated_existing_product_versions_total':counter('updated_existing_product_versions_total')+len(updated_product_ids),
                  'new_distinct_product_ids_this_cycle':len(new_product_ids),
                  'updated_existing_product_versions_this_cycle':len(updated_product_ids),
                  'last_new_artifact_at_utc':state['cycle_finished_at_utc'] if fresh else health.get('last_new_artifact_at_utc'),
                  'consecutive_zero_new_cycles':0 if fresh else counter('consecutive_zero_new_cycles')+1,
                  'zero_new_products_reason_code':reason,
                  'unfinished_rework_requires_attention':bool(failures or admission_failures or designer_failures or research_failures
                      or quality_return_orders or quality_return_state['invalid_orders']
                      or rework_counts.get('needs_rework') or rework_counts.get('expert_review')
                      or research_rework_counts.get('research_correction_required')),
                  'independent_quality_returns_pending':len(quality_return_orders),
                  'invalid_quality_return_orders':quality_return_state['invalid_orders'],
                  'commercial_quality_certified':False}
        maker.atomic_text(health_path,json.dumps(activity,sort_keys=True,indent=2)+'\n')
        maker.atomic_text(root / "production-state.json",
                          json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        fcntl.flock(file.fileno(), fcntl.LOCK_UN)
        return {"status": "needs_rework" if failures or admission_failures or designer_failures or research_failures else "ok",
                "processed": dossier["processed_count"],
                "manufactured": len(produced),
                "new_artifacts": sum(bool(p.get("changed")) for p in produced),
                "updated": dossier["updated_count"],
                "new_distinct_products": len(new_product_ids),
                "updated_existing_versions": len(updated_product_ids),
                "failed": len(failures), "rework_queue": rework_counts,
                "registered_recipes": len(recipe_catalog), "new_recipe_count": design_state["new_recipes"],
                "research_rework_queue": research_rework_counts}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--recipes", required=True)
    p.add_argument("--max-products", type=int, default=25)
    p.add_argument("--enable-designer", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--enable-design-intake", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--enable-invention-supply", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--design-capacity", type=int, default=6,
                   help="Maximum validated synthesis requests per VPS tick (1-20).")
    p.add_argument(
        "--max-recipes", type=int, default=None,
        help="Optional positive limit; by default build every registered recipe.",
    )
    options = p.parse_args(argv)
    if not 1 <= options.max_products <= 100 or (
        options.max_recipes is not None and options.max_recipes < 1
    ):
        raise ValueError("BOUNDED_LIMIT_REQUIRED")
    result = run_cycle(options.db, options.out, options.recipes,
                       max_products=options.max_products,
                       max_recipes=options.max_recipes, enable_designer=options.enable_designer,
                       enable_design_intake=options.enable_design_intake,
                       design_capacity=options.design_capacity,
                       enable_invention_supply=options.enable_invention_supply)
    print("VPS_FACTORY_CYCLE_STATUS=" + result["status"])
    if result["status"] == "already_running":
        return 0
    print("VPS_FACTORY_ORDERS_REQUIRED=false")
    print("VPS_FACTORY_PRIVATE_PRODUCT_PACKAGES=" + str(result["manufactured"]))
    print("VPS_FACTORY_ACTUALLY_NEW_PACKAGES=" + str(result.get("new_artifacts", 0)))
    print("VPS_FACTORY_FIRST_TIME_PRODUCT_IDS=" + str(result.get("new_distinct_products", 0)))
    print("VPS_FACTORY_UPDATED_EXISTING_PRODUCT_IDS=" + str(result.get("updated_existing_versions", 0)))
    print("VPS_FACTORY_REGISTERED_BUILD_RECIPES=" + str(result.get("registered_recipes", 0)))
    print("VPS_FACTORY_NEW_SYNTHESIZED_RECIPES=" + str(result.get("new_recipe_count", 0)))
    print("VPS_FACTORY_API_AND_TOKEN_USAGE=0")
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

