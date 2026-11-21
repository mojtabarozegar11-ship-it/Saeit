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
MAX_SOURCE_MODULES = 200
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


def _core_imports(tree, current_module):
    """Return local imports, correctly resolving relative Python packages."""
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                parts = current_module.split(".")[:-node.level]
                if node.module:
                    resolved = ".".join(parts + [node.module])
                    if resolved.startswith("core."):
                        imports.add(resolved)
                else:
                    # `from . import factory_tool_pack` has no node.module.
                    # Without this branch an absent dependency is silently skipped.
                    imports.update(
                        ".".join(parts + [alias.name])
                        for alias in node.names
                        if alias.name != "*" and ".".join(parts).startswith("core")
                    )
            elif node.level == 0 and node.module:
                if node.module.startswith("core."):
                    imports.add(node.module)
                elif node.module == "core":
                    # `from core import factory_tool_pack` is also a local import.
                    imports.update("core." + alias.name for alias in node.names
                                   if alias.name != "*")
        elif isinstance(node, ast.Import):
            for name in node.names:
                if name.name.startswith("core."):
                    imports.add(name.name)
    return imports


def _model_imported_symbols(tree, current_module):
    symbols = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if node.level:
            parts = current_module.split(".")[:-node.level]
            module = ".".join(parts + [node.module])
        else:
            module = node.module
        if module == "core.models":
            symbols.update(alias.name for alias in node.names if alias.name != "*")
    return symbols


def _declared_module_symbols(tree):
    symbols = set()
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.add(node.name)
        elif isinstance(node, ast.Assign):
            symbols.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            symbols.add(node.target.id)
    return symbols


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
    """Perform bounded, read-only source-import traversal; never load Python modules."""
    root = Path(root)
    blockers = []
    trees = {}
    modules_checked = set()
    model_imports = set()
    pending = [
        ("core.management.commands.factory_product_step", ENTRYPOINTS[0]),
        ("core.factory_worker_compat", ENTRYPOINTS[1]),
    ]
    visited = set()
    checked_entrypoints = 0
    while pending:
        module, relative = pending.pop(0)
        if module in visited:
            continue
        if len(visited) >= MAX_SOURCE_MODULES:
            blockers.append({"code": "SOURCE_GRAPH_LIMIT", "component": module})
            break
        visited.add(module)
        if module not in {"core.management.commands.factory_product_step",
                          "core.factory_worker_compat"} and not _module_present(root, module):
            blockers.append({"code": "LOCAL_IMPORT_MISSING", "component": module})
            continue
        if not (root / relative).is_file() and (root / relative / "__init__.py").is_file():
            relative = relative / "__init__.py"
        tree = _parse(root / relative, blockers, relative.as_posix())
        if tree is None:
            continue
        if module in {"core.management.commands.factory_product_step",
                      "core.factory_worker_compat"}:
            checked_entrypoints += 1
        trees[module] = tree
        imports = _core_imports(tree, module)
        modules_checked.update(imports)
        model_imports.update(_model_imported_symbols(tree, module))
        for dependency in sorted(imports):
            if dependency not in visited:
                local = Path(*dependency.split("."))
                candidate = local.with_suffix(".py")
                if not (root / candidate).is_file():
                    candidate = local
                pending.append((dependency, candidate))

    model_tree = trees.get("core.models")
    if model_tree is None:
        model_tree = _parse(root / MODEL, blockers, MODEL.as_posix())
    if model_tree is not None:
        declared = _declared_module_symbols(model_tree)
        for symbol in sorted(model_imports - declared):
            blockers.append({"code": "MODEL_SYMBOL_MISSING",
                             "component": "core.models." + symbol})
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
        "checked_entrypoints": checked_entrypoints,
        "checked_local_imports": len(modules_checked),
        "checked_source_modules": len(trees),
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
