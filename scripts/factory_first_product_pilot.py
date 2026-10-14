#!/usr/bin/env python3
"""VPS-local first-product pilot: evidence dossier only, never publishes or charges.

No network, LLM calls, Django writes, DB writes or product activation. Python 3.8+.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile


def decode(value):
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            pass
    return {}


def linked(conn, table, key, value):
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if table not in tables:
        return []
    columns = {row[1] for row in conn.execute("PRAGMA table_info(" + table + ")")}
    if key not in columns:
        return []
    return [dict(row) for row in conn.execute("SELECT * FROM " + table + " WHERE " + key + "=? ORDER BY id", (value,))]


def prepare(conn, forced_product_id=None):
    columns = {row[1] for row in conn.execute("PRAGMA table_info(core_product)")}
    required = {"id", "title", "metadata", "owner_id", "knowledge_article_id", "price", "active"}
    if not required.issubset(columns):
        raise RuntimeError("PRODUCT_SCHEMA_INCOMPATIBLE")
    order = "factory_managed DESC, id ASC" if "factory_managed" in columns else "id ASC"
    if forced_product_id is None:
        row = conn.execute("SELECT * FROM core_product ORDER BY " + order + " LIMIT 1").fetchone()
    else:
        row = conn.execute("SELECT * FROM core_product WHERE id=?", (forced_product_id,)).fetchone()
    if row is None:
        raise RuntimeError("NO_EXISTING_PRODUCT")
    product = dict(row)
    metadata = decode(product.get("metadata"))
    if not isinstance(metadata, dict):
        metadata = {}
    validation = metadata.get("validation") or {}
    if not isinstance(validation, dict):
        validation = {}
    missing = validation.get("missing_factors")
    if not isinstance(missing, list):
        missing = []
    runs = linked(conn, "core_factoryrun", "product_id", product["id"])
    projects = []
    for run in runs:
        projects += linked(conn, "core_researchproject", "factory_run_id", run["id"])
    sources, evidence, findings, reports = [], [], [], []
    for project in projects:
        pid = project["id"]
        sources += linked(conn, "core_researchsource", "project_id", pid)
        evidence += linked(conn, "core_evidence", "project_id", pid)
        findings += linked(conn, "core_finding", "project_id", pid)
        reports += linked(conn, "core_report", "project_id", pid)
    source_urls = {s.get("url", "").strip() for s in sources if isinstance(s.get("url"), str) and s["url"].strip()}
    issues = []
    if product.get("active"):
        issues.append("ALREADY_ACTIVE")
    if not product.get("owner_id"):
        issues.append("MISSING_PRODUCT_OWNER")
    if not product.get("knowledge_article_id"):
        issues.append("NO_APPROVED_KNOWLEDGE_ARTICLE")
    if float(product.get("price") or 0) <= 0:
        issues.append("NO_POSITIVE_PRICE")
    if missing:
        issues.append("VALIDATION_MISSING_FACTORS")
    if str(validation.get("outcome", "")).upper() not in ("PASS", "APPROVED"):
        issues.append("VALIDATION_NOT_PASSED")
    if len(source_urls) < 2:
        issues.append("FEWER_THAN_TWO_DISTINCT_SOURCE_URLS")
    if len(evidence) < 3:
        issues.append("FEWER_THAN_THREE_EVIDENCE_RECORDS")
    if not reports:
        issues.append("MISSING_RESEARCH_REPORT")
    return {
        "schema_version": 1,
        "product_id": product["id"],
        "title": product.get("title"),
        "validation_outcome": validation.get("outcome"),
        "factory_state": metadata.get("factory_state"),
        "missing_factors": missing,
        "issues": issues,
        "sources": [{"id":s.get("id"),"title":s.get("title"),"publisher":s.get("publisher"),"url":s.get("url")} for s in sources],
        "evidence": [{"id":e.get("id"),"source_id":e.get("source_id"),"passage":e.get("passage"),"confidence":e.get("confidence")} for e in evidence],
        "findings": [{"id":f.get("id"),"statement":f.get("statement"),"limitation":f.get("limitation"),"confidence":f.get("confidence")} for f in findings],
        "reports": [{"id":r.get("id"),"title":r.get("title"),"status":r.get("status"),"content":decode(r.get("content")) or r.get("content")} for r in reports],
        "status": "PRIVATE_INTERNAL_DRAFT_NOT_FOR_SALE",
    }


def draft_markdown(bundle):
    lines = [
        "# INTERNAL PRODUCT RESEARCH DRAFT — NOT FOR SALE",
        "",
        "Product ID: " + str(bundle["product_id"]),
        "Title: " + str(bundle.get("title") or "(untitled)"),
        "",
        "This draft records existing research only. Claims and sources still need review.",
        "No store, payment, owner approval or product visibility is changed by this tool.",
        "",
        "## Quality blockers",
    ]
    lines += ["- " + str(x) for x in bundle["issues"]] or ["- Independent editorial and owner approval remain mandatory"]
    lines += ["", "## Missing validation factors"]
    lines += ["- " + str(x) for x in bundle["missing_factors"]] or ["- None listed; independent review still mandatory"]
    lines += ["", "## References — verify provenance before customer use"]
    for s in bundle["sources"]:
        lines.append("- " + str(s.get("title") or "Untitled") + " | " + str(s.get("publisher") or "Publisher unverified") + " | " + str(s.get("url") or "Missing URL"))
    lines += ["", "## Existing evidence (unverified)"]
    for e in bundle["evidence"]:
        lines += ["### Evidence " + str(e.get("id")) + " / source " + str(e.get("source_id")), str(e.get("passage") or ""), ""]
    lines += ["", "## Existing findings (provisional)"]
    for f in bundle["findings"]:
        lines.append("- " + str(f.get("statement") or "") + " | Limitations: " + str(f.get("limitation") or "unspecified"))
    lines += ["", "## Research reports (raw internal material)"]
    for r in bundle["reports"]:
        c = r.get("content")
        lines += ["### Report " + str(r.get("id")) + " | " + str(r.get("status")), json.dumps(c, ensure_ascii=False, indent=2) if isinstance(c, (dict, list)) else str(c), ""]
    lines += [
        "## Required next steps",
        "1. Verify factual evidence from independent authoritative sources.",
        "2. Resolve all missing validation factors and rerun the established quality gate.",
        "3. Build a complete original licensed customer-facing deliverable.",
        "4. Set ownership, fair price and allowed destination marketplaces.",
        "5. Request explicit owner approval before activation or external publication.",
        "",
    ]
    return "\n".join(lines)


def write_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(str(path.parent), 0o700)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--product-id", type=int)
    ap.add_argument("--prepare", action="store_true")
    args = ap.parse_args(argv)
    db = Path(args.db).expanduser().resolve()
    if not db.is_file():
        raise RuntimeError("FACTORY_DATABASE_MISSING")
    conn = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only=ON")
        bundle = prepare(conn, args.product_id)
    finally:
        conn.close()
    print("FIRST_PRODUCT_PILOT_PRODUCT_ID=" + str(bundle["product_id"]))
    print("FIRST_PRODUCT_PILOT_ISSUE_COUNT=" + str(len(bundle["issues"])))
    print("FIRST_PRODUCT_PILOT_MISSING_FACTORS=" + str(len(bundle["missing_factors"])))
    print("FIRST_PRODUCT_PILOT_SOURCES=" + str(len(bundle["sources"])))
    print("FIRST_PRODUCT_PILOT_EVIDENCE=" + str(len(bundle["evidence"])))
    print("FIRST_PRODUCT_PILOT_REPORTS=" + str(len(bundle["reports"])))
    print("FIRST_PRODUCT_PILOT_APPROVAL_REQUIRED=true")
    print("FIRST_PRODUCT_PILOT_NO_PUBLISH_NO_DB_WRITE=true")
    if args.prepare:
        directory = Path(args.out).expanduser().resolve() / ("product-" + str(bundle["product_id"]))
        serialized = json.dumps(bundle, sort_keys=True, ensure_ascii=False, indent=2)
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        digest_path = directory / "sha256.txt"
        if digest_path.is_file() and digest_path.read_text(encoding="utf-8").strip() == digest:
            print("FIRST_PRODUCT_PILOT_UNCHANGED=true")
        else:
            write_atomic(directory / "evidence_manifest.json", serialized + "\n")
            write_atomic(directory / "internal_draft.md", draft_markdown(bundle))
            write_atomic(digest_path, digest + "\n")
            print("FIRST_PRODUCT_PILOT_PRIVATE_FILES_CREATED=true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
