#!/usr/bin/env python3
"""Read-only cPanel symlink dependency inventory for MojPlayWin primary roots.

No file contents, database, orders, target names or paths are printed.
No links are followed during traversal; no host files are created or changed.
"""
from __future__ import annotations

from collections import Counter
import json
import os
import posixpath
import pwd
from pathlib import Path, PurePosixPath

HOME = Path("/home/zomorod2")
ROOTS = ("Saeit-staging", "mojplaywin.com")
MAX_WALK_ENTRIES = 200_000


def role_for_target(source_relative, link_target):
    """Coarse location class only, never a path or filename."""
    if not isinstance(link_target, str) or not link_target:
        return "invalid_target"
    if link_target.startswith("/"):
        try:
            rel = PurePosixPath(link_target).relative_to(str(HOME))
        except ValueError:
            return "outside_account"
        candidate = str(rel)
    else:
        candidate = posixpath.normpath(posixpath.join(
            *PurePosixPath(source_relative).parts[:-1], link_target))
    parts = PurePosixPath(candidate).parts
    if not parts or parts[0] == "..":
        return "outside_account"
    if parts[0] in ROOTS:
        return "backed_primary_roots"
    if parts[0] == "virtualenv":
        return "python_runtime_dependency"
    if parts[0] in ("Saeit", "public_html"):
        return "alternative_site_code_root"
    if parts[0] in ("tmp", "logs", ".local", ".cache"):
        return "ephemeral_runtime_path"
    return "other_unbacked_account_root"



def target_kind(resolved):
    """A fixed type label; never return any part of the target path."""
    if not resolved.exists():
        return "missing"
    if resolved.is_dir():
        return "directory"
    if resolved.is_file():
        return "regular_file"
    return "other"


# Marker labels are fixed, not user-controlled source or target names.
# Inspect only direct child metadata; never read target file contents.
MARKER_NAMES = {
    "python_project": frozenset(("manage.py", "requirements.txt", "pyproject.toml", "pipfile", "setup.py")),
    "javascript_project": frozenset(("package.json", "vite.config.ts", "next.config.js", "next.config.mjs")),
    "php_project": frozenset(("composer.json", "wp-config.php", "artisan")),
    "website_media": frozenset(("static", "media", "uploads", "assets", "images")),
    "repository_metadata": frozenset((".git",)),
    "private_configuration_or_backup": frozenset((".env", ".env.production", "backup", "backups", "dump", "dumps")),
}


def alias_purpose(source_relative):
    """Return a label from a controlled vocabulary, never the link's name."""
    name = PurePosixPath(source_relative).name.casefold()
    if name in ("static", "media", "uploads", "assets", "images"):
        return name + "_alias"
    if name in ("venv", ".venv", "virtualenv", "site-packages"):
        return "python_runtime_alias"
    if name in ("src", "core", "templates", "app", "modules", "plugins"):
        return "project_code_alias"
    if name in ("backup", "backups", "dump", "dumps"):
        return "backup_alias"
    return "unclassified_alias"


def target_site_affinity(resolved, home=HOME):
    """Classify account-relative destination *identity hints*, not site ownership.

    Only fixed labels and nesting depth leave the host, never directory names.
    """
    try:
        rel = resolved.relative_to(home.resolve(strict=True))
    except ValueError:
        return {"hint": "outside_account", "depth": 0}
    parts = tuple(p.casefold() for p in rel.parts)
    if not parts:
        return {"hint": "entire_account_disallowed", "depth": 0}
    if parts[0] in ("saeit", "saeit-staging", "mojplaywin.com"):
        role = "known_site_named_root"
    elif any(p in ("mojplaywin", "mpw", "mojplaywin-assets", "mpw-static",
                       "mpw-media") for p in parts[:2]):
        role = "site_brand_labeled"
    elif parts[0] in ("staticfiles", "static", "media", "assets", "uploads"):
        role = "generic_asset_root_unverified"
    else:
        role = "unverified_account_root"
    return {"hint": role, "depth": min(len(parts), 4)}


def direct_child_metadata(directory, *, max_entries=10_000):
    """Only shallow directory-entry metadata. Does not open files or follow links.

    Every returned string comes from a fixed vocabulary; private entry names,
    directory paths, file bytes and customer records cannot enter the output.
    """
    counts = Counter()
    marks = set()
    try:
        with os.scandir(directory) as children:
            for i, child in enumerate(children, 1):
                if i > max_entries:
                    raise RuntimeError("TARGET_DIRECTORY_SCAN_LIMIT")
                lower_name = child.name.casefold()
                for category, names in MARKER_NAMES.items():
                    if lower_name in names:
                        marks.add(category)
                if child.is_symlink():
                    counts["symbolic_link"] += 1
                elif child.is_dir(follow_symlinks=False):
                    counts["directory"] += 1
                elif child.is_file(follow_symlinks=False):
                    counts["regular_file"] += 1
                else:
                    counts["other"] += 1
    except OSError:
        raise RuntimeError("TARGET_DIRECTORY_METADATA_UNREADABLE") from None
    return {
        "direct_child_count": sum(counts.values()),
        "direct_child_types": dict(sorted(counts.items())),
        "fixed_marker_categories": sorted(marks),
        "scope": "one_level_metadata_only",
    }


def bounded_asset_tree_metadata(directory, *, max_entries=150_000):
    """Inspect *metadata* of link-reachable tree without dereferencing nested links.

    This is NOT content inspection, malware scanning, privacy certification,
    an approved backup allowlist, or evidence of site ownership.
    """
    import stat

    shapes = Counter()
    total_bytes = total_entries = hidden_entries = 0
    web = {".css", ".js", ".mjs", ".html", ".svg", ".woff", ".woff2",
           ".ttf", ".otf", ".ico", ".map"}
    media = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif",
             ".pdf", ".mp3", ".mp4", ".webm", ".wav", ".ogg"}
    source = {".py", ".php", ".sh", ".rb", ".go", ".java", ".jsx",
              ".tsx", ".ts", ".vue", ".yml", ".yaml", ".toml"}
    sensitive = {".pem", ".key", ".p12", ".pfx", ".sql", ".sqlite",
                 ".sqlite3", ".db", ".bak", ".gpg", ".age"}
    secret_names = {".env", ".env.production", ".htpasswd", "id_rsa",
                    "wp-config.php", "secrets.yml", "secrets.yaml"}

    def walk_error(_error):
        raise RuntimeError("TARGET_TREE_METADATA_UNREADABLE")

    for dirname, dirs, files in os.walk(
            directory, followlinks=False, onerror=walk_error):
        total_entries += len(dirs) + len(files)
        if total_entries > max_entries:
            raise RuntimeError("TARGET_TREE_SCAN_LIMIT")
        for entry in dirs + files:
            if entry.startswith("."):
                hidden_entries += 1
            p = Path(dirname) / entry
            try:
                st = p.lstat()  # No symlink target opened or followed.
            except OSError:
                raise RuntimeError("TARGET_TREE_METADATA_UNREADABLE") from None
            if stat.S_ISLNK(st.st_mode):
                shapes["nested_symlink"] += 1
            elif stat.S_ISDIR(st.st_mode):
                shapes["directory"] += 1
            elif stat.S_ISREG(st.st_mode):
                total_bytes += st.st_size
                lower = entry.casefold()
                suffix = p.suffix.casefold()
                if lower in secret_names or suffix in sensitive:
                    shapes["sensitive_or_backup_file_shape"] += 1
                elif suffix in (".gz", ".br"):
                    # Presence of an uncompressed sidecar is only a metadata
                    # hint. We never open or decompress either file.
                    original = p.with_suffix("")
                    if original.is_file() and not original.is_symlink() and original.suffix.casefold() in web:
                        shapes["precompressed_web_sidecar_shape"] += 1
                    else:
                        shapes["other_gzip_or_brotli_shape"] += 1
                elif suffix in (".zip", ".tar", ".7z"):
                    shapes["download_archive_shape"] += 1
                elif suffix in (".json", ".xml", ".txt", ".md", ".csv", ".webmanifest"):
                    shapes["generic_text_or_data_file_shape"] += 1
                elif suffix in source:
                    shapes["source_code_file_shape"] += 1
                elif suffix in web:
                    shapes["web_asset_file_shape"] += 1
                elif suffix in media:
                    shapes["media_file_shape"] += 1
                else:
                    shapes["other_regular_file_shape"] += 1
            else:
                shapes["special_file"] += 1
    size_band = ("below_100_mib" if total_bytes < 100 * 1024**2
                 else "below_1_gib" if total_bytes < 1024**3
                 else "below_10_gib" if total_bytes < 10 * 1024**3
                 else "10_gib_or_more")
    return {
        "walk_completed_without_following_links": True,
        "entry_count": total_entries,
        "entry_shapes": dict(sorted(shapes.items())),
        "hidden_entry_count": hidden_entries,
        "size_band": size_band,
        "file_contents_read": False,
    }


def allowed_private_target_metadata(resolved, home=HOME):
    """Explicitly reject other tenants, entire account home, and other owners."""
    account_home = home.resolve(strict=True)
    target = resolved.resolve(strict=True)
    if target == account_home or account_home not in target.parents:
        return {"inspection": "rejected_outside_scoped_account"}
    if not target.is_dir() or target.stat().st_uid != os.geteuid():
        return {"inspection": "rejected_type_or_owner"}
    return {"inspection": "one_level_completed",
            "metadata": direct_child_metadata(target),
            "tree_metadata": bounded_asset_tree_metadata(target)}


def inspect():
    result = {
        "classification": "MPW_LIVE_SYMLINK_DEPENDENCIES_READ_ONLY",
        "production_modified": False, "database_read": False,
        "orders_created": 0, "payments_created": 0,
        "paths_or_targets_logged": False,
        "archive_data_read": False,
        "all_primary_roots_pinned": True,
    }
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        raise RuntimeError("UNEXPECTED_OWNER")
    wsgi = HOME / "mojplaywin.com" / "passenger_wsgi.py"
    if (not wsgi.is_file() or wsgi.is_symlink() or
            "APP='/home/zomorod2/Saeit-staging'" not in
            wsgi.read_text("utf8", "replace")):
        raise RuntimeError("PASSENGER_PIN_MISSING")
    for name in ROOTS:
        p = HOME / name
        if not p.is_dir() or p.is_symlink() or p.resolve() != p:
            raise RuntimeError("PRIMARY_ROOT_DRIFT")
    categories, resolution, target_types = Counter(), Counter(), Counter()
    links = entries = 0
    external_dependencies = []
    def fail_walk(_error):
        raise RuntimeError("SCAN_UNREADABLE")
    for name in ROOTS:
        for directory, dirs, files in os.walk(
                HOME / name, followlinks=False, onerror=fail_walk):
            entries += len(dirs) + len(files)
            if entries > MAX_WALK_ENTRIES:
                raise RuntimeError("INVENTORY_LIMIT")
            for entry in dirs + files:
                path = Path(directory) / entry
                if not path.is_symlink():
                    continue
                links += 1
                try:
                    raw_target = os.readlink(path)
                    role = role_for_target(str(path.relative_to(HOME)), raw_target)
                    resolved = path.resolve(strict=False)
                    if path.exists():
                        owner = resolved.stat().st_uid == os.geteuid()
                        state = "present_same_owner" if owner else "present_other_owner"
                    else:
                        state = "dangling"
                    categories[role] += 1
                    resolution[role + "_" + state] += 1
                    target_types[role + "_" + target_kind(resolved)] += 1
                    if role != "backed_primary_roots":
                        external_dependencies.append({
                            "source_primary_root": name,
                            "source_depth_within_root": min(len(path.relative_to(HOME / name).parts), 5),
                            "alias_purpose": alias_purpose(str(path.relative_to(HOME))),
                            "destination_role": role,
                            "target_site_affinity": target_site_affinity(resolved),
                            "target_inspection": allowed_private_target_metadata(resolved),
                        })
                except (OSError, RuntimeError, ValueError):
                    categories["unreadable"] += 1
    result.update({
        "examined_entries_capped": entries,
        "total_symlinks": links,
        "dependency_classes": dict(sorted(categories.items())),
        "dependency_resolution": dict(sorted(resolution.items())),
        "dependency_target_types": dict(sorted(target_types.items())),
        "external_dependency_metadata": external_dependencies,
    })
    return result


if __name__ == "__main__":
    print("MPW_LIVE_LINK_INVENTORY=" + json.dumps(inspect(), sort_keys=True))
