#!/usr/bin/env python3
"""Bounded read-only inventory of the actual F01 factory runtime on the VPS.

No network, database access, subprocess execution or file mutations. Prints
non-secret operational metadata (SHA-256, file counts, flags and slot names).
Python 3.8+, standard library. Suitable for SSH stdin-only diagnostics.
"""
import hashlib
import json
from pathlib import Path
import sys

PRODUCT = 'farm_enterprise_economics'
MAX_JSON = 1024 * 1024
MAX_SOURCE_FILE = 4 * 1024 * 1024
CODE_FILES = ('offline_calculator.html', 'offline_engine.js', 'offline_ui.js')
RUNTIME_NAMES = ('single-product-runtime', 'autonomous-product-runtime', '')


def read_object(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON:
        return None
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, OSError, UnicodeError):
        return None
    return value if isinstance(value, dict) else None


def source_fingerprint(path):
    result = {'exists': path.is_dir() and not path.is_symlink()}
    if not result['exists']:
        return result
    files = []
    try:
        for item in sorted(path.rglob('*')):
            rel = item.relative_to(path)
            if any(part.startswith('.') or part == '__pycache__' for part in rel.parts):
                continue
            if item.is_symlink():
                result['unsafe_symlink_present'] = True
                return result
            if item.is_file():
                if item.stat().st_size > MAX_SOURCE_FILE:
                    result['oversized_source_file'] = True
                    return result
                files.append((rel.as_posix(), item))
        digest = hashlib.sha256()
        for name, item in files:
            digest.update(name.encode('utf-8') + b'\x00')
            digest.update(item.read_bytes())
        result.update(source_sha256=digest.hexdigest(), source_file_count=len(files))
        for name in CODE_FILES:
            result[name + '_present'] = (name in [n for n, _ in files])
    except (OSError, UnicodeError):
        result['read_error'] = True
    return result


def summarize(root):
    root = Path(root)
    operations = root / 'operations'
    private = root / 'private' / 'autonomous-product-cycle'
    if any(p.is_symlink() for p in (root, operations, private)):
        raise RuntimeError('UNSAFE_FACTORY_PARENT_SYMLINK')
    slots = read_object(private / 'quality-excellence' / 'product-flow' / 'active-slots' / 'current.json')
    state = read_object(private / 'production-state.json')
    goods = private / 'digital-products' / PRODUCT
    manifest = read_object(goods / 'manufacturing_manifest.json')
    quality = read_object(goods / 'professional_quality_release_stop.json')
    output = {
        'schema': 'saeit.factory.c05.readonly-inventory.v1',
        'filesystem_root_exists': root.is_dir(),
        'single_product_runner_present': (
            (operations / 'single-product-runtime' / 'run-single-product-cycle.sh').is_file()),
        'paths': {},
        'slot': {'exists': slots is not None},
        'production': {'exists': state is not None},
        'artifact': {'exists': manifest is not None},
    }
    for name in RUNTIME_NAMES:
        key = name or 'operations-direct'
        path = operations / name / 'product_recipes' / PRODUCT if name else operations / 'product_recipes' / PRODUCT
        output['paths'][key] = source_fingerprint(path)
    if slots is not None:
        active = slots.get('active', [])
        waiting = slots.get('waiting', [])
        technical = slots.get('technical_exited', {})
        completed = technical.get(PRODUCT) if isinstance(technical, dict) else None
        output['slot'].update(
            line_id=slots.get('line_id'), capacity=slots.get('capacity'),
            active_recipe_names=[x.get('recipe') for x in active if isinstance(x, dict)]
                if isinstance(active, list) else None,
            waiting_count=len(waiting) if isinstance(waiting, list) else None,
            flagship_technical_exited=isinstance(completed, dict),
            flagship_exit_source_sha256=completed.get('source_sha256') if isinstance(completed, dict) else None,
            flagship_exit_artifact_sha256=completed.get('artifact_sha256') if isinstance(completed, dict) else None,
            commercial_release=slots.get('commercial_release'))
    if state is not None:
        output['production'].update(
            active_product_slot_recipes=state.get('active_product_slot_recipes'),
            publishable_product_count=state.get('publishable_product_count'),
            commercial_quality_review_completed=state.get('commercial_quality_review_completed'),
            registered_recipe_count=state.get('registered_recipe_count'))
    if manifest is not None:
        archive = goods / (PRODUCT + '-internal-qa.zip')
        digest = None
        if archive.is_file() and not archive.is_symlink() and archive.stat().st_size < 30 * 1024 * 1024:
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        output['artifact'].update(
            source_sha256=manifest.get('source_sha256'),
            recorded_artifact_sha256=manifest.get('artifact_sha256'),
            measured_archive_sha256=digest,
            archive_hash_matches_manifest=(digest is not None and digest == manifest.get('artifact_sha256')),
            qa_status=manifest.get('qa_status'),
            measured_successful_tests=(manifest.get('qa_measurements') or {}).get('successful_tests')
                if isinstance(manifest.get('qa_measurements'), dict) else None,
            public_listing_enabled=manifest.get('public_listing_enabled'),
            professional_quality_approved=manifest.get('professional_quality_approved'))
    output['quality_stop_exists'] = quality is not None
    output['quality_stop_release_permission'] = (
        quality.get('commercial_release_permitted_from_manufacturing') if quality else None)
    backups = operations / 'backups'
    output['f01_source_backups_count'] = (
        sum(1 for item in backups.iterdir() if item.name.startswith('f01-source-'))
        if backups.is_dir() and not backups.is_symlink() else None)
    try:
        disk = root.stat().st_dev
        output['factory_same_disk_as_operations'] = disk == operations.stat().st_dev
    except OSError:
        output['factory_same_disk_as_operations'] = None
    return output


def main():
    home = Path.home() / 'factory-runtime'
    try:
        print(json.dumps(summarize(home), sort_keys=True, ensure_ascii=True))
    except (OSError, RuntimeError, ValueError) as exc:
        print('FACTORY_C05_READONLY_ERROR=' + type(exc).__name__, file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
