#!/usr/bin/env python3
"""C124: discover the actual MojProp cPanel domain/docroot/Passenger binding.

Uses only cPanel UAPI read operations for the exact mojprop.top hostname.
It never guesses a filesystem root, reads application files or databases,
changes domain settings, enables Passenger, restarts a service, or deploys.
Only bounded, allow-listed hosting metadata is emitted.
"""
from __future__ import annotations

import json
import os
import pwd
import re
import stat
import subprocess

OWNER = "zomorod2"
DOMAIN = "mojprop.top"
UAPI = "/usr/bin/uapi"
MAX_OUTPUT = 65536
MAX_DEPTH = 8
SAFE_PATH_PREFIX = "/home/zomorod2/"
_LAST_UAPI_IO = {}


def _walk(value, depth=0):
    if depth > MAX_DEPTH:
        return
    if type(value) is dict:
        for key, item in value.items():
            yield str(key).lower(), item
            yield from _walk(item, depth + 1)
    elif type(value) is list:
        for item in value[:100]:
            if type(item) in (str, int, float, bool) or item is None:
                yield "", item
            else:
                yield from _walk(item, depth + 1)


def _domain_in(value):
    return any(type(item) is str and item.rstrip(".").lower() == DOMAIN
               for _, item in _walk(value))


def _safe_home_path(value):
    if type(value) is not str or not value.startswith(SAFE_PATH_PREFIX):
        return None
    if any(part in ("", ".", "..") for part in value.split("/")[3:]):
        return None
    return value[:512] if len(value) <= 512 else None


def _find_path(value, keys):
    for key, item in _walk(value):
        if key in keys:
            candidate = _safe_home_path(item)
            if candidate:
                return candidate
    return None


def _safe_error_tokens(stderr):
    """Return only generic allow-listed CLI words; never emit provider text."""
    allowed = {
        "uapi", "unknown", "unrecognized", "option", "argument", "arguments",
        "user", "permission", "error", "usage", "command", "not", "found",
        "invalid", "api", "root", "must", "run", "as", "requires", "module",
        "function", "disabled", "failed", "could", "cannot", "execute",
        "perl", "json", "output", "help", "version", "syntax", "access",
        "denied", "missing", "parameter", "parameters", "required", "specify",
        "specified", "incorrect", "unknown", "supported", "available",
    }
    words = re.findall(r"[a-zA-Z][a-zA-Z_-]{1,24}", stderr[:4096].decode("utf-8", "replace").lower())
    return sorted({word for word in words if word in allowed})[:20]


def _classify_uapi_error(stderr):
    """Map provider stderr to a fixed safe category; never return its contents."""
    err = stderr[:4096].decode("utf-8", "replace").lower()
    if all(token in err for token in ("failed", "uapi", "as", "user")):
        return "uapi_execution_context_failed"
    rules = (
        (("unknown option", "unrecognized option"), "cli_option_rejected"),
        (("permission denied", "access denied", "not authorized", "not permitted"), "permission_denied"),
        (("invalid user", "unknown user", "no such user", "user does not exist"), "account_context_rejected"),
        (("must be run as root", "must be run by root", "root privileges"), "root_privilege_required"),
        (("module not found", "unknown module", "no such module"), "uapi_module_not_found"),
        (("function not found", "unknown function", "no such function"), "uapi_function_not_found"),
        (("api disabled", "uapi disabled", "api access disabled"), "uapi_access_disabled"),
        (("not found", "no such file"), "uapi_component_not_found"),
        (("usage:", "syntax", "invalid argument", "too many arguments"), "cli_syntax_rejected"),
        (("internal server error", "server error", "fatal error"), "cpanel_runtime_error"),
        (("perl", "exception", "traceback"), "cpanel_runtime_exception"),
        (("session", "authentication", "login required"), "cpanel_session_error"),
    )
    for needles, category in rules:
        if any(needle in err for needle in needles):
            return category
    return "unclassified_nonzero_exit"


def _uapi(module, function, parameters=()):
    _LAST_UAPI_IO.clear()
    args = [UAPI, "--output=json", module, function]
    args.extend(parameters)
    env = {"LC_ALL": "C", "PATH": "/usr/bin:/bin:/usr/local/bin",
           "HOME": "/home/zomorod2", "USER": OWNER, "LOGNAME": OWNER}
    try:
        result = subprocess.run(args, capture_output=True, timeout=18,
                                check=False, env=env)
    except subprocess.TimeoutExpired as exc:
        _LAST_UAPI_IO.update({"timeout": True, "stdout_bytes": len(exc.stdout or b""), "stderr_bytes": len(exc.stderr or b"")})
        return None, "timeout"
    except OSError as exc:
        _LAST_UAPI_IO.update({"exec_error_type": type(exc).__name__})
        return None, "exec_error"
    _LAST_UAPI_IO.update({"exit_code": int(result.returncode), "stdout_bytes": len(result.stdout), "stderr_bytes": len(result.stderr), "stderr_empty": len(result.stderr) == 0, "stdout_empty": len(result.stdout) == 0, "stderr_safe_tokens": _safe_error_tokens(result.stderr)})
    if result.returncode != 0:
        reason = _classify_uapi_error(result.stderr)
        return None, reason
    if not 0 < len(result.stdout) <= MAX_OUTPUT:
        return None, "empty_or_oversize"
    try:
        payload = json.loads(result.stdout)
    except (UnicodeError, ValueError, TypeError):
        return None, "invalid_json"
    envelope = payload.get("result") if type(payload) is dict else None
    if type(envelope) is not dict:
        return None, "missing_result_envelope"
    if envelope.get("status") != 1:
        return None, "uapi_status_not_success"
    return envelope.get("data"), "success"


def inspect():
    out = {
        "schema": "mojprop.domain_identity.readonly.c124.v1",
        "read_only": True,
        "owner_identity_verified": False,
        "uapi_binary_safe": False,
        "domain_list_query_succeeded": False,
        "domain_list_contains_mojprop": False,
        "single_domain_query_succeeded": False,
        "domain_docroot": None,
        "passenger_list_query_succeeded": False,
        "passenger_applications_for_domain": 0,
        "passenger_application_root": None,
        "passenger_application_uri": None,
        "passenger_startup_file": None,
        "passenger_enabled": None,
        "raw_provider_data_emitted": False,
        "files_read": False,
        "database_accessed": False,
        "customer_data_accessed": False,
        "files_modified": False,
        "service_restarted": False,
        "payment_created": False,
        "email_sent": False,
        "deployment_authorized": False,
        "cost_incurred": False,
        "uapi_diagnostics": {},
        "uapi_io_diagnostics": {},
    }
    try:
        if pwd.getpwuid(os.geteuid()).pw_name != OWNER:
            return out
        out["owner_identity_verified"] = True
        meta = os.stat(UAPI)
        if (not stat.S_ISREG(meta.st_mode) or meta.st_mode & 0o022
                or meta.st_uid not in (0, os.geteuid())):
            return out
        out["uapi_binary_safe"] = True

        domains, domain_status = _uapi("DomainInfo", "list_domains")
        out["uapi_diagnostics"]["domain_list"] = domain_status
        out["uapi_io_diagnostics"]["domain_list"] = dict(_LAST_UAPI_IO)
        if domain_status == "success":
            out["domain_list_query_succeeded"] = True
            out["domain_list_contains_mojprop"] = _domain_in(domains)

        domain_data, single_status = _uapi(
            "DomainInfo", "single_domain_data", ("domain=" + DOMAIN,)
        )
        out["uapi_diagnostics"]["single_domain"] = single_status
        out["uapi_io_diagnostics"]["single_domain"] = dict(_LAST_UAPI_IO)
        if single_status == "success":
            out["single_domain_query_succeeded"] = True
            out["domain_docroot"] = _find_path(
                domain_data, {"documentroot", "document_root", "docroot"}
            )

        apps, passenger_status = _uapi("PassengerApps", "list_applications")
        out["uapi_diagnostics"]["passenger_list"] = passenger_status
        out["uapi_io_diagnostics"]["passenger_list"] = dict(_LAST_UAPI_IO)
        if passenger_status == "success":
            out["passenger_list_query_succeeded"] = True
            records = apps if type(apps) is list else [apps]
            matches = [item for item in records
                       if type(item) is dict and _domain_in(item)]
            out["passenger_applications_for_domain"] = min(len(matches), 20)
            if matches:
                app = matches[0]
                out["passenger_application_root"] = _find_path(
                    app, {"path", "app_root", "application_root", "root"}
                )
                out["passenger_application_uri"] = next(
                    (v[:160] for k, v in _walk(app)
                     if k in {"base_uri", "app_uri", "uri"}
                     and type(v) is str and v.startswith("/")), None
                )
                out["passenger_startup_file"] = next(
                    (v[:128] for k, v in _walk(app)
                     if k in {"startup_file", "startupfile"}
                     and type(v) is str and "/" not in v and "\\" not in v), None
                )
                enabled = next((v for k, v in _walk(app)
                                if k in {"enabled", "is_enabled"}
                                and type(v) is bool), None)
                out["passenger_enabled"] = enabled
    except (OSError, subprocess.SubprocessError, ValueError, KeyError):
        pass
    return out


if __name__ == "__main__":
    print("MOJPROP_C124_DOMAIN_IDENTITY_READONLY=" +
          json.dumps(inspect(), sort_keys=True, separators=(",", ":")))
