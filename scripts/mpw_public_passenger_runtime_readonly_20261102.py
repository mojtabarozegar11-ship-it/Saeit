#!/usr/bin/env python3
"""Read-only, redacted diagnosis of the public MojPlayWin Passenger registration.

Never prints raw uapi records, process command lines, paths from other sites,
environment variables, SQL, credentials, application source or customer data.
No restart, edits, migrations, connection to a database, or service mutation.
"""
from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

PUBLIC = Path("/home/zomorod2/mojplaywin.com")
APP = Path("/home/zomorod2/Saeit-staging")
KNOWN_GUEST_SHA = "7693254e4ed72141b6de7fc283c5a3214159ea49d838318337e47e86953f5f2f"


def _as_target_root(value):
    """Classify only two allowlisted roots; never return the original string."""
    if not isinstance(value, str):
        return "unknown"
    value = value.strip().strip("'\"").rstrip("/")
    if value in (str(PUBLIC), "mojplaywin.com"):
        return "public"
    if value in (str(APP), "Saeit-staging"):
        return "staging"
    return "other"


def _uapi_summary(payload):
    if not isinstance(payload, dict):
        return {"ok": False, "public_root": False, "staging_root": False,
                "mentions_domain": False}
    result = payload.get("result")
    if not isinstance(result, dict):
        return {"ok": False, "public_root": False, "staging_root": False,
                "mentions_domain": False}
    ok = result.get("status") == 1 or result.get("status") is True
    strings = []
    def walk(item, depth=0):
        if depth > 8 or len(strings) >= 500:
            return
        if isinstance(item, str):
            strings.append(item)
        elif isinstance(item, dict):
            for key, value in list(item.items())[:50]:
                if isinstance(key, str) and key.lower() in (
                        "app_path", "application_root", "path", "document_root",
                        "domain", "domain_name", "name", "app_root", "base_uri",
                        "url", "app_name", "directory"):
                    walk(value, depth + 1)
                elif isinstance(value, (dict, list)):
                    walk(value, depth + 1)
        elif isinstance(item, list):
            for value in item[:100]:
                walk(value, depth + 1)
    walk(result.get("data"))
    return {"ok": bool(ok),
            "public_root": any(_as_target_root(s) == "public" for s in strings),
            "staging_root": any(_as_target_root(s) == "staging" for s in strings),
            "mentions_domain": any(s.lower().strip() in
                                   ("mojplaywin.com", "www.mojplaywin.com")
                                   for s in strings)}


def _run_uapi():
    if shutil.which("uapi") is None:
        return None
    try:
        completed = subprocess.run(
            ["uapi", "--output=json", "PassengerApps", "list_applications"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=35, check=False)
        if completed.returncode or len(completed.stdout) > 2_000_000:
            return None
        return json.loads(completed.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


def _passenger_status_summary(raw=None):
    """Parse Passenger app roots without disclosing other apps or raw status."""
    available = True
    readable = False
    if raw is None:
        executable = shutil.which("passenger-status")
        available = executable is not None
        if executable is None:
            return {"available": False, "readable": False,
                    "public_root": False, "staging_root": False}
        try:
            command = subprocess.run([executable], stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, timeout=25,
                                     check=False)
            if command.returncode or len(command.stdout) > 2_000_000:
                return {"available": True, "readable": False,
                        "public_root": False, "staging_root": False}
            raw = command.stdout
        except (OSError, subprocess.TimeoutExpired):
            return {"available": True, "readable": False,
                    "public_root": False, "staging_root": False}
    if not isinstance(raw, (bytes, str)) or len(raw) > 2_000_000:
        return {"available": available, "readable": False,
                "public_root": False, "staging_root": False}
    body = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
    roots = re.findall(r"(?im)^\s*App root:\s*([^\r\n]+)", body)
    readable = bool(roots or "Application groups" in body)
    return {"available": available, "readable": readable,
            "public_root": any(_as_target_root(v) == "public" for v in roots),
            "staging_root": any(_as_target_root(v) == "staging" for v in roots)}


def _owned_workers():
    """Only aggregate this user's candidate Python/Passenger processes."""
    result = {"candidate_count": 0, "cwd_public": 0, "cwd_staging": 0}
    procs = Path("/proc")
    if not procs.is_dir():
        return result
    uid = os.geteuid()
    try:
        paths = (p for p in procs.iterdir() if p.name.isdigit())
        for path in paths:
            try:
                if path.stat().st_uid != uid:
                    continue
                cmd = (path / "cmdline").read_bytes()[:16384].lower()
                if not any(token in cmd for token in (b"passenger", b"python", b"wsgi")):
                    continue
                result["candidate_count"] += 1
                cwd = Path(os.readlink(path / "cwd"))
                if cwd == PUBLIC or PUBLIC in cwd.parents:
                    result["cwd_public"] += 1
                if cwd == APP or APP in cwd.parents:
                    result["cwd_staging"] += 1
            except (OSError, ValueError):
                continue
    except OSError:
        pass
    return result


def inspect_store_sources(*, public=PUBLIC, app=APP):
    """Redacted store and guest-recovery source probe; no Django import or DB IO.

    All targets are fixed repository-relative names. Absence or a source hash
    mismatch must not be interpreted as proof of the effective Passenger worker
    or the production database; this is metadata only, never release approval.
    """
    targets = {
        "view": ("core/mojplaywin_views.py", ("def store(request):", "record_funnel_event(request", "except Exception as exc")),
        "funnel": ("core/commerce_funnel.py", ("def record_funnel_event(", "class CommerceFunnelEvent")),
        "models": ("core/models.py", ("class CommerceFunnelEvent(",)),
        "store_template": ("core/templates/mojplaywin/store.html", ('{% extends "mojplaywin/site_base.html" %}',)),
        "main_template_tag": ("command_center/templatetags/mpw_main.py", ("def mpw_main_data(",)),
        # Fixed, bounded metadata only: no .env, private files or customer rows.
        "guest_adapter": ("services/mpw_trx_guest_commerce.py", ()),
        "guest_recovery": ("services/mpw_trx_email_recovery.py", (
            "def _recovery_enabled(", "MPW_GUEST_RECOVERY_EMAIL_APPROVED",
            "def recovery_verify(", "def recovery_download(")),
        "recovery_migration": ("core/migrations/0049_mpw_guest_email_recovery.py", ()),
        "commercial_web": ("services/mpw_trx_commercial_web.py", ()),
        "commercial_context": ("services/mpw_trx_commercial_context.py", ()),
        "public_pages": ("services/mpw_trx_public_pages.py", ()),
        "commerce_app": ("mpw_commerce/apps.py", ()),
        "commerce_models": ("mpw_commerce/models.py", ()),
        "commerce_migration": ("mpw_commerce/migrations/0001_initial.py", ()),
        "commerce_downloads": ("mpw_commerce/downloads.py", ()),
        "commerce_buyer_orders": ("mpw_commerce/buyer_orders.py", ()),
        "settings_source": ("config/settings.py", ("INSTALLED_APPS",)),
        "url_source": ("config/urls.py", ()),
    }
    output = {}
    for label, root in (("public", public), ("staging", app)):
        if root.is_symlink() or not root.is_dir():
            raise RuntimeError("UNSAFE_STORE_SOURCE_ROOT")
        found = {}
        for name, (relative, markers) in targets.items():
            target = root / relative
            ancestor = target
            while ancestor != root:
                if ancestor.is_symlink():
                    raise RuntimeError("STORE_SOURCE_SYMLINK_REFUSED")
                ancestor = ancestor.parent
            if not target.is_file():
                found[name] = {"present": False}
                continue
            size = target.stat().st_size
            if size > 800000:
                found[name] = {"present": True, "size_limit_exceeded": True}
                continue
            payload = target.read_bytes()
            content = payload.decode("utf-8", "replace")
            found[name] = {
                "present": True,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "sha256_prefix": hashlib.sha256(payload).hexdigest()[:16],
                "marker_presence": [needle in content for needle in markers],
            }
        output[label] = found
    return {
        "classification": "MPW_STORE_SOURCE_METADATA_ONLY",
        "roots": output,
        "client_or_customer_data_read": False,
        "environment_values_read": False,
        "application_imported": False,
        "database_read": False,
        "files_modified": False,
    }



STORE_FALLBACK_PREFIX = (
    "# MPW_STATIC_STORE_FALLBACK_V1\n"
    "RewriteEngine On\n"
    "RewriteCond %{REQUEST_METHOD} ^GET$\n"
    "RewriteCond %{REQUEST_URI} ^/store/?$\n"
    "RewriteRule ^store/?$ store/index.html [END]\n\n"
)


def inspect_public_store_fallback(public, conf):
    """Bounded, names-redacted file and exact leading-rule preflight."""
    from itertools import islice
    store = public / "store"
    index = store / "index.html"
    valid_dir = store.is_dir() and not store.is_symlink()
    entries = list(islice(store.iterdir(), 33)) if valid_dir else []
    valid_index = valid_dir and index.is_file() and not index.is_symlink()
    marker = False
    if valid_index and index.stat().st_size <= 200_000:
        marker = b"MPW_STATIC_STORE_FALLBACK_V1" in index.read_bytes()
    normalized_conf = conf.replace("\r\n", "\n").lstrip("\ufeff\n")
    marker_lines = [i for i, line in enumerate(conf.splitlines()) if "MPW_STATIC_STORE_FALLBACK_V1" in line]
    return {
        "exact_block_once": conf.count(STORE_FALLBACK_PREFIX) == 1,
        "normalized_block_once": normalized_conf.count(STORE_FALLBACK_PREFIX) == 1,
        "marker_at_first_line": marker_lines == [0],
        "marker_line_capped": min(marker_lines[0], 1000) if len(marker_lines) == 1 else None,
        "exact_leading_rule": conf.startswith(STORE_FALLBACK_PREFIX),
        "rule_marker_once": conf.count("MPW_STATIC_STORE_FALLBACK_V1") == 1,
        "store_directory_regular": valid_dir,
        "index_file_regular": valid_index,
        "index_owner_marker": marker,
        "store_index_only": len(entries) == 1 and entries[0].name == "index.html" and valid_index,
        "entry_count_capped": min(len(entries), 32),
        "directory_has_more_than_32_entries": len(entries) > 32,
        "files_modified": False,
    }



def inspect_passenger_wiring(conf, wsgi_text):
    """Boolean-only public virtual-host wiring evidence; no directive values leak."""
    python = re.findall(r"(?im)^\s*PassengerPython\s+([^\r\n#]+)", conf)
    startup = re.findall(r"(?im)^\s*PassengerStartupFile\s+([^\r\n#]+)", conf)
    return {
        "passenger_python_directives": min(8, len(python)),
        "passenger_python_311": any("/3.11/" in p for p in python),
        "passenger_python_stage_venv": any("/virtualenv/Saeit-staging/" in p for p in python),
        "passenger_python_other_venv": any(
            "/virtualenv/" in p and "/virtualenv/Saeit-staging/" not in p for p in python
        ),
        "passenger_startup_file_directives": min(8, len(startup)),
        "wsgi_mentions_staging_source": str(APP) in wsgi_text,
        "wsgi_has_django_entrypoint": (
            "from config.wsgi import application" in wsgi_text
            or "get_wsgi_application()" in wsgi_text
        ),
        "htaccess_rewrite_rule_count_capped": min(
            32, sum(bool(re.match(r"^\s*RewriteRule\b", s, re.I)) for s in conf.splitlines())
        ),
    }


def classify_missing_module(module):
    """Fixed-label bucketing only; never return untrusted module text."""
    module = module.lower()
    if module == b"config" or module.startswith(b"config."):
        return "project_config"
    if module == b"core.commerce_funnel" or module.startswith(b"core.commerce_funnel."):
        return "optional_commerce_telemetry"
    if module == b"core" or module.startswith(b"core."):
        return "project_core"
    if module == b"django" or module.startswith(b"django."):
        return "django_dependency"
    if module == b"whitenoise" or module.startswith(b"whitenoise."):
        return "static_middleware_dependency"
    if module == b"environ" or module.startswith(b"environ."):
        return "environment_library"
    if module in (b"mysqlclient", b"mysqldb", b"pymysql"):
        return "database_driver"
    if module == b"command_center" or module.startswith(b"command_center."):
        return "management_module"
    return "other_unclassified"


def inspect_error_classes(public, now_epoch=None):
    """Scan bounded recent, allowlisted *error* files; emit only fixed classes."""
    now_epoch = time.time() if now_epoch is None else now_epoch
    files = (
        public / "error_log", public / "stderr.log",
        public / "tmp/passenger.stderr.log", public / "logs/error.log",
    )
    signatures = {
        "module_missing": b"modulenotfounderror",
        "import_error": b"importerror",
        "django_improper_settings": b"improperlyconfigured",
        "database_operational_error": b"operationalerror",
        "file_permission_error": b"permissionerror",
        "template_missing": b"templatedoesnotexist",
        "static_manifest_error": b"missing staticfiles manifest entry",
        "passenger_boot_error": b"cannot load application",
        "python_traceback": b"traceback (most recent call last)",
    }
    category_names = (
        "project_config", "optional_commerce_telemetry", "project_core",
        "django_dependency", "static_middleware_dependency", "environment_library",
        "database_driver", "management_module", "other_unclassified",
    )
    # Named exception types only; all output keys are fixed and aggregate.
    exception_types = {
        "django_disallowed_host": b"disallowedhost",
        "django_suspicious_operation": b"suspiciousoperation",
        "django_app_registry": b"appregistrynotready",
        "django_url_reverse": b"noreversematch",
        "django_template_syntax": b"templatesyntaxerror",
        "python_attribute": b"attributeerror",
        "python_type": b"typeerror",
        "python_value": b"valueerror",
        "python_key": b"keyerror",
        "python_runtime": b"runtimeerror",
        "python_name": b"nameerror",
        "python_assertion": b"assertionerror",
        "python_file_not_found": b"filenotfounderror",
        "python_os": b"oserror",
        "python_system_exit": b"systemexit",
        "python_connection_refused": b"connectionrefusederror",
        "python_timeout": b"timeouterror",
        "database_programming": b"programmingerror",
        "database_integrity": b"integrityerror",
    }
    runtime_cause_phrases = {
        "django_initialization": (b"populate()", b"app registry", b"apps aren't loaded"),
        "passenger_wsgi_startup": (b"passenger", b"wsgi", b"app root", b"startup", b"spawn"),
        "python_import_environment": (b"sys.path", b"virtualenv", b"interpreter", b"import", b"module"),
        "resource_exhaustion": (b"resource temporarily unavailable", b"out of memory",
                                b"too many open files", b"cannot allocate memory",
                                b"can't start new thread", b"process limit"),
        "database_runtime": (b"database", b"sqlite", b"mysql", b"mariadb"),
        "settings_environment": (b"settings", b"environment", b"secret_key", b"configuration"),
        "filesystem_runtime": (b"permission", b"directory", b"file not found"),
        "async_or_thread": (b"event loop", b"thread", b"async"),
        "store_business_guard": (b"store", b"checkout", b"commerce", b"payment"),
    }
    runtime_leading_words = (
        b"cannot", b"unable", b"failed", b"missing", b"invalid", b"no", b"the",
        b"application", b"wsgi", b"passenger", b"django", b"settings",
        b"public", b"staging", b"expected", b"wrong", b"store", b"source",
    )
    shape_names = (
        "exception_message_line", "non_exception_reference",
        "module_phrase_near_marker", "module_phrase_absent_near_marker",
    )
    result = {"regular_recent_error_files": 0, "bounded_bytes_scanned": 0,
              "classes": {key: 0 for key in signatures},
              "missing_module_categories": {key: 0 for key in category_names},
              "missing_module_shapes": {key: 0 for key in shape_names},
              "exception_type_signatures": {key: 0 for key in exception_types},
              "runtime_error_cause_buckets": {key: 0 for key in (
                  *runtime_cause_phrases.keys(), "other_unclassified")},
              "runtime_error_leading_words": {key.decode("ascii"): 0 for key in runtime_leading_words},
              "runtime_error_message_distinct_capped": 0,
              "files_modified": False, "raw_log_emitted": False}
    runtime_message_digests = set()
    for path in files:
        try:
            if (path.is_symlink() or path.parent.is_symlink() or
                    not path.is_file() or path.stat().st_uid != os.geteuid()):
                continue
            info = path.stat()
            if not 0 <= now_epoch - info.st_mtime <= 3 * 86400:
                continue
            with path.open("rb") as handle:
                handle.seek(max(0, info.st_size - 262144))
                data = handle.read(262144).lower()
            result["regular_recent_error_files"] += 1
            result["bounded_bytes_scanned"] += len(data)
            for key, needle in signatures.items():
                result["classes"][key] = min(100, result["classes"][key] + data.count(needle))
            for key, token in exception_types.items():
                pattern = rb"(?<![a-z0-9_])(?:[a-z_][a-z0-9_]*\.){0,6}" + token + rb"\s*:"
                for match in re.finditer(pattern, data):
                    prefix = data[max(0, match.start() - 32):match.start()]
                    if re.search(rb"\b(?:except|raise)\s+$", prefix):
                        continue
                    result["exception_type_signatures"][key] = min(
                        100, result["exception_type_signatures"][key] + 1
                    )
            # Bounded single-line RuntimeError messages. Emit only fixed-label
            # categories, whitelisted leading words and a distinct count.
            for marker in re.finditer(rb"\bruntimeerror\s*:", data):
                prefix = data[max(0, marker.start() - 32):marker.start()]
                if re.search(rb"\b(?:except|raise)\s+$", prefix):
                    continue
                message = data[marker.end():marker.end() + 256].split(b"\n", 1)[0].strip()
                if not message:
                    continue
                runtime_message_digests.add(hashlib.sha256(message).digest())
                category = "other_unclassified"
                for label, phrases in runtime_cause_phrases.items():
                    if any(phrase in message for phrase in phrases):
                        category = label
                        break
                result["runtime_error_cause_buckets"][category] = min(
                    100, result["runtime_error_cause_buckets"][category] + 1
                )
                first = re.match(rb"([a-z]{2,24})\b", message)
                if first and first.group(1) in runtime_leading_words:
                    fixed_word = first.group(1).decode("ascii")
                    result["runtime_error_leading_words"][fixed_word] = min(
                        100, result["runtime_error_leading_words"][fixed_word] + 1
                    )
            # Never emit log text, module names, or arbitrary substrings.
            # Distinguish exception messages from code references in tracebacks.
            for marker in re.finditer(rb"modulenotfounderror", data):
                suffix = data[marker.end():marker.end() + 256]
                first_line = suffix.split(b"\n", 1)[0]
                prefix = data[max(0, marker.start() - 32):marker.start()]
                source_reference = bool(re.search(rb"\b(?:except|raise)\s+$", prefix))
                is_exception = bool(re.match(rb"\s*:", first_line)) and not source_reference
                line_shape = "exception_message_line" if is_exception else "non_exception_reference"
                result["missing_module_shapes"][line_shape] = min(
                    100, result["missing_module_shapes"][line_shape] + 1
                )
                # Do not borrow the next exception's module from a source-code marker.
                scoped = suffix.split(b"modulenotfounderror", 1)[0] if is_exception else b""
                normalized = re.sub(rb"\s+", b" ", scoped)
                phrase = re.search(
                    rb"no module named\s+(?:['\"]|&#39;|&#x27;|&quot;)?"
                    rb"([a-z_][a-z0-9_.]{0,127})",
                    normalized,
                )
                phrase_shape = ("module_phrase_near_marker" if phrase
                                else "module_phrase_absent_near_marker")
                result["missing_module_shapes"][phrase_shape] = min(
                    100, result["missing_module_shapes"][phrase_shape] + 1
                )
                if phrase and is_exception:
                    group = classify_missing_module(phrase.group(1))
                    result["missing_module_categories"][group] = min(
                        100, result["missing_module_categories"][group] + 1
                    )
        except (OSError, ValueError):
            continue
    result["runtime_error_message_distinct_capped"] = min(32, len(runtime_message_digests))
    return result


def inspect(*, public=PUBLIC, app=APP, uapi_payload=None, workers=None, status_payload=None):
    if public == PUBLIC and app == APP and pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        raise RuntimeError("WRONG_CPANEL_ACCOUNT")
    if public.is_symlink() or app.is_symlink() or not public.is_dir() or not app.is_dir():
        raise RuntimeError("WRONG_PUBLIC_APP_ROOTS")
    htaccess = public / ".htaccess"
    wsgi = public / "passenger_wsgi.py"
    guest = app / "services/mpw_trx_guest_commerce.py"
    marker = public / "tmp/restart.txt"
    conf = htaccess.read_text("utf-8", "replace") if htaccess.is_file() and not htaccess.is_symlink() else ""
    roots = re.findall(r"(?im)^\s*PassengerAppRoot\s+([^\r\n#]+)", conf)
    wsgi_text = wsgi.read_text("utf-8", "replace") if wsgi.is_file() and not wsgi.is_symlink() else ""
    guest_prior = bool(guest.is_file() and not guest.is_symlink() and
                       hashlib.sha256(guest.read_bytes()).hexdigest() == KNOWN_GUEST_SHA)
    marker_ok = marker.is_file() and not marker.is_symlink()
    guest_ok = guest.is_file() and not guest.is_symlink()
    if uapi_payload is None:
        uapi_payload = _run_uapi()
    api = _uapi_summary(uapi_payload)
    status = _passenger_status_summary(status_payload)
    if workers is None:
        workers = _owned_workers()
    return {"classification": "MPW_PUBLIC_PASSENGER_READ_ONLY_RUNTIME_CONTRACT",
            "passenger_wiring_readonly": inspect_passenger_wiring(conf, wsgi_text),
            "server_error_classes_readonly": inspect_error_classes(public),
            "public_app_root_directive_count": len(roots),
            "htaccess_public_root": len(roots) == 1 and _as_target_root(roots[0]) == "public",
            "htaccess_staging_root": len(roots) == 1 and _as_target_root(roots[0]) == "staging",
            "store_fallback_readonly": inspect_public_store_fallback(public, conf),
            "public_wsgi_references_staging": str(APP) in wsgi_text,
            "guest_module_restored_to_known_prior": guest_prior,
            "public_restart_marker_present": bool(marker_ok),
            "public_restart_marker_newer_than_guest": bool(
                marker_ok and guest_ok and marker.stat().st_mtime >= guest.stat().st_mtime),
            "uapi_passenger_list_ok": api["ok"],
            "uapi_registers_public_root": api["public_root"],
            "uapi_registers_staging_root": api["staging_root"],
            "uapi_mentions_public_domain": api["mentions_domain"],
            "passenger_status_cli_available": status["available"],
            "passenger_status_registry_readable": status["readable"],
            "passenger_status_public_root": status["public_root"],
            "passenger_status_staging_root": status["staging_root"],
            "owned_candidate_worker_count_capped": min(100, workers["candidate_count"]),
            "owned_worker_cwd_public_count_capped": min(100, workers["cwd_public"]),
            "owned_worker_cwd_staging_count_capped": min(100, workers["cwd_staging"]),
            "python_minor": sys.version_info.minor,
            "production_service_restarted": False,
            "effective_public_worker_proven": False,
            "database_or_customer_data_read": False,
            "files_modified": False,
            "release_permitted": False,
            "store_source_readonly": inspect_store_sources(public=public, app=app)}


if __name__ == "__main__":
    if sys.argv[1:] != ["inspect"]:
        raise SystemExit(2)
    try:
        report = inspect()
    except Exception:
        print("MPW_PASSENGER_DIAGNOSTIC=PREREQUISITE_REJECTED", file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps(report, sort_keys=True))
