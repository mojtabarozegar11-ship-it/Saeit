#!/usr/bin/env python3
"""Read-only, no-Django preflight of the factory worker's source contract.

This does NOT inspect the VPS, the database or the native factory slot. A clean
source result must never be interpreted as production readiness.
"""

import argparse
import ast
import json
from pathlib import Path


SCHEMA = "saeit.factory.source-contract-audit.v1"
ENTRYPOINTS = (
    Path("core/management/commands/factory_product_step.py"),
    Path("core/factory_worker_compat.py"),
)
MODEL = Path("core/models.py")
REQUIRED_TASK_FIELDS = (
    "factory_run", "product", "environment", "next_retry_at",
)


def _parse(path, blockers, code):
    if not path.is_file():
        blockers.append({"code": "SOURCE_MISSING", "component": code})
        return None
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        blockers.append({"code": "SOURCE_UNREADABLE", "component": code,
                         "reason": type(exc).__name__})
        return None


def _core_imports(tree):
    """Return only the project's local Python module import dependencies."""
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level == 1 and node.module:
                imports.add("core." + node.module)
            elif node.level == 0 and node.module:
                if node.module.startswith("core."):
                    imports.add(node.module)
        elif isinstance(node, ast.Import):
            for name in node.names:
                if name.name.startswith("core."):
                    imports.add(name.name)
    return imports


def _module_present(root, module):
    relative = Path(*module.split("."))
    return ((root / relative.with_suffix(".py")).is_file()
            or (root / relative / "__init__.py").is_file())


def _declared_fields(tree, class_name):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            fields = set()
            for statement in node.body:
                if isinstance(statement, ast.Assign):
                    fields.update(target.id for target in statement.targets
                                  if isinstance(target, ast.Name))
                elif isinstance(statement, ast.AnnAssign):
                    if isinstance(statement.target, ast.Name):
                        fields.add(statement.target.id)
            return fields
    return None


def audit(root):
    """Perform only static, explicit-file reads and return deterministic JSON."""
    root = Path(root)
    blockers = []
    trees = {}
    modules_checked = set()
    for relative in ENTRYPOINTS:
        tree = _parse(root / relative, blockers, relative.as_posix())
        if tree is not None:
            trees[relative.as_posix()] = tree
            modules_checked.update(_core_imports(tree))

    for module in sorted(modules_checked):
        if not _module_present(root, module):
            blockers.append({"code": "LOCAL_IMPORT_MISSING", "component": module})

    model_tree = _parse(root / MODEL, blockers, MODEL.as_posix())
    if model_tree is not None:
        fields = _declared_fields(model_tree, "AgentTask")
        if fields is None:
            blockers.append({"code": "MODEL_CLASS_MISSING", "component": "AgentTask"})
        else:
            for field in REQUIRED_TASK_FIELDS:
                if field not in fields:
                    blockers.append({"code": "MODEL_FIELD_MISSING",
                                     "component": "AgentTask." + field})

        product_fields = _declared_fields(model_tree, "Product")
        if product_fields is None or "metadata" not in product_fields:
            blockers.append({"code": "MODEL_FIELD_MISSING",
                             "component": "Product.metadata"})

    blockers.sort(key=lambda item: (item["code"], item["component"]))
    return {
        "schema": SCHEMA,
        "mode": "source_only_read_only",
        "live_vps_verified": False,
        "production_ready": False,
        "status": "blocked" if blockers else "source_contract_present",
        "checked_entrypoints": len(trees),
        "checked_local_imports": len(modules_checked),
        "blockers": blockers,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path,
                        default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    result = audit(args.root)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 2 if result["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
