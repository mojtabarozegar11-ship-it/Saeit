#!/usr/bin/env python3
"""C14 privacy-safe structural triage of the actual company PHP POST flow.

No GET/POST, no PHP execution, no customer data, no remote data writes.
Scan only two known owner-local, non-symlink, capped PHP source files.
All output is fixed-key boolean/count only, without raw source excerpts.
Static indicators are *not* evidence of successful database persistence.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import pwd
import re
import stat
import sys

ROOT = Path.home() / "public_html" / "ask-master"
MAX_SOURCE = 400_000
PHP = ("index.php",)  # Additional owner-local PHP files enumerated below
S = {
    "post_branch": rb"\$_SERVER\s*\[\s*['\"]REQUEST_METHOD['\"]\s*\]|\$_POST\b",
    "email_validation": rb"FILTER_VALIDATE_EMAIL|filter_var\s*\(",
    "csrf_token_definition": rb"csrf|xsrf|_token|nonce",
    "csrf_server_verification": rb"hash_equals\s*\(|\$_SESSION\s*\[[^]]*csrf",
    "consent_checkbox": rb"type\s*=\s*['\"]checkbox['\"]|consent|privacy",
    "server_consent_required": rb"\$_POST\s*\[\s*['\"](?:consent|privacy_consent|agree|agreement|accept_terms|terms)['\"]",
    "ip_rate_control": rb"rate[_ -]?limit|throttle|cooldown|retry_after",
    "session_usage": rb"session_start\s*\(|\$_SESSION\s*\[",
    "sql_insert": rb"\bINSERT\s+INTO\b",
    "sql_select": rb"\bSELECT\b",
    "prepared_sql": rb"->prepare\s*\(|mysqli_prepare\s*\(",
    "sqlite_client": rb"SQLite3\b|sqlite:",
    "mysql_client": rb"mysqli\b|mysql:",
    "pdo_client": rb"\bPDO\s*\(",
    "file_store": rb"file_put_contents\s*\(|fwrite\s*\(",
    "external_form_dispatch": rb"curl_exec\s*\(|wp_remote_post\s*\(",
    "email_dispatch": rb"\bmail\s*\(|PHPMailer|SMTP",
    "cookie_session": rb"session_set_cookie_params\s*\(|setcookie\s*\(",
    "exception_handling": rb"\bcatch\s*\(",
    "success_receipt": rb"receipt|ticket|tracking",
    "error_log": rb"error_log\s*\(",
    "robots_privacy": rb"noindex|no-store",
    "html_output_escape": rb"htmlspecialchars\s*\(|htmlentities\s*\(",
    "filestore_permissions": rb"chmod\s*\(|umask\s*\(",
    "inclusion": rb"\b(?:require|require_once|include|include_once)\b",
}

def out(key: str, value: object) -> None:
    if not re.fullmatch("[A-Z0-9_]+", key):
        raise ValueError("bad output key")
    print("ZM_C14_PHP_" + key + "=" + str(value).lower())

def main() -> int:
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        out("STATE", "WRONG_USER")
        return 12
    if ROOT.is_symlink() or not ROOT.is_dir():
        out("STATE", "NO_SAFE_PHP_ROOT")
        return 13
    contents = []
    if not (ROOT / "index.php").is_file():
        out("STATE", "NO_INDEX_FILE")
        return 14
    names = list(PHP) + sorted(
        f.name for f in ROOT.glob("*.php")
        if f.name not in PHP
    )
    if len(names) > 12:
        out("STATE", "TOO_MANY_LOCAL_PHP_FILES")
        return 14
    for basename in names:
        f = ROOT / basename
        if not f.exists() and not f.is_symlink():
            out("SOURCE_"+basename.replace(".", "_").upper()+"_EXISTS", "false")
            continue
        if f.is_symlink() or not f.is_file():
            out("STATE", "UNSAFE_SYMLINK")
            return 14
        meta = f.stat()
        if not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.getuid():
            out("STATE", "SOURCE_OWNER_MISMATCH")
            return 15
        if not 0 < meta.st_size <= MAX_SOURCE:
            out("STATE", "SOURCE_SIZE_OUT_OF_BOUNDS")
            return 16
        contents.append(f.read_bytes())
        out("SOURCE_"+basename.replace(".", "_").upper()+"_EXISTS", "true")
        out("SOURCE_"+basename.replace(".", "_").upper()+"_SHA256", hashlib.sha256(contents[-1]).hexdigest())
    if not contents:
        out("STATE", "NO_SUPPORTED_PHP_FILE")
        return 17
    joined = b"\n".join(contents)
    out("STATE", "SOURCE_INSPECTED_READ_ONLY")
    out("SOURCE_COUNT", len(contents))
    for key, regex in sorted(S.items()):
        try:
            found = bool(re.search(regex, joined, re.I))
        except re.error:
            out("STATE", "REGEX_INVALID")
            return 18
        out("INDICATOR_"+key.upper(), str(found))
    out("POST_RECEIPT_VERIFIED", "unknown")
    out("CONSENT_ENFORCEMENT_VERIFIED", "unknown")
    out("SOURCE_TO_DB_MAPPING_VERIFIED", "unknown")
    out("CRM_HANDOFF_VERIFIED", "unknown")
    out("REAL_CUSTOMER_DATA_READ", "false")
    out("PRODUCTION_WRITES", "0")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
