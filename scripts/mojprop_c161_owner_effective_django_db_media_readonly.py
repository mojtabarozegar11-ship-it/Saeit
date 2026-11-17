#!/usr/bin/env python3
"""C161: effective staging Django DB engine + MEDIA_ROOT metadata, no secrets.

Identifies the configured backend without opening a DB connection, touching a
customer record, calling a view, copying media, creating a backup, or printing
config credentials / database names / connection hosts / filesystem paths.
This does NOT prove the active Passenger worker loads this staging tree.
Private .env may be read *by Django settings loader in-process*; no values
are emitted. Source file paths are fixed, metadata-only and no-follow.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import pwd
import stat
import sys

OWNER = "zomorod2"
HOME = Path("/home/zomorod2")
ROOT = HOME / "Saeit-staging"
CONFIG = ROOT / "config"
SETTINGS_FILE = CONFIG / "settings.py"
MAX_DIRECT_ENTRIES = 64

EMPTY_SCAN = {
    "bounded_direct_scan_complete": False,
    "direct_files": 0, "direct_subdirectories": 0,
    "direct_file_bytes_observed": 0, "recursive_media_scope_proven": False,
    "media_file_content_read": False,
}


def owned_regular(path: Path, uid: int, *, directory: bool) -> bool:
    try:
        m = path.lstat()
    except OSError:
        return False
    if m.st_uid != uid or m.st_mode & 0o022:
        return False
    if directory:
        return stat.S_ISDIR(m.st_mode)
    return stat.S_ISREG(m.st_mode) and m.st_nlink == 1


def staging_source_safe(uid: int) -> bool:
    return all((
        owned_regular(HOME, uid, directory=True),
        owned_regular(ROOT, uid, directory=True),
        owned_regular(CONFIG, uid, directory=True),
        owned_regular(SETTINGS_FILE, uid, directory=False),
    ))


def classify_database(settings: object) -> dict:
    out = {
        "configured": False, "engine": "unknown",
        "name_configured": False, "host_class": "unknown",
        "connection_opened": False, "credentials_exposed": False,
    }
    try:
        connections = getattr(settings, "DATABASES", None)
        if type(connections) is not dict or type(connections.get("default")) is not dict:
            return out
        db = connections["default"]
        engine = db.get("ENGINE")
        out["configured"] = True
        out["engine"] = {
            "django.db.backends.mysql": "mysql",
            "django.db.backends.postgresql": "postgresql",
            "django.db.backends.sqlite3": "sqlite",
            "django.db.backends.oracle": "oracle",
        }.get(engine, "other_or_unknown")
        value = db.get("NAME")
        out["name_configured"] = bool(value) and value != ":memory:"
        host = db.get("HOST")
        if type(host) is str and host in ("", "localhost", "127.0.0.1", "::1"):
            out["host_class"] = "local_or_default"
        elif type(host) is str and host.startswith("/"):
            out["host_class"] = "local_socket_or_path"
        else:
            out["host_class"] = "remote_or_unknown"
    except (TypeError, ValueError):
        return out
    return out


def storage_type(settings: object) -> str:
    try:
        storages = getattr(settings, "STORAGES", None)
        backend = (storages.get("default", {}).get("BACKEND")
                   if type(storages) is dict else None)
        if backend == "django.core.files.storage.FileSystemStorage":
            return "django_filesystem_storage"
        if type(backend) is str and backend:
            return "other_or_external_storage"
    except (TypeError, ValueError):
        pass
    return "unverified"


def class_media_path(settings: object, uid: int) -> dict:
    out = {
        "root_state": "unknown",
        "within_owner_home": False,
        "within_staging": False,
        "backend_kind": storage_type(settings),
        "metadata": dict(EMPTY_SCAN),
        "media_root_contents_opened": False,
        "complete_media_inventory_proven": False,
    }
    try:
        value = getattr(settings, "MEDIA_ROOT", None)
        if value in (None, "", "."):
            out["root_state"] = "not_configured"
            return out
        if not isinstance(value, (str, Path)):
            out["root_state"] = "unsupported_setting"
            return out
        candidate = Path(value)
        if not candidate.is_absolute():
            out["root_state"] = "relative_path_unverified"
            return out
        if HOME not in candidate.parents or candidate == ROOT:
            out["root_state"] = "outside_or_overbroad_owner_home"
            return out
        out["within_owner_home"] = True
        out["within_staging"] = ROOT in candidate.parents
        # Check all directory ancestors from fixed HOME; never resolve symlinks.
        parent = candidate.parent
        while parent != HOME:
            if HOME not in parent.parents or not owned_regular(parent, uid, directory=True):
                out["root_state"] = "unsafe_or_missing_ancestor"
                return out
            parent = parent.parent
        if not owned_regular(candidate, uid, directory=True):
            try:
                candidate.lstat()
                out["root_state"] = "unsafe_root"
            except FileNotFoundError:
                out["root_state"] = "missing_root"
            except OSError:
                out["root_state"] = "unavailable"
            return out
        out["root_state"] = "owner_safe_directory"
        files = dirs = total_bytes = count = 0
        with os.scandir(candidate) as entries:
            for entry in entries:
                count += 1
                if count > MAX_DIRECT_ENTRIES:
                    return out
                try:
                    info = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                if info.st_uid != uid or info.st_mode & 0o022:
                    continue
                if stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                    files += 1
                    total_bytes += max(0, info.st_size)
                elif stat.S_ISDIR(info.st_mode):
                    dirs += 1
        out["metadata"] = {
            **EMPTY_SCAN,
            "bounded_direct_scan_complete": True,
            "direct_files": files,
            "direct_subdirectories": dirs,
            "direct_file_bytes_observed": total_bytes,
        }
    except (OSError, TypeError, ValueError):
        out["root_state"] = "unavailable"
    return out


def report() -> dict:
    out = {
        "schema": "mojprop.cpanel.effective_django_db_media.readonly.c161.v1",
        "owner_identity_verified": False, "staging_source_safe": False,
        "read_only": True, "django_settings_loaded": False,
        "database": classify_database(None),
        "media": class_media_path(None, -1),
        "db_connection_opened": False, "db_dump_created": False,
        "database_name_or_credentials_emitted": False,
        "owner_secret_values_emitted": False,
        "source_settings_loaded_into_memory": False,
        "actual_live_passenger_worker_parity_proven": False,
        "offhost_db_media_backup_verified": False,
        "full_app_db_media_restore_verified": False,
        "production_release_authorized": False,
        "new_financial_commitment": False,
    }
    try:
        if pwd.getpwuid(os.geteuid()).pw_name != OWNER:
            return out
        out["owner_identity_verified"] = True
        if not staging_source_safe(os.geteuid()):
            return out
        out["staging_source_safe"] = True
        os.chdir(ROOT)
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
        # No django.setup() and no DB connection: evaluation can read .env
        # as part of Django configuration, but no sensitive value is printed.
        from django.conf import settings
        out["source_settings_loaded_into_memory"] = True
        _ = settings.DATABASES
        out["django_settings_loaded"] = True
        out["database"] = classify_database(settings)
        out["media"] = class_media_path(settings, os.geteuid())
    except (OSError, ImportError, KeyError, TypeError, ValueError,
            RuntimeError, AttributeError):
        pass
    return out


if __name__ == "__main__":
    print("MOJPROP_C161_EFFECTIVE_STAGING_DB_MEDIA_READONLY=" +
          json.dumps(report(), sort_keys=True, separators=(",", ":")))
