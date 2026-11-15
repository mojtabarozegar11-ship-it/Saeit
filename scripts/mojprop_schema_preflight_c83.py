"""Offline source/runtime closure guard for manual Moj Prop commercial release.

No remote access, Django connection or production mutation. The installer must
call this BEFORE backing up/writing model, migration, URL or admin source.
A successful source audit does NOT prove an independently restorable database.
"""
import ast
from pathlib import Path


MIGRATIONS = (
    "0041_mojprop_request",
    "0042_mojprop_offer",
    "0043_mojprop_digital_inquiry",
    "0044_mojprop_acceptance_evidence",
    "0045_mojprop_delivery_evidence",
)
MODELS = ("MojPropRequest", "MojPropOffer", "MojPropDeliveryEvidence")
ADMINS = ("MojPropRequestAdmin", "MojPropOfferAdmin", "MojPropDeliveryEvidenceAdmin")
MODULES = (
    "core/mojprop_views.py",
    "core/mojprop_receipts.py",
    "core/mojprop_catalog_contract.py",
    "core/mojprop_workflow.py",
    "core/mojprop_offer_draft.py",
    "core/mojprop_quote_contract.py",
    "core/mojprop_quote_views.py",
)


def _classes(path):
    root = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {node.name for node in root.body if isinstance(node, ast.ClassDef)}


def migration_operations_signature(path):
    """Compare migration operations, ignoring only installer-selected parent."""
    root = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    migrations = [n for n in root.body if isinstance(n, ast.ClassDef) and n.name == "Migration"]
    if len(migrations) != 1:
        raise RuntimeError("Moj Prop migration must contain exactly one Migration class")
    ops = [n.value for n in migrations[0].body if isinstance(n, ast.Assign)
           and any(isinstance(t, ast.Name) and t.id == "operations" for t in n.targets)]
    if len(ops) != 1:
        raise RuntimeError("Moj Prop migration missing or ambiguous operations")
    return ast.dump(ops[0], include_attributes=False)


def _dependency(path, name):
    root = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    cls = next(n for n in root.body if isinstance(n, ast.ClassDef) and n.name == "Migration")
    for n in cls.body:
        if isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "dependencies" for t in n.targets
        ):
            pairs = [
                v for v in ast.walk(n.value)
                if isinstance(v, ast.Tuple) and len(v.elts) == 2
                and isinstance(v.elts[0], ast.Constant) and v.elts[0].value == "core"
                and isinstance(v.elts[1], ast.Constant)
                and v.elts[1].value == name
            ]
            return len(pairs) == 1
    return False


def check_schema_closure(live_root, staged_root):
    """Fail closed if source package and live schema migration tree conflict.

    Returns a source-only inventory; never claims a DB dump/restore is verified.
    """
    live_root, staged_root = Path(live_root), Path(staged_root)
    for path in (
        "core/models.py", "core/admin.py", "config/urls.py", *MODULES,
        *(f"core/migrations/{name}.py" for name in MIGRATIONS),
    ):
        src = staged_root / path
        if src.is_symlink() or not src.is_file():
            raise RuntimeError("missing or unsafe staged commercial dependency: " + path)
        if src.suffix == ".py":
            ast.parse(src.read_text(encoding="utf-8"), filename=path)

    for name in MODELS:
        if name not in _classes(staged_root / "core/models.py"):
            raise RuntimeError("commercial source model is missing: " + name)
    for name in ADMINS:
        if name not in _classes(staged_root / "core/admin.py"):
            raise RuntimeError("commercial source admin is missing: " + name)

    for previous, name in zip(MIGRATIONS[:-1], MIGRATIONS[1:]):
        if not _dependency(staged_root / f"core/migrations/{name}.py", previous):
            raise RuntimeError("commercial migration dependency chain is incomplete: " + name)

    live_models = _classes(live_root / "core/models.py")
    live_admin = _classes(live_root / "core/admin.py")
    # A partially installed model/admin tree cannot be upgraded by appending
    # all staged classes or by relying on the old intake-only early return.
    for selected, required, label in (
        (live_models.intersection(MODELS), MODELS, "model"),
        (live_admin.intersection(ADMINS), ADMINS, "admin"),
    ):
        if selected and selected != set(required):
            raise RuntimeError("partial Moj Prop " + label + " tree needs reviewed upgrade")

    # Never let a targeted 'migrate core 0045' silently unapply or rewrite
    # unrelated newer migrations in an owner-preserved application tree.
    known = set(MIGRATIONS)
    directory = live_root / "core/migrations"
    for path in directory.glob("*.py"):
        if path.is_symlink():
            raise RuntimeError("unsafe live core migration symlink")
        head = path.stem.split("_", 1)[0]
        if head.isdigit() and int(head) >= 41 and path.stem not in known:
            raise RuntimeError("unreviewed later or conflicting core migration: " + path.stem)

    for name in MIGRATIONS:
        dst = live_root / f"core/migrations/{name}.py"
        src = staged_root / f"core/migrations/{name}.py"
        if dst.is_symlink():
            raise RuntimeError("unsafe migration symlink: " + name)
        if dst.exists():
            if not dst.is_file() or migration_operations_signature(dst) != migration_operations_signature(src):
                raise RuntimeError("existing live migration differs from reviewed source: " + name)

    return {
        "source_chain": list(MIGRATIONS),
        "modules": len(MODULES),
        "models": len(MODELS),
        "admins": len(ADMINS),
        "live_db_restored": False,
        "manual_deploy_authorized": False,
    }
