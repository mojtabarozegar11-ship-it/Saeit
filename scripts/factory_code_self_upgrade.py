#!/usr/bin/env python3
"""Factory's reproducible code self-edit pipeline (private candidate mode).

Discovers all factory Python modules, generates actual revised source files
for observed known security defects, probes baseline against the candidate,
and records source hashes and measured regression evidence. No candidate is
executed by cron, released to storefronts, or auto-deployed to production.
Unreviewed free-form LLM code and arbitrary shell mutation are NOT allowed.
Python 3.8+, standard library.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

SCHEMA = "saeit.factory.code-self-upgrade.v1"
# The rules are explicit tested repair templates, not unrestricted code generation.
SAFE_FIXES = (
    # path, exact function signature, exact first body, function name, probe input
    ("scripts/factory_research_triage.py", "def atomic(path, value):",
     "    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)\n",
     "atomic", "dict"),
    ("scripts/factory_specialist_pilots.py", "def atomic(path, data):",
     "    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)\n",
     "atomic", "dict"),
    ("scripts/factory_first_product_pilot.py", "def write_atomic(path, text):",
     "    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)\n",
     "write_atomic", "text"),
    ("scripts/factory_public_library_adapter.py", "def atomic_write(path, raw, *, mode=0o644):",
     "    fd, temp = tempfile.mkstemp(prefix=\".saeit-public-\", dir=path.parent)\n",
     "atomic_write", "bytes"),
)
PRELUDE = "    if path.parent.is_symlink():\n        raise RuntimeError('SELF_UPGRADE_BLOCKED_SYMLINK_PARENT')\n"
MAX_FILE_BYTES = 1_000_000

# Probe an actual before/after behavior in a disposable directory.
PROBE = r"""
import importlib.util,json,pathlib,sys
target=pathlib.Path(sys.argv[1])
root=pathlib.Path(sys.argv[2])
outside=root/'outside'
inside=root/'inside'
outside.mkdir(parents=True)
inside.mkdir(parents=True)
(inside/'external').symlink_to(outside, target_is_directory=True)
spec=importlib.util.spec_from_file_location('self_edit_candidate',str(target))
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
blocked=False
try:
    function=getattr(module,sys.argv[3])
    payload={'test':'known_symlink_attack'} if sys.argv[4]=='dict' else (
        b'known_symlink_attack' if sys.argv[4]=='bytes' else 'known_symlink_attack')
    function(inside/'external'/'unexpected.json',payload)
except (OSError,RuntimeError,ValueError):
    blocked=True
print(json.dumps({'blocked':blocked,'escaped':(outside/'unexpected.json').exists()}))
"""


def digest_bytes(value):
    return hashlib.sha256(value).hexdigest()


def atomic(path, value):
    if path.is_symlink() or path.parent.is_symlink():
        raise RuntimeError("CODE_UPGRADE_UNSAFE_OUTPUT")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp = tempfile.mkstemp(prefix=".self-upgrade-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf8") as out:
            json.dump(value, out, indent=2, sort_keys=True)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, str(path))
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def inventory(repo):
    base = Path(repo).resolve()
    scripts = base / "scripts"
    if not scripts.is_dir() or scripts.is_symlink():
        raise RuntimeError("CODE_UPGRADE_FACTORY_SOURCE_MISSING")
    # Include all existing factory-related Python sources rather than a hand-
    # selected static number; a new module is discovered on the next run.
    source = list(scripts.glob("factory_*.py")) + list(scripts.glob("vps_master_evolution_cycle.py"))
    source += list((base / "ops" / "factory-toolchain").glob("*.py"))
    entries = []
    for file in sorted(set(source)):
        if file.is_symlink() or not file.is_file() or file.stat().st_size > MAX_FILE_BYTES:
            raise RuntimeError("CODE_UPGRADE_UNSAFE_SOURCE")
        data = file.read_bytes()
        ast.parse(data.decode("utf8"), filename=str(file))
        entries.append({"path": file.relative_to(base).as_posix(),
                        "source_sha256": digest_bytes(data),
                        "source_bytes": len(data)})
    return entries


def edit(source, header, body, method_name):
    # Strict, tested function-level transforms. No arbitrary LLM shell output.
    tree = ast.parse(source)
    methods = [x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == method_name]
    if len(methods) != 1 or header not in source:
        return None
    needle = header + "\n" + body
    if needle not in source:
        return None
    new = source.replace(needle, header + "\n" + PRELUDE + body, 1)
    if new == source or len(new) - len(source) > 200:
        raise RuntimeError("CODE_UPGRADE_PATCH_UNEXPECTED")
    ast.parse(new)
    return new


def probe(python, source, stage, method_name, payload_kind):
    root = stage / "probe"
    root.mkdir(parents=True)
    try:
        process = subprocess.run(
            [str(python), "-I", "-B", "-c", PROBE, str(source), str(root), method_name, payload_kind],
            capture_output=True, universal_newlines=True, timeout=20,
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8",
                 "PYTHONDONTWRITEBYTECODE": "1"},
        )
        if process.returncode != 0:
            raise RuntimeError("CODE_UPGRADE_PROBE_FAIL:" + process.stderr[-300:])
        value = json.loads(process.stdout.strip())
        if set(value) != {"blocked", "escaped"}:
            raise RuntimeError("CODE_UPGRADE_PROBE_SCHEMA_INVALID")
        return value
    finally:
        # Caller owns the disposable candidate environment and may retain it.
        pass


def generate(repo, output, python=None):
    base = Path(repo).resolve()
    out = Path(output).expanduser().absolute()
    if out.is_symlink() or out == base or base in out.parents:
        raise RuntimeError("CODE_UPGRADE_OUTPUT_MUST_BE_PRIVATE_OUTSIDE_CHECKOUT")
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    if out.is_symlink() or not out.is_dir():
        raise RuntimeError("CODE_UPGRADE_OUTPUT_UNSAFE")
    modules = inventory(base)
    allowed = {rule[0] for rule in SAFE_FIXES}
    source_paths = {e["path"] for e in modules}
    if not allowed.issubset(source_paths):
        raise RuntimeError("CODE_UPGRADE_EXPECTED_MODULE_MISSING")
    candidates = []
    already_protected = []
    for path, header, body, method_name, payload_kind in SAFE_FIXES:
        original = base / path
        source = original.read_text(encoding="utf8")
        candidate = edit(source, header, body, method_name)
        if candidate is None:
            # Existing upstream fix is not a newly generated change. Verify it
            # empirically; never double-count the same repair as a new upgrade.
            with tempfile.TemporaryDirectory(dir=str(out)) as tmp:
                existing = probe(python or sys.executable, original, Path(tmp),
                                 method_name, payload_kind)
            if existing != {"blocked": True, "escaped": False}:
                raise RuntimeError("CODE_UPGRADE_UNREPAIRED_UNSUPPORTED_SOURCE:" + path)
            already_protected.append({
                "path": path, "source_sha256": digest_bytes(source.encode("utf8")),
                "negative_case_blocked": True, "new_code_edit_performed": False})
            continue
        item = {
            "path": path, "rule": "reject_atomic_symlink_parent",
            "baseline_sha256": digest_bytes(source.encode("utf8")),
            "candidate_sha256": digest_bytes(candidate.encode("utf8")),
            "changed_source": True, "private_only": True,
        }
        slot = out / ("candidate-" + str(len(candidates) + 1))
        if slot.exists() and slot.is_symlink():
            raise RuntimeError("CODE_UPGRADE_UNSAFE_SLOT")
        slot.mkdir(parents=True, exist_ok=True, mode=0o700)
        proposed = slot / original.name
        if proposed.is_symlink():
            raise RuntimeError("CODE_UPGRADE_UNSAFE_PATCH_PATH")
        proposed.write_text(candidate, encoding="utf8")
        os.chmod(proposed, 0o600)
        # Prove the real pre-existing fault and the candidate repair with
        # two independent runs, not just AST checks or strings in logs.
        with tempfile.TemporaryDirectory(dir=str(slot)) as tmp:
            scratch = Path(tmp)
            baseline = probe(python or sys.executable, original, scratch / "baseline",
                             method_name, payload_kind)
            improved = probe(python or sys.executable, proposed, scratch / "candidate",
                             method_name, payload_kind)
        item.update({"baseline": baseline, "candidate": improved,
                     "negative_case_reproduced": baseline == {
                         "blocked": False, "escaped": True},
                     "security_regression_prevented": improved == {
                         "blocked": True, "escaped": False}})
        item["measured_quality_improvement"] = (item["negative_case_reproduced"]
                                                 and item["security_regression_prevented"])
        if not item["measured_quality_improvement"]:
            raise RuntimeError("CODE_UPGRADE_NO_VERIFIABLE_IMPROVEMENT:" + path)
        candidates.append(item)
    state = {
        "schema": SCHEMA,
        "factory_python_files_scanned": len(modules),
        "module_sha256_inventory": modules,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "candidates_with_measured_improvement": sum(
            x["measured_quality_improvement"] for x in candidates),
        "private_verified_code_edits": len(candidates),
        "already_protected_source_modules": already_protected,
        "preexisting_verified_repairs": len(already_protected),
        "validated_repair_rule_coverage": len(candidates) + len(already_protected),
        "unresolved_known_security_regressions": 0,
        "production_code_promotions": 0,
        "commercial_publications": 0,
        "generation_number_proven_in_production": 0,
        "whole_code_autonomous_evolution_complete": False,
        "approval_required_for_production_merge": True,
        "unreviewed_llm_edits_admitted": False,
        "code_mutation_scope": [x[0] for x in SAFE_FIXES],
        "code_edits_across_all_modules_claimed": False,
        "upgrade_policy": "tested_allowlisted_defect_rules_no_live_mutation",
        "modules_without_proven_repair": len(modules) - len(candidates) - len(already_protected),
    }
    atomic(out / "evolution-proof.json", state)
    return state


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    state = generate(a.repo, a.out)
    print("FACTORY_CODE_SELF_EDIT_VERIFIED_CANDIDATES=" + str(state["candidate_count"]))
    print("FACTORY_CODE_SELF_EDIT_MODULES_SCANNED=" + str(state["factory_python_files_scanned"]))
    print("FACTORY_CODE_SELF_EDIT_MEASURED_BETTER=" + str(state["candidates_with_measured_improvement"]))
    print("FACTORY_CODE_SELF_EDIT_LIVE_PROMOTIONS=0")


if __name__ == "__main__":
    main()
