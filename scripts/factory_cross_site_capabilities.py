#!/usr/bin/env python3
"""Cross-site factory capabilities: byte-for-byte provenance + read-only QA adapter.

Factory may reuse *logic*, not site credentials, schedulers, production data or
site-specific writes. Import candidates are isolated; no live deployment,
agent activation, payments, publication, promotion or version inflation.
Python 3.8+; standard library only.
"""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
from html import unescape
import json
from pathlib import Path
import re

SCHEMA = "saeit.factory.cross-site-capabilities.v1"
SOURCES = (
    ("zomorod", "content/zomorod-v11/site_agents.php",
     "ops/factory-site-capabilities/zomorod/site_agents.php"),
    ("zomorod", "content/zomorod-v11/site_agent_workforce.php",
     "ops/factory-site-capabilities/zomorod/site_agent_workforce.php"),
    ("mojplaywin", "command_center/mpw_private_telemetry.py",
     "ops/factory-site-capabilities/mojplaywin/mpw_private_telemetry.py"),
)
MAX_SOURCE = 100_000
MAX_HTML = 768 * 1024
_EXPECTED_ZM = ("master", "content", "seo", "commerce", "agriculture",
                "research", "economic", "weather", "quality", "media", "security")
_KIND = ("ROLE_CODES", "FIVE", "SIX")


def safe_bytes(path, max_size=MAX_SOURCE):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= max_size:
        raise ValueError("CROSS_SITE_UNSAFE_OR_MISSING_SOURCE:" + path.name)
    return path.read_bytes()


def hash_value(blob):
    return hashlib.sha256(blob).hexdigest()


def mpw_named_roles(source):
    tree = ast.parse(source.decode("utf-8"), filename="mpw_private_telemetry.py")
    groups = {}
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id in _KIND:
                    groups[target.id] = tuple(ast.literal_eval(stmt.value))
    if any(name not in groups or not groups[name] for name in _KIND):
        raise ValueError("MPW_ROLE_REGISTRY_NOT_FOUND")
    if len(groups["ROLE_CODES"]) != 11 or len(groups["FIVE"]) != 5 or len(groups["SIX"]) != 6:
        raise ValueError("MPW_ROLE_REGISTRY_SIZE_CHANGED_REVIEW_REQUIRED")
    if any(not isinstance(x, str) or not re.fullmatch("[a-z_]{3,40}", x)
           for values in groups.values() for x in values):
        raise ValueError("MPW_UNSAFE_ROLE_IDENTIFIER")
    return groups


def zomorod_named_roles(source):
    code = source.decode("utf-8")
    begin = code.find("['master',")
    end = code.find("];", begin)
    if begin < 0 or end < begin:
        raise ValueError("ZM_AGENT_SEED_NOT_FOUND")
    roles = tuple(re.findall(r"\['([a-z]+)'\s*,", code[begin:end]))
    if roles != _EXPECTED_ZM:
        raise ValueError("ZM_AGENT_REGISTRY_CHANGED_REVIEW_REQUIRED")
    return roles


def audit_repo(repo):
    root = Path(repo).resolve()
    records = []
    for site, origin, imported in SOURCES:
        data = safe_bytes(root / origin)
        copied = safe_bytes(root / imported)
        if copied != data:
            raise ValueError("CROSS_SITE_COPY_MISMATCH:" + imported)
        records.append({"site": site, "origin": origin, "factory_candidate": imported,
                        "sha256": hash_value(data), "bytes": len(data),
                        "identical_source_copy": True,
                        "isolated_candidate_only": True})
    zm = zomorod_named_roles(safe_bytes(root / SOURCES[0][1]))
    mpw = mpw_named_roles(safe_bytes(root / SOURCES[2][1]))
    # Comparable *capabilities* only: Gen64/Gen65/Factory Gen50 are distinct
    # role lineages, not numerically comparable software versions.
    return {
        "schema": SCHEMA, "imported_source_files": len(records),
        "sources": records,
        "zomorod_site_agents": list(zm),
        "mojplaywin_health_roles": list(mpw["ROLE_CODES"]),
        "mojplaywin_private_robot_groups": {
            "five": list(mpw["FIVE"]), "six": list(mpw["SIX"])},
        "mojplaywin_private_robot_roles": len(mpw["FIVE"]) + len(mpw["SIX"]),
        "mojplaywin_module_slots": 77,
        "module_names_retrieved_from_private_runtime": False,
        "newly_activated_factory_agents": 0,
        "production_site_modified": False,
        "factory_private_vps_install_verified": False,
        "site_generations_directly_comparable_to_factory": False,
        "manual_compatibility_and_independent_tests_required": True,
    }


def html_quality(http_status, content_type, raw, error=""):
    """Pure offline reuse of Zomorod's HTML checks for factory web deliverables.

    This is a *review score*, never a commercial QA receipt.
    """
    if not isinstance(raw, bytes) or len(raw) > MAX_HTML:
        raise ValueError("FACTORY_HTML_OVERSIZED_OR_INVALID")
    if (http_status != 200 or error or
            not isinstance(content_type, str) or
            not content_type.lower().startswith("text/html") or len(raw) < 64):
        return {"status": "blocked", "score": 0, "issues": ["invalid_html_observation"],
                "html_sha256": hash_value(raw)}
    body = raw.decode("utf-8", "replace")
    mt = re.search(r"<title\b[^>]*>(.*?)</title\s*>", body, flags=re.I | re.S)
    title = unescape(re.sub(r"<[^>]+>", "", mt.group(1)) if mt else "")
    title = " ".join(title.split())
    h1 = len(re.findall(r"<h1(?:\s[^>]*)?>", body, flags=re.I))
    anchors = len(re.findall(r"<a\b[^>]*\bhref\s*=", body, flags=re.I))
    description = ""
    for tag in re.findall(r"<meta\b[^>]*>", body, flags=re.I | re.S):
        if re.search(r"""\bname\s*=\s*(['"])description\1""", tag, re.I):
            val = re.search(r"""\bcontent\s*=\s*(['"])(.*?)\1""", tag, re.I | re.S)
            if val:
                description = unescape(val.group(2)).strip()
                break
    issues = []
    if not title:
        issues.append("missing_title")
    elif len(title) > 100:
        issues.append("title_over_100_chars")
    if h1 != 1:
        issues.append("h1_count_not_one")
    if not description:
        issues.append("missing_meta_description")
    if anchors == 0:
        issues.append("no_anchor_links")
    return {"status": "review", "score": max(0, 100 - 25 * len(issues)),
            "issues": issues, "title": title, "h1_count": h1,
            "anchors": anchors, "html_sha256": hash_value(raw),
            "publish_approved": False}


def telemetry_state(raw_state, observed_at, now=None, ttl_seconds=7200):
    """Port MojPlayWin's evidence TTL; never promote an import to live execution."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("TZ_REQUIRED")
    if not isinstance(observed_at, str):
        return "unknown"
    try:
        observed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        if observed.tzinfo is None:
            return "unknown"
    except (ValueError, TypeError):
        return "unknown"
    age = (now - observed.astimezone(timezone.utc)).total_seconds()
    if age < -60 or age > ttl_seconds:
        return "stale"
    if raw_state in ("ok", "healthy", "success", "active_private",
                     "gen65_operational_private", "active_private_learning"):
        return "healthy"
    if raw_state == "loaded_only":
        return "loaded_only"
    if raw_state in ("warning", "degraded"):
        return "degraded"
    if raw_state in ("error", "failed"):
        return "failed"
    return "unknown"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--html-file")
    args = parser.parse_args()
    report = audit_repo(args.repo)
    if args.html_file:
        report["offline_web_preview"] = html_quality(
            200, "text/html", safe_bytes(args.html_file, MAX_HTML))
    print("FACTORY_CROSS_SITE_IMPORT_AUDIT=" + json.dumps(report, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
