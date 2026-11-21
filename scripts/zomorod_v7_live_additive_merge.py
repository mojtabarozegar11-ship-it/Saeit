#!/usr/bin/env python3
"""Fail-closed V7 additive PHP integration. Never writes production paths.

Inputs are a private live app.php copy and a pinned V7 repository app.php.
Output is a separate candidate file. Preserve all live code; inject narrowly
reviewed V7 imports, navigation, DB period checks, POST and GET routes.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re


class UnsafeMerge(RuntimeError):
    pass


MODULES = (
    "workflow_desk.php",
    "industry_operations.php",
    "finance_audit.php",
    "payroll_control.php",
    "payroll_ui.php",
    "period_controls.php",
)
PAGES = ("workflow_desk", "industry_ops", "finance_audit", "payroll", "period_controls")
ACTIONS = (
    "flow_create", "flow_transition", "industry_create", "industry_advance",
    "payroll_create", "payroll_decision", "period_freeze", "period_close",
)


def require_once(text: str, needle: str, description: str) -> None:
    if text.count(needle) != 1:
        raise UnsafeMerge(f"{description}: expected one unambiguous anchor, got {text.count(needle)}")


def section(text: str, start: str, stop: str, description: str) -> str:
    require_once(text, start, description + " start")
    require_once(text, stop, description + " stop")
    a, b = text.index(start), text.index(stop)
    if b <= a:
        raise UnsafeMerge(f"{description}: markers out of order")
    return text[a:b]


def merge(live: str, v7: str) -> str:
    if not live.startswith("<?php") or not v7.startswith("<?php"):
        raise UnsafeMerge("Both files must be PHP")
    if "verifyCsrf();" not in live or "function authorize(" not in live:
        raise UnsafeMerge("Live authentication or CSRF gate not identified")
    if "if(role()!=='admin')" not in live:
        raise UnsafeMerge("Owner-only agent/store privilege guard missing")
    for name in MODULES:
        if ("'/" + name + "'") in live:
            raise UnsafeMerge("Unexpected already-integrated module: " + name)
    for name in PAGES:
        if "$page==='" + name + "'" in live:
            raise UnsafeMerge("Unexpected already-integrated page: " + name)
    for name in ACTIONS:
        if "'" + name + "'" in live:
            raise UnsafeMerge("Unexpected already-integrated action: " + name)
    if "zmPeriodGuard($db,$date)" in live or "zmPeriodSchema($db)" in live:
        raise UnsafeMerge("Period controls may have already been integrated")

    result = live
    anchor = "$private = $home.'/.private/zomorod-business';\n"
    require_once(result, anchor, "private root")
    imports = "".join(
        "if(is_file($private.'/" + name + "')) require_once $private.'/" + name + "';\n"
        for name in MODULES if name != "period_controls.php"
    )
    # Period module is mandatory when enabling accounting closure controls.
    imports += "require_once $private.'/period_controls.php';\n"
    result = result.replace(anchor, anchor + imports, 1)

    # Inject checks into the existing functions. Do not replace their bodies.
    db_start = "function db(string $private): PDO {"
    record_start = "function record(PDO $db,string $number,string $date,string $note,string $cur,array $lines):int {\n"
    require_once(result, db_start, "db")
    require_once(result, record_start, "journal posting")
    db_segment = section(result, db_start, "function q(PDO $db", "db function")
    require_once(db_segment, "    return $db;", "db return")
    db_modified = db_segment.replace("    return $db;", "    zmPeriodSchema($db);\n    return $db;", 1)
    result = result.replace(db_segment, db_modified, 1)
    result = result.replace(record_start, record_start + "    zmPeriodGuard($db,$date);\n", 1)

    # Preserve installed layoutStart() CSS, branding and any site-only links.
    nav_marker = "$nav=["
    require_once(result, nav_marker, "navigation")
    nav_end = result.index("];", result.index(nav_marker))
    nav = result[result.index(nav_marker):nav_end + 2]
    v7_start = v7.index(nav_marker)
    v7_end = v7.index("];", v7_start)
    v7nav = v7[v7_start:v7_end + 2]
    additions = []
    for name in PAGES:
        if re.search(r"'" + re.escape(name) + r"'\s*=>", nav):
            raise UnsafeMerge("Navigation already includes: " + name)
        match = re.search(r"'" + re.escape(name) + r"'\s*=>\s*'[^']*'", v7nav)
        if not match:
            raise UnsafeMerge("Pinned V7 navigation label missing: " + name)
        additions.append(match.group(0))
    require_once(nav, "'accounts'=>", "navigation accounts")
    nav_new = nav.replace("'accounts'=>", ",".join(additions) + ",'accounts'=>", 1)
    result = result.replace(nav, nav_new, 1)

    # Extract executable branches from the pinned V7 source, preserving role
    # checks inside the modules; the existing outer CSRF gate remains in place.
    post_start = "} elseif(in_array($action,['flow_create','flow_transition'],true)){"
    post_stop = "} elseif($action==='user'){"
    page_start = "} elseif($page==='workflow_desk'){"
    page_stop = "} elseif($page==='agent_center'){"
    post_block = section(v7, post_start, post_stop, "V7 POST dispatcher")
    page_block = section(v7, page_start, page_stop, "V7 GET dispatcher")
    # Sensitive payroll and internal procurement/contract desk are never
    # exposed to a read-only viewer account.
    for name in ("workflow_desk", "payroll"):
        old = "} elseif($page==='" + name + "'){\n        authorize('view');"
        new = "} elseif($page==='" + name + "'){\n        if(!in_array(role(),['admin','manager','accountant'],true))bail('دسترسی کافی ندارید.',403);"
        if page_block.count(old) != 1:
            raise UnsafeMerge("Sensitive GET authorization anchor changed: " + name)
        page_block = page_block.replace(old, new, 1)
    require_once(result, post_stop, "live POST insertion")
    require_once(result, page_stop, "live GET insertion")
    result = result.replace(post_stop, post_block + post_stop, 1)
    result = result.replace(page_stop, page_block + page_stop, 1)
    # Re-check the authoritative database role on every authenticated request.
    # A demoted account must not retain a stale elevated session role.
    page_assignment = "$page=(string)($_GET['page']??'dashboard');"
    require_once(result, page_assignment, "authenticated page dispatcher")
    result = result.replace(page_assignment, "$_SESSION['role']=(string)$user['role'];\n    " + page_assignment, 1)

    if result == live or len(result) <= len(live):
        raise UnsafeMerge("Candidate did not expand correctly")
    for name in MODULES:
        needle = ("require_once $private.'/period_controls.php';" if name == "period_controls.php"
                  else "if(is_file($private.'/" + name + "'))")
        require_once(result, needle, "module: " + name)
    for name in PAGES:
        require_once(result, "$page==='" + name + "'", "page: " + name)
    for name in ACTIONS:
        if ("'" + name + "'") not in result:
            raise UnsafeMerge("POST action absent: " + name)
    require_once(result, "zmPeriodSchema($db)", "period schema")
    require_once(result, "zmPeriodGuard($db,$date)", "period posting guard")
    if "verifyCsrf();" not in result or "function authorize(" not in result:
        raise UnsafeMerge("Security invariant lost")
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--live", type=Path, required=True)
    p.add_argument("--v7", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--expected-live-sha256", required=True)
    args = p.parse_args()
    source = args.live.read_bytes()
    live_sha = hashlib.sha256(source).hexdigest()
    if not re.fullmatch(r"[0-9a-f]{64}", args.expected_live_sha256):
        raise UnsafeMerge("Invalid exact live fingerprint")
    if live_sha != args.expected_live_sha256:
        raise UnsafeMerge("Live app drifted since semantic audit: stop, do not overwrite")
    if args.out.exists():
        raise UnsafeMerge("Candidate output already exists")
    candidate = merge(source.decode("utf-8"), args.v7.read_text(encoding="utf-8"))
    args.out.write_text(candidate, encoding="utf-8")
    args.out.chmod(0o600)
    print("V7_CANDIDATE_GENERATED=YES")
    print("LIVE_APP_HASH_MATCH=YES")
    print("LIVE_FUNCTIONS_PRESERVED_BY_ADDITIVE_TRANSFORM=YES")
    print("LIVE_HOST_EXTENSIONS_PRESERVED=YES")
    print("CANDIDATE_SHA256=" + hashlib.sha256(candidate.encode()).hexdigest())
    print("CANDIDATE_NOT_PRODUCTION_ACTIVATED=YES")


if __name__ == "__main__":
    main()
