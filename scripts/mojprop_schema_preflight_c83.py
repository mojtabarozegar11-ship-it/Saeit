"""Offline source/runtime closure guard for manual Moj Prop commercial release.

No remote access, Django connection or production mutation. The installer must
call this BEFORE backing up/writing model, migration, URL or admin source.
A successful source audit does NOT prove an independently restorable database.
"""
import ast
import hashlib
from pathlib import Path


MIGRATIONS = (
    "0041_mojprop_request",
    "0042_mojprop_offer",
    "0043_mojprop_digital_inquiry",
    "0044_mojprop_acceptance_evidence",
    "0045_mojprop_delivery_evidence",
    "0046_signal_free_subscription",
    "0047_mpw_guest_email_recovery",
)
MODELS = ("MojPropRequest", "MojPropOffer", "MojPropDeliveryEvidence")
ADMINS = ("MojPropRequestAdmin", "MojPropOfferAdmin", "MojPropDeliveryEvidenceAdmin")
LEGACY_BASELINES = {
    "core/models.py": "scripts/fixtures/mojprop_legacy_request_source_c84.py",
    "core/admin.py": "scripts/fixtures/mojprop_legacy_admin_source_c84.py",
}

MODULES = (
    "core/mojprop_accessible_intake.py",
    "core/mojprop_views.py",
    "core/mojprop_receipts.py",
    "core/mojprop_catalog_contract.py",
    "core/mojprop_workflow.py",
    "core/mojprop_offer_draft.py",
    "core/mojprop_quote_contract.py",
    "core/mojprop_quote_views.py",
    "core/signal_free_models.py",
    "core/signal_free_views.py",
)


def _class_signatures(path):
    root = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result = {}
    for node in root.body:
        if not isinstance(node, ast.ClassDef):
            continue
        # Python silently replaces an earlier same-name class. A duplicate
        # Moj Prop class defeats a set-based source/upgrade review even if the
        # reviewed legacy suffix is still present byte-for-byte.
        if node.name in result and node.name.startswith("MojProp"):
            raise RuntimeError("duplicate Moj Prop class definition: " + node.name)
        result[node.name] = ast.dump(node, include_attributes=False)
    return result


def _classes(path):
    return set(_class_signatures(path))


def has_reviewed_legacy_suffix(live_root, staged_root, relative):
    """Only recognize a byte-identical previously reviewed 0041-era suffix.

    Never infer that owner-edited or unrelated classes can be overwritten.
    """
    fixture = LEGACY_BASELINES.get(relative)
    if not fixture:
        raise RuntimeError("unrecognized legacy upgrade target")
    saved = Path(staged_root) / fixture
    live = Path(live_root) / relative
    if saved.is_symlink() or not saved.is_file() or live.is_symlink() or not live.is_file():
        return False
    baseline = saved.read_text(encoding="utf-8").rstrip()
    content = live.read_text(encoding="utf-8").rstrip()
    return bool(baseline) and content.endswith(baseline)

def migration_operations_signature(path):
    """Fingerprint the WHOLE migration, ignoring only its approved DB parent.

    Comparing the operations expression alone misses malicious/unreviewed
    RunPython helper functions, imports, class options and executable top-level
    code. The installer may choose the dependency parent, but nothing else.
    """
    root = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    migrations = [n for n in root.body if isinstance(n, ast.ClassDef) and n.name == "Migration"]
    if len(migrations) != 1:
        raise RuntimeError("Moj Prop migration must contain exactly one Migration class")
    definitions = migrations[0].body
    ops = [n for n in definitions if isinstance(n, ast.Assign)
           and any(isinstance(t, ast.Name) and t.id == "operations" for t in n.targets)]
    parents = [n for n in definitions if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == "dependencies" for t in n.targets)]
    if len(ops) != 1 or len(parents) != 1:
        raise RuntimeError("Moj Prop migration missing or ambiguous operations/dependencies")
    if len(parents[0].targets) != 1 or not isinstance(parents[0].targets[0], ast.Name):
        raise RuntimeError("Moj Prop migration has unsafe dependency assignment")
    deps = parents[0].value
    if not isinstance(deps, (ast.List, ast.Tuple)):
        raise RuntimeError("Moj Prop migration dependencies must be explicit")
    core_parents = [
        entry for entry in deps.elts
        if (isinstance(entry, ast.Tuple) and len(entry.elts) == 2
            and isinstance(entry.elts[0], ast.Constant)
            and entry.elts[0].value == "core"
            and isinstance(entry.elts[1], ast.Constant)
            and isinstance(entry.elts[1].value, str))
    ]
    if len(core_parents) != 1:
        raise RuntimeError("Moj Prop migration has ambiguous core parent")
    # Only the one core predecessor is installer-selectable. Keep swappable
    # user dependencies and every other dependency byte-for-byte reviewable.
    core_parents[0].elts[1] = ast.Constant(value="__INSTALLER_SELECTED_PARENT__")
    return ast.dump(root, include_attributes=False)


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


_SOURCE_ONLY_UNRELEASED = {
    # Exact reviewed Git blob object for the not-yet-deployable Starter30
    # 0048 migration. This exception is ONLY for repository selftest and
    # cannot authorize staging or a production database change.
    "0048_mojprop_starter30_order": "4551c1bf131a1d47fe3f8894ee08a7b3cc73c337",
}


def _source_only_git_blob_matches(path, expected):
    content = path.read_bytes()
    header = ("blob " + str(len(content)) + "\0").encode("ascii")
    return hashlib.sha1(header + content).hexdigest() == expected


def check_schema_closure(live_root, staged_root, *, source_only_selftest=False):
    """Fail closed if source package and live schema migration tree conflict.

    The unreleased 0048 file is admitted ONLY for exact-byte source selftest;
    the installer calls the default mode and still refuses live 0048.
    Successful source selftest does not prove DB backup or restore.
    """
    live_root, staged_root = Path(live_root), Path(staged_root)
    if type(source_only_selftest) is not bool:
        raise RuntimeError("invalid source-only gate")
    if source_only_selftest and (
        live_root.resolve(strict=True) != staged_root.resolve(strict=True)
        or live_root.is_symlink() or staged_root.is_symlink()
    ):
        raise RuntimeError("source-only migration gate requires one identical repository")
    for path in (
        "core/models.py", "core/admin.py", "config/urls.py", "config/settings.py", *MODULES,
        *LEGACY_BASELINES.values(),
        *(f"core/migrations/{name}.py" for name in MIGRATIONS),
    ):
        src = staged_root / path
        if src.is_symlink() or not src.is_file():
            raise RuntimeError("missing or unsafe staged commercial dependency: " + path)
        if src.suffix == ".py":
            ast.parse(src.read_text(encoding="utf-8"), filename=path)

    # A staged 0048 plus an older 0047-only release tar would otherwise
    # install new Django models without their DB schema on the live tenant.
    # Source selftest is the ONLY allowed exception; real release remains
    # denied until installer, tar, schema and independent restore are reviewed.
    if not source_only_selftest:
        for migration in (staged_root / "core/migrations").glob("*.py"):
            if migration.is_symlink():
                raise RuntimeError("unsafe staged core migration symlink")
            head = migration.stem.split("_", 1)[0]
            if head.isdigit() and int(head) >= 41 and migration.stem not in set(MIGRATIONS):
                raise RuntimeError("unreviewed staged core migration: " + migration.stem)

    if not source_only_selftest:
        # Even if the release tar omits migration 0048, it must not install
        # the corresponding Django model definitions against a 0047 schema.
        new_schema = {"MojPropStarter30Order", "MojPropStarter30TxClaim"}
        hidden = _classes(staged_root / "core/models.py") & new_schema
        if hidden:
            raise RuntimeError("unreviewed staged Starter30 model schema: " + ",".join(sorted(hidden)))

    for name in MODELS:
        if name not in _classes(staged_root / "core/models.py"):
            raise RuntimeError("commercial source model is missing: " + name)
    if "MojSignalFreeSubscription" not in _classes(staged_root / "core/signal_free_models.py"):
        raise RuntimeError("free educational subscriber source model is missing")
    if "MojSignalFreeSubscriptionAdmin" not in _classes(staged_root / "core/admin.py"):
        raise RuntimeError("free educational membership admin contract missing")
    if "MOJTABA_SIGNAL_FREE_SIGNUP_ENABLED" not in (
        staged_root / "config/settings.py"
    ).read_text(encoding="utf-8"):
        raise RuntimeError("free email delivery permission flag is missing")
    for name in ADMINS:
        if name not in _classes(staged_root / "core/admin.py"):
            raise RuntimeError("commercial source admin is missing: " + name)

    for previous, name in zip(MIGRATIONS[:-1], MIGRATIONS[1:]):
        if not _dependency(staged_root / f"core/migrations/{name}.py", previous):
            raise RuntimeError("commercial migration dependency chain is incomplete: " + name)

    live_models = _classes(live_root / "core/models.py")
    live_admin = _classes(live_root / "core/admin.py")
    # Only exact, previously reviewed intake-only file suffixes can upgrade.
    # Unknown partial installs remain blocked before any file or DB write.
    for selected, required, label, relative, known_legacy in (
        (live_models.intersection(MODELS), MODELS, "model",
         "core/models.py", {"MojPropRequest"}),
        (live_admin.intersection(ADMINS), ADMINS, "admin",
         "core/admin.py", {"MojPropRequestAdmin"}),
    ):
        if selected and selected != set(required):
            if selected != known_legacy or not has_reviewed_legacy_suffix(
                live_root, staged_root, relative
            ):
                raise RuntimeError("partial Moj Prop " + label +
                                   " tree needs reviewed upgrade")

    for relative, required, label in (
        ("core/models.py", MODELS, "model"),
        ("core/admin.py", ADMINS, "admin"),
    ):
        live = _class_signatures(live_root / relative)
        staged = _class_signatures(staged_root / relative)
        if all(name in live for name in required):
            for name in required:
                if live[name] != staged[name]:
                    raise RuntimeError("existing Moj Prop " + label +
                                       " differs from reviewed source: " + name)

    # Never let a targeted 'migrate core 0046' silently unapply or rewrite
    # unrelated newer migrations in an owner-preserved application tree.
    known = set(MIGRATIONS)
    directory = live_root / "core/migrations"
    for path in directory.glob("*.py"):
        if path.is_symlink():
            raise RuntimeError("unsafe live core migration symlink")
        head = path.stem.split("_", 1)[0]
        if head.isdigit() and int(head) >= 41 and path.stem not in known:
            if not (
                source_only_selftest
                and path.stem in _SOURCE_ONLY_UNRELEASED
                and path.is_file()
                and _source_only_git_blob_matches(path, _SOURCE_ONLY_UNRELEASED[path.stem])
            ):
                raise RuntimeError("unreviewed later or conflicting core migration: " + path.stem)

    # Owner-preserved signal modules cannot be silently replaced with an
    # incompatible file merely because the filename matches.
    for module in ("core/signal_free_models.py", "core/signal_free_views.py"):
        dst = live_root / module
        src = staged_root / module
        if dst.is_symlink():
            raise RuntimeError("unsafe live signal-free module symlink: " + module)
        if dst.exists() and (not dst.is_file() or dst.read_bytes() != src.read_bytes()):
            raise RuntimeError("unreviewed live signal-free module drift: " + module)

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
