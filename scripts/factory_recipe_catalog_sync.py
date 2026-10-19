#!/usr/bin/env python3
"""Validate and atomically reconcile the VPS product recipe catalog.

Removed recipes are moved out of the active catalog into a private retirement
archive. Existing product packages, research tickets and QA records are untouched.
Python 3.8+, standard library only.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import time


MAKER_PATH = Path(__file__).resolve().with_name("factory_product_maker.py")
_spec = importlib.util.spec_from_file_location("saeit_recipe_catalog_maker", str(MAKER_PATH))
maker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(maker)


def _private_dir(path):
    if path.is_symlink():
        raise RuntimeError("CATALOG_PATH_SYMLINK:" + str(path))
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir() or path.is_symlink():
        raise RuntimeError("CATALOG_DIRECTORY_INVALID:" + str(path))
    os.chmod(str(path), 0o700)


def _unique_archive_path(root, slug, stamp):
    target = root / (slug + "-" + stamp)
    suffix = 0
    while target.exists():
        suffix += 1
        target = root / (slug + "-" + stamp + "-" + str(suffix))
    return target


def _atomic_manifest(path, recipes, retired):
    _private_dir(path.parent)
    fd, temporary = tempfile.mkstemp(prefix=".catalog-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({
                "schema": "saeit.factory.installed-recipes.v1",
                "active_recipes": sorted(recipes),
                "retired_this_sync": sorted(retired),
            }, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _set_private_modes(root):
    for directory, subdirs, files in os.walk(root):
        os.chmod(directory, 0o700)
        for filename in files:
            os.chmod(os.path.join(directory, filename), 0o600)


def sync_catalog(source_root, active_root, retired_root, manifest_path):
    source = Path(source_root).expanduser()
    active = Path(active_root).expanduser()
    retired = Path(retired_root).expanduser()
    manifest = Path(manifest_path).expanduser()
    for path in (source, active, retired, manifest.parent):
        if path.is_symlink():
            raise RuntimeError("CATALOG_PATH_SYMLINK:" + str(path))
    source = source.resolve()
    active = active.resolve()
    retired = retired.resolve()
    manifest = manifest.resolve()
    catalog = maker.discover_recipes(source)
    names = set(catalog)
    _private_dir(active.parent)
    _private_dir(retired)
    if active.exists() and (not active.is_dir() or active.is_symlink()):
        raise RuntimeError("ACTIVE_CATALOG_INVALID")
    if active.parent.stat().st_dev != retired.stat().st_dev:
        raise RuntimeError("CATALOG_ARCHIVE_MUST_SHARE_FILESYSTEM")

    stamp = str(time.time_ns())
    stage = Path(tempfile.mkdtemp(prefix=".recipe-catalog-stage-", dir=str(active.parent)))
    old = active.parent / (".recipe-catalog-old-" + stamp)
    archived = []
    moved_old = False
    installed_new = False
    try:
        staged_root = stage / "catalog"
        staged_root.mkdir(mode=0o700)
        for slug in sorted(names):
            shutil.copytree(source / slug, staged_root / slug, symlinks=False)
        _set_private_modes(staged_root)
        staged_catalog = maker.discover_recipes(staged_root)
        for slug in sorted(staged_catalog):
            maker.verify_recipe(staged_root / slug)

        if active.exists():
            os.replace(str(active), str(old))
            moved_old = True
        os.replace(str(staged_root), str(active))
        installed_new = True
        installed = set(maker.discover_recipes(active))
        if installed != names:
            raise RuntimeError("INSTALLED_CATALOG_MISMATCH")

        previous = set()
        if moved_old:
            old_entries = [item for item in old.iterdir() if not item.name.startswith(".")]
            if any(not item.is_dir() or item.is_symlink() for item in old_entries):
                raise RuntimeError("PREVIOUS_CATALOG_CONTAINS_UNSAFE_ENTRIES")
            previous = set(maker.discover_recipes(old)) if old_entries else set()
        removed = sorted(previous - names)
        for slug in removed:
            destination = _unique_archive_path(retired, slug, stamp)
            os.replace(str(old / slug), str(destination))
            archived.append((slug, destination))
        _atomic_manifest(manifest, installed, removed)
        if moved_old:
            shutil.rmtree(old, ignore_errors=True)
        return {"active_count": len(installed), "active_recipes": sorted(installed),
                "retired_count": len(removed), "retired_recipes": removed}
    except Exception:
        for slug, destination in reversed(archived):
            if destination.exists() and old.exists():
                os.replace(str(destination), str(old / slug))
        if installed_new and active.exists():
            failed = active.parent / (".recipe-catalog-failed-" + stamp)
            os.replace(str(active), str(failed))
        if moved_old and old.exists():
            os.replace(str(old), str(active))
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--active", required=True)
    parser.add_argument("--retired", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args(argv)
    result = sync_catalog(args.source, args.active, args.retired, args.manifest)
    print("FACTORY_ACTIVE_RECIPE_COUNT=" + str(result["active_count"]))
    print("FACTORY_RETIRED_RECIPE_COUNT=" + str(result["retired_count"]))
    for slug in result["retired_recipes"]:
        print("FACTORY_RETIRED_RECIPE=" + slug)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError) as error:
        print("FACTORY_RECIPE_CATALOG_SYNC_ERROR=" + str(error)[:500], file=__import__("sys").stderr)
        raise SystemExit(1)
