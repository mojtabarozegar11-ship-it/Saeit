#!/usr/bin/env python3
"""Safely deploy the Moj Prop public-intake backend to the pinned Passenger app.

The live Saeit staging tree contains owner-preserved modules that are not present
in the current public repository snapshot. Models, admin, and URL configuration
are therefore patched additively; they are never replaced wholesale.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile


ROOT = Path("/home/zomorod2/Saeit-staging")
DOCROOT = Path("/home/zomorod2/mojplaywin.com")
BACKUP_ROOT = Path("/home/zomorod2/.mojplaywin-moj-prop-backups")
URLCONF = Path("config/urls.py")
FILES = (
    Path("core/models.py"),
    Path("core/admin.py"),
    Path("core/mojprop_views.py"),
    Path("core/migrations/0041_mojprop_request.py"),
    Path("core/migrations/0042_merge_commercefunnel_mojprop.py"),
)
ALL_FILES = (URLCONF,) + FILES
REPLACE_FILES = (
    Path("core/mojprop_views.py"),
    Path("core/migrations/0041_mojprop_request.py"),
    Path("core/migrations/0042_merge_commercefunnel_mojprop.py"),
)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_run_id(value: str) -> str:
    if not value.isdigit() or len(value) > 20:
        raise ValueError("invalid workflow run id")
    return value


def validate_commit(value: str) -> str:
    if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("invalid source commit")
    return value


def assert_regular(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"{label} is missing or unsafe: {path}")


def assert_safe_parent(path: Path, root: Path) -> None:
    current = path.parent
    while current != root:
        if current == Path("/"):
            raise RuntimeError(f"unsafe parent chain: {path}")
        if current.is_symlink():
            raise RuntimeError(f"symlink parent refused: {current}")
        current = current.parent


def compile_python(path: Path) -> None:
    compile(path.read_text(encoding="utf-8"), str(path), "exec")


def selftest(repo_root: Path) -> None:
    for relative in ALL_FILES:
        source = repo_root / relative
        assert_regular(source, "source")
        if source.suffix == ".py":
            compile_python(source)
    view = (repo_root / "core/mojprop_views.py").read_text(encoding="utf-8")
    urls = (repo_root / "config/urls.py").read_text(encoding="utf-8")
    model = (repo_root / "core/models.py").read_text(encoding="utf-8")
    required = (
        ("mojprop_intake", view),
        ("MojPropRequest", model),
        ('path("moj-prop-intake/"', urls),
        ("get_token", view),
        ("_ip_hash", view),
    )
    missing = [marker for marker, text in required if marker not in text]
    if missing:
        raise RuntimeError(f"backend selftest missing markers: {missing}")
    merge = (repo_root / "core/migrations/0042_merge_commercefunnel_mojprop.py").read_text("utf-8")
    if ("operations = []" not in merge):
        raise RuntimeError("Moj Prop migration contract does not match reviewed schema")
    print("MOJ_PROP_BACKEND_SELFTEST=PASS")


def choose_python() -> Path:
    candidates = (
        Path("/home/zomorod2/virtualenv/Saeit-staging/3.11/bin/python"),
        Path("/home/zomorod2/virtualenv/Saeit/3.11/bin/python"),
        ROOT / ".venv/bin/python",
    )
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise RuntimeError("verified Django Python runtime not found")


def backup_target(target: Path, backup: Path, manifest: dict, relative: Path) -> None:
    if target.exists():
        assert_regular(target, "live target")
        saved = backup / relative
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, saved)
        manifest[str(relative)] = {
            "existed": True,
            "sha256": digest(target),
            "mode": stat.S_IMODE(target.stat().st_mode),
        }
    else:
        manifest[str(relative)] = {"existed": False}


def atomic_replace(source: Path, target: Path, mode: int) -> None:
    assert_regular(source, "staged source")
    assert_safe_parent(target, ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.mojprop-", dir=str(target.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            with source.open("rb") as incoming:
                shutil.copyfileobj(incoming, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_write_text(target: Path, text: str, mode: int) -> None:
    assert_safe_parent(target, ROOT)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.mojprop-", dir=str(target.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def format_core_migration_dependencies(leaves, *, allow_moj_prop_parent=False) -> str:
    """Join verified core graph leaves, optionally allowing the freshly staged 0041."""
    if (type(leaves) not in (tuple, list) or not 1 <= len(leaves) <= 8
            or len(set(leaves)) != len(leaves)
            or any(type(name) is not str
                   or not re.fullmatch(r"[0-9]{4}_[A-Za-z0-9_]+", name)
                   for name in leaves)
            or ("0041_mojprop_request" in leaves and not allow_moj_prop_parent)
            or "0042_merge_commercefunnel_mojprop" in leaves):
        raise RuntimeError("Unverified or conflicting core migration graph")
    return "dependencies = [\n" + "".join(
        f'        ("core", "{name}"),\n' for name in sorted(leaves)
    ) + "    ]"


def live_core_migration_leaves(*, allow_moj_prop_parent=False):
    """Query Django's real disk graph, not an unreliable shell filename glob."""
    python = choose_python()
    probe = """
import json, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.db.migrations.loader import MigrationLoader
loader = MigrationLoader(None)
nodes = sorted(name for app, name in loader.graph.leaf_nodes("core"))
print("MOJ_PROP_CORE_LEAVES=" + json.dumps(nodes))
"""
    run = subprocess.run(
        [str(python), "-c", probe], cwd=str(ROOT), capture_output=True,
        text=True, check=True, timeout=90,
    )
    matches = [line.split("=", 1)[1] for line in run.stdout.splitlines()
               if line.startswith("MOJ_PROP_CORE_LEAVES=")]
    if len(matches) != 1:
        raise RuntimeError("Cannot verify Django core migration leaf nodes")
    leaves = json.loads(matches[0])
    format_core_migration_dependencies(
        leaves, allow_moj_prop_parent=allow_moj_prop_parent,
    )
    return tuple(leaves)


def install_migration(source: Path, target: Path) -> None:
    assert_regular(source, "staged migration")
    if target.exists() or target.is_symlink():
        raise RuntimeError("Moj Prop migration already exists; inspect before overwrite")
    leaves = live_core_migration_leaves()
    staged = source.read_text(encoding="utf-8")
    match = re.search(r"dependencies\s*=\s*\[.*?\]", staged, flags=re.S)
    if match is None or len(re.findall(r"\(\s*['\"]core['\"],", match.group())) != 1:
        raise RuntimeError("Staged migration has no unique core parent")
    content = staged[:match.start()] + format_core_migration_dependencies(leaves) + staged[match.end():]
    atomic_write_text(target, content, 0o640)
    print("MOJ_PROP_MIGRATION_PARENTS=" + ",".join(sorted(leaves)))


def install_join_migration(source: Path, target: Path) -> None:
    """Install a zero-operation 0042 merge based on the verified live graph.

    The effective cPanel app may have additional owner-preserved migrations;
    do not guess its branch history or overwrite an existing migration.
    """
    assert_regular(source, "staged join migration")
    if target.exists() or target.is_symlink():
        raise RuntimeError("Moj Prop join migration exists; inspect instead of overwriting")
    leaves = live_core_migration_leaves(allow_moj_prop_parent=True)
    if "0041_mojprop_request" not in leaves:
        raise RuntimeError("Moj Prop intake must be a live migration leaf before join")
    staged = source.read_text(encoding="utf-8")
    if ('operations = []' not in staged
            or 'class Migration' not in staged):
        raise RuntimeError("Unrecognized Moj Prop join migration payload")
    match = re.search(r"dependencies\\s*=\\s*\\[.*?\\]", staged, flags=re.S)
    if match is None:
        raise RuntimeError("Moj Prop join migration has no dependency list")
    content = (
        staged[:match.start()]
        + format_core_migration_dependencies(
            leaves, allow_moj_prop_parent=True,
        )
        + staged[match.end():]
    )
    atomic_write_text(target, content, 0o640)
    print("MOJ_PROP_JOIN_MIGRATION_PARENTS=" + ",".join(sorted(leaves)))


def patch_models(target: Path, source: Path) -> None:
    assert_regular(target, "live models")
    assert_regular(source, "staged models")
    live = target.read_text(encoding="utf-8")
    if "class MojPropRequest(" in live:
        print("MOJ_PROP_MODEL_ALREADY_PATCHED")
        return
    staged = source.read_text(encoding="utf-8")
    marker = "\nclass MojPropRequest("
    start = staged.find(marker)
    if start < 0:
        raise RuntimeError("staged MojPropRequest class is missing")
    block = staged[start + 1 :].rstrip() + "\n"
    if "class T(" not in live or "from django.db import models" not in live:
        raise RuntimeError("live models file has no safe additive-model anchors")
    mode = stat.S_IMODE(target.stat().st_mode)
    atomic_write_text(target, live.rstrip() + "\n\n" + block, mode)
    print("MOJ_PROP_MODEL_PATCH=PASS")


def patch_admin(target: Path, source: Path) -> None:
    assert_regular(target, "live admin")
    assert_regular(source, "staged admin")
    live = target.read_text(encoding="utf-8")
    if "class MojPropRequestAdmin(" in live:
        print("MOJ_PROP_ADMIN_ALREADY_PATCHED")
        return
    staged = source.read_text(encoding="utf-8")
    marker = "\nfrom .models import MojPropRequest\n"
    start = staged.find(marker)
    if start < 0:
        raise RuntimeError("staged MojPropRequest admin block is missing")
    block = staged[start + 1 :].rstrip() + "\n"
    if "from django.contrib import admin" not in live or "ModelAdmin" not in live:
        raise RuntimeError("live admin file has no safe additive-admin anchors")
    mode = stat.S_IMODE(target.stat().st_mode)
    atomic_write_text(target, live.rstrip() + "\n\n" + block, mode)
    print("MOJ_PROP_ADMIN_PATCH=PASS")


def patch_urlconf(target: Path) -> None:
    """Install only the independent first-party API outside static /moj-prop/."""
    assert_regular(target, "live URL configuration")
    source = target.read_text(encoding="utf-8")
    if 'path("moj-prop-intake/"' in source:
        print("MOJ_PROP_API_URLCONF_ALREADY_PATCHED")
        return
    if "from django.urls import" not in source or "urlpatterns" not in source:
        raise RuntimeError("live URL configuration has no safe Django path anchor")
    import_line = next(
        (line for line in source.splitlines() if line.startswith("from django.urls import ")), ""
    )
    if "path" not in import_line:
        raise RuntimeError("live URL configuration does not import path")
    block = "\n\n# Moj Prop API outside static Passenger-disabled /moj-prop/.\n"
    if "from core.mojprop_views import mojprop_intake" not in source:
        block += "from core.mojprop_views import mojprop_intake\n"
    block += ('urlpatterns.insert(0, path("moj-prop-intake/", '
              'mojprop_intake, name="mojprop_intake"))\n')
    if 'path("moj-prop/intake/"' not in source:
        block += ('urlpatterns += [path("moj-prop/intake/", '
                  'mojprop_intake, name="mojprop_intake_legacy")]\n')
    mode = stat.S_IMODE(target.stat().st_mode)
    atomic_write_text(target, source.rstrip() + block, mode)
    print("MOJ_PROP_API_URLCONF_PATCH=PASS")


def restore(backup: Path) -> None:
    manifest_path = backup / "manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise RuntimeError("backend backup manifest is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for relative in ALL_FILES:
        entry = manifest[str(relative)]
        target = ROOT / relative
        assert_safe_parent(target, ROOT)
        if entry["existed"]:
            saved = backup / relative
            assert_regular(saved, "backend backup")
            atomic_replace(saved, target, int(entry["mode"]))
        elif target.exists():
            assert_regular(target, "unexpected target")
            target.unlink()
    restart = DOCROOT / "tmp" / "restart.txt"
    if restart.is_symlink():
        raise RuntimeError("Passenger restart path is a symlink")
    restart.parent.mkdir(parents=True, exist_ok=True)
    restart.touch()
    print("MOJ_PROP_BACKEND_ROLLBACK=PASS")


def run_checked(command: list[str], cwd: Path) -> None:
    print("RUNNING=" + " ".join(command[:3]))
    subprocess.run(command, cwd=str(cwd), check=True, timeout=300)


def deploy(run_id: str, commit: str, staged_root: Path) -> None:
    run_id = validate_run_id(run_id)
    commit = validate_commit(commit)
    if ROOT.is_symlink() or not ROOT.is_dir():
        raise RuntimeError("Passenger application root is missing or redirected")
    if DOCROOT.is_symlink() or not DOCROOT.is_dir():
        raise RuntimeError("MojPlayWin document root is missing or redirected")
    assert_regular(DOCROOT / "passenger_wsgi.py", "Passenger routing file")
    if "Saeit-staging" not in (DOCROOT / "passenger_wsgi.py").read_text(
        encoding="utf-8", errors="replace"
    ):
        raise RuntimeError("Passenger routing file no longer points to Saeit-staging")
    if staged_root.is_symlink() or not staged_root.is_dir():
        raise RuntimeError("backend staging root is missing or unsafe")
    for relative in ALL_FILES:
        assert_regular(staged_root / relative, "backend staged file")

    backup = BACKUP_ROOT / run_id
    if backup.exists():
        raise RuntimeError(f"refusing to reuse backend backup: {backup}")
    backup.mkdir(parents=True, mode=0o700)
    manifest = {"run_id": run_id, "commit": commit, "files": [str(item) for item in ALL_FILES]}
    for relative in ALL_FILES:
        backup_target(ROOT / relative, backup, manifest, relative)
    (backup / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    try:
        for relative in REPLACE_FILES:
            target = ROOT / relative
            if relative == Path("core/migrations/0041_mojprop_request.py"):
                install_migration(staged_root / relative, target)
            elif relative == Path("core/migrations/0042_merge_commercefunnel_mojprop.py"):
                install_join_migration(staged_root / relative, target)
            else:
                current_mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o640
                atomic_replace(staged_root / relative, target, current_mode)
                if digest(target) != digest(staged_root / relative):
                    raise RuntimeError(f"post-copy hash mismatch: {relative}")
        patch_models(ROOT / Path("core/models.py"), staged_root / Path("core/models.py"))
        patch_admin(ROOT / Path("core/admin.py"), staged_root / Path("core/admin.py"))
        patch_urlconf(ROOT / URLCONF)

        python = choose_python()
        run_checked([str(python), "manage.py", "check", "--deploy"], ROOT)
        run_checked([str(python), "manage.py", "migrate", "--noinput"], ROOT)
        run_checked([str(python), "manage.py", "collectstatic", "--noinput"], ROOT)

        restart = DOCROOT / "tmp" / "restart.txt"
        if restart.is_symlink():
            raise RuntimeError("Passenger restart path is a symlink")
        restart.parent.mkdir(parents=True, exist_ok=True)
        restart.touch()
        print("MOJ_PROP_BACKEND_DEPLOY=PASS")
        print("MOJ_PROP_BACKEND_COMMIT=" + commit)
        print("MOJ_PROP_BACKUP=" + str(backup))
    except Exception:
        restore(backup)
        raise


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        raise SystemExit("usage: script.py selftest [repo_root] | deploy RUN_ID COMMIT STAGED_ROOT | rollback RUN_ID")
    action = argv[1]
    if action == "selftest":
        selftest(Path(argv[2]).resolve() if len(argv) > 2 else Path.cwd())
        return 0
    if action == "deploy" and len(argv) == 5:
        deploy(argv[2], argv[3], Path(argv[4]).resolve())
        return 0
    if action == "rollback" and len(argv) == 3:
        restore(BACKUP_ROOT / validate_run_id(argv[2]))
        return 0
    raise SystemExit("invalid arguments")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))