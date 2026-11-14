#!/usr/bin/env python3
"""Read-only structural provenance of the deployed Zomorod PHP lead handler.

Run over SSH stdin as `python3 -B -` under the cPanel account. It does not
execute PHP, send requests, read customer data or reveal source/config values.
Every signal reports a *static source indicator*, never a verified control.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import stat
import sys

EXPECTED_USER = "zomorod2"
ROOT = Path.home() / "public_html" / "ask-master"
MAX_SINGLE_BYTES = 256 * 1024
MAX_TOTAL_BYTES = 768 * 1024
MAX_FILES = 12
# Regexes look for syntactic features only; none demonstrates real enforcement.
INDICATORS = {
    "request_method_gate": rb"REQUEST_METHOD",
    "post_input_access": rb"\$_POST\b|php://input",
    "session_access": rb"\$_SESSION\b|session_start\s*\(",
    "csrf_name_or_check": rb"csrf|xsrf|hash_equals\s*\(",
    "consent_name_or_check": rb"consent|privacy|agreement",
    "honeypot_name_or_check": rb"honeypot|website_check|fax_number",
    "captcha_name_or_check": rb"captcha|turnstile|recaptcha|hcaptcha",
    "email_validation": rb"FILTER_VALIDATE_EMAIL|filter_var\s*\(",
    "input_validation": rb"mb_strlen|strlen\s*\(|preg_match\s*\(",
    "max_input_handling": rb"CONTENT_LENGTH|post_max_size|MAX_LENGTH",
    "duplicate_or_rate_limit": rb"rate.limit|duplicate|throttl|cooldown",
    "database_access": rb"PDO\b|mysqli|SQLite3\b",
    "prepared_statement": rb"->prepare\s*\(|mysqli_prepare\s*\(",
    "database_mutation": rb"\bINSERT\s+INTO\b|\bUPDATE\s+[a-z_]",
    "filesystem_write": rb"file_put_contents\s*\(|fwrite\s*\(",
    "mail_dispatch": rb"\bmail\s*\(|PHPMailer|SMTP",
    "external_dispatch": rb"curl_exec\s*\(|wp_remote_post\s*\(",
    "redirect_or_receipt": rb"\bheader\s*\(|receipt|thank.you|tracking",
    "upload_handling": rb"\$_FILES\b|move_uploaded_file\s*\(",
    "output_escaping": rb"htmlspecialchars\s*\(|htmlentities\s*\(",
    "exception_or_error_handling": rb"\btry\s*\{|error_log\s*\(",
    "origin_or_referer_check": rb"HTTP_ORIGIN|HTTP_REFERER|same.origin",
}

def print_fact(name: str, value: object) -> None:
    if not re.fullmatch(r"[A-Z0-9_]+", name):
        raise ValueError("unsafe label")
    print("ZM_PHP_" + name + "=" + str(value).lower())

def read_sources(root: Path) -> tuple[list[tuple[str, bytes]], str]:
    if root.is_symlink() or not root.is_dir():
        return [], "NO_SAFE_DIRECTORY"
    entry = root / "index.php"
    if entry.is_symlink() or not entry.is_file():
        return [], "NO_SAFE_ENTRY"
    # Directory names and file contents are never emitted to logs.
    candidates = [entry]
    for p in sorted(root.glob("*.php")):
        if p.name != "index.php" and not p.is_symlink() and p.is_file():
            candidates.append(p)
    if len(candidates) > MAX_FILES:
        return [], "TOO_MANY_SOURCES"
    total = 0
    out = []
    for file in candidates:
        try:
            metadata = file.stat()
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
                return [], "UNSAFE_FILE_OWNERSHIP"
            if metadata.st_size <= 0 or metadata.st_size > MAX_SINGLE_BYTES:
                return [], "INVALID_SOURCE_SIZE"
            total += metadata.st_size
            if total > MAX_TOTAL_BYTES:
                return [], "TOO_MUCH_SOURCE"
            out.append((file.name, file.read_bytes()))
        except OSError:
            return [], "SOURCE_UNREADABLE"
    return out, "STRUCTURAL_READ_COMPLETE"

def collect(sources: list[tuple[str, bytes]]) -> dict[str, bool]:
    joined = b"\n".join(data for _, data in sources)
    return {
        key: re.search(pattern, joined, re.I) is not None
        for key, pattern in INDICATORS.items()
    }

def main() -> int:
    if os.environ.get("PYTHONDONTWRITEBYTECODE") not in (None, "1"):
        print_fact("STATE", "ENVIRONMENT_REJECTED")
        return 12
    import pwd
    if pwd.getpwuid(os.getuid()).pw_name != EXPECTED_USER:
        print_fact("STATE", "IDENTITY_REJECTED")
        return 13
    sources, state = read_sources(ROOT)
    print_fact("STATE", state)
    if not sources:
        print_fact("POST_PERSISTENCE_VERIFIED", "unknown")
        print_fact("CUSTOMER_CONSENT_VERIFIED", "unknown")
        print_fact("CRM_HANDOFF_VERIFIED", "unknown")
        return 14
    print_fact("SOURCE_COUNT", len(sources))
    print_fact("SOURCE_TOTAL_BYTES", sum(len(data) for _, data in sources))
    print_fact("ENTRY_SHA256", hashlib.sha256(sources[0][1]).hexdigest())
    signals = collect(sources)
    for key, indicator in sorted(signals.items()):
        print_fact("STATIC_" + key.upper(), str(indicator))
    # These are deliberately UNKNOWN even when static strings appear.
    print_fact("POST_PERSISTENCE_VERIFIED", "unknown")
    print_fact("CUSTOMER_CONSENT_VERIFIED", "unknown")
    print_fact("CSRF_ENFORCEMENT_VERIFIED", "unknown")
    print_fact("DATABASE_OWNER_AND_RETENTION_VERIFIED", "unknown")
    print_fact("CRM_HANDOFF_VERIFIED", "unknown")
    print_fact("REAL_PAID_ORDER_VERIFIED", "unknown")
    print_fact("CLIENT_DATA_READ", "false")
    print_fact("PRODUCTION_DATA_MUTATED", "false")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
