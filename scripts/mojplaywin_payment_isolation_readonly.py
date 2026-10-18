#!/usr/bin/env python3
"""Read-only capability probe for payment-only isolated publishing.

Only checks command availability and metadata of a tightly scoped set of
public routing files. Never exposes .htaccess contents, env, secrets, database,
customer records, child-site contents, or performs writes.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess

HOME = Path("/home/zomorod2")
WEB = HOME / "mojplaywin.com"
GATEWAY = WEB / "checkout" / "crypto"
SHARED = HOME / "Saeit-staging"


def php_info():
    php = shutil.which("php")
    if not php:
        return {"installed": False}
    try:
        p = subprocess.run([php, "-r", 'echo json_encode(["version"=>PHP_VERSION,"pdo_sqlite"=>extension_loaded("pdo_sqlite"),"sqlite3"=>extension_loaded("sqlite3"),"curl"=>extension_loaded("curl"),"openssl"=>extension_loaded("openssl"),"sodium"=>extension_loaded("sodium")]);'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=8)
        x = json.loads(p.stdout) if p.returncode == 0 and len(p.stdout) < 1000 else {}
        return {"installed": bool(x), **x}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {"installed": False}


def metadata(path):
    return {
        "exists": path.exists(), "symlink": path.is_symlink(),
        "directory": path.is_dir(), "regular": path.is_file(),
    }


def main():
    # Inspect routing syntax in memory but avoid printing config/paths.
    ht = WEB / ".htaccess"
    httext = ""
    if ht.is_file() and not ht.is_symlink() and ht.stat().st_size < 32768:
        httext = ht.read_text(encoding="utf-8",errors="replace")
    php = php_info()
    return {
        "classification": "MOJPLAYWIN_PAYMENT_ISOLATION_READONLY",
        "webroot": metadata(WEB),
        "crypto_subfolder": metadata(GATEWAY),
        "checkout_parent": metadata(GATEWAY.parent),
        "checkout_htaccess": metadata(GATEWAY.parent / ".htaccess"),
        "gateway_htaccess": metadata(GATEWAY / ".htaccess"),
        "php": php,
        "webroot_has_passenger_routing": "passenger" in httext.lower(),
        "webroot_has_rewrite_rules": "rewriterule" in httext.lower(),
        "webroot_has_filesystem_rewrite_cond": "-f" in httext or "-d" in httext,
        "apache_routing_tokens": [
            # Whitelisted non-secret directives only, with paths/user values omitted.
            {"directive": line.strip().split(None, 1)[0].lower(),
             "mentions_checkout": "checkout" in line.lower(),
             "mentions_passenger": "passenger" in line.lower(),
             "mentions_index_php": "index.php" in line.lower(),
             "mentions_static_f": "-f" in line,
             "mentions_static_d": "-d" in line,
             "has_last_flag": "[l" in line.lower() or ",l" in line.lower()}
            for line in httext.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
            and line.strip().split(None, 1)[0].lower()
            in {"rewriteengine", "rewritecond", "rewriterule", "rewritebase", "directoryindex",
                "passengerenabled", "passengerappenv", "passengerbaseuri", "passengerapproot",
                "passengerpython", "passengerapproot", "options", "sethandler"}
        ][:70],
        "shared_django_project_exists": SHARED.is_dir(),
        "standalone_gateway_safe_to_deploy": False,
        "production_code_changed": False,
        "payment_enabled": False,
    }


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True))
