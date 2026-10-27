#!/usr/bin/env python3
"""Fail-closed audit: the scoped Ramadan War release must stage its full JS import closure.

Read-only. No host credentials, filesystem mutation, network access or deployment.
"""
import ast
import posixpath
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GAME = ROOT / "games" / "ramadan-war"
DEPLOY = GAME / "deploy.py"
WORKFLOW = ROOT / ".github/workflows/zomorod-ramadan-war-web-card.yml"

RELATIVE_IMPORT = re.compile(
    r"""(?:\bfrom\s*|\bimport\s*|\bimport\s*\(\s*)['"]([.]{1,2}/[^'"]+)['"]"""
)
STAGED_COPY = re.compile(
    r'^\s*timeout\s+\d+s\s+scp\s+-q\s+-F\s+"\$d/config"\s+'
    r'games/ramadan-war/(\S+)\s+"host:\$stage/incoming/([^"]+)"\s*$',
    re.MULTILINE,
)


def release_assets(source):
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "ASSETS"
            for target in node.targets
        ):
            assets = ast.literal_eval(node.value)
            if not isinstance(assets, list) or not all(
                isinstance(name, str) and name for name in assets
            ):
                raise ValueError("ASSETS must be a nonempty list of paths")
            return assets
    raise ValueError("ASSETS list missing from scoped deployer")


def audit(game_dir=GAME, deploy_source=None, workflow_source=None):
    """Return explicit errors, never mutate the working tree."""
    deploy_source = DEPLOY.read_text(encoding="utf-8") if deploy_source is None else deploy_source
    workflow_source = WORKFLOW.read_text(encoding="utf-8") if workflow_source is None else workflow_source
    assets = release_assets(deploy_source)
    errors = []
    if len(set(assets)) != len(assets):
        errors.append("duplicate asset in deploy manifest")
    for name in assets:
        if name.startswith("/") or posixpath.normpath(name) != name or name.startswith("../"):
            errors.append(f"unsafe asset path: {name}")
            continue
        path = game_dir / name
        if not path.is_file() or path.is_symlink():
            errors.append(f"missing release asset: {name}")
            continue
        if path.suffix not in {".js", ".mjs"}:
            continue
        source = path.read_text(encoding="utf-8")
        for relative in RELATIVE_IMPORT.findall(source):
            dependency = posixpath.normpath(posixpath.join(posixpath.dirname(name), relative))
            if dependency.startswith("../") or dependency.startswith("/"):
                errors.append(f"import escapes release route: {name} -> {relative}")
            elif dependency not in assets:
                errors.append(f"unbundled JS import: {name} -> {dependency}")
    copies = STAGED_COPY.findall(workflow_source)
    staged = {src: dst for src, dst in copies}
    if len(copies) != len(staged):
        errors.append("duplicate source path in staged copies")
    for name in assets:
        if staged.get(name) != name:
            errors.append(f"asset not staged at matching relative path: {name}")
    if staged.get("deploy.py") != "deploy.py":
        errors.append("scoped deployer not staged")
    if staged.get("route.htaccess") != ".htaccess":
        errors.append("route configuration not staged")
    return errors


if __name__ == "__main__":
    problems = audit()
    if problems:
        for problem in problems:
            print("RAMADAN_RELEASE_CLOSURE_FAIL:", problem)
        raise SystemExit(1)
    print("RAMADAN_RELEASE_CLOSURE=PASS; imported modules, manifest and staged copies agree")
