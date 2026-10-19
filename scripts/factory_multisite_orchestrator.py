#!/usr/bin/env python3
"""VPS-local, noncommercial multi-site distribution preparation.

Never modifies a website, dispatches over network or changes product approval.
New sites become eligible through the private registry after owner/adapter checks.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile
from urllib.parse import urlsplit

IDENT = re.compile(r"^[a-z][a-z0-9_-]{1,64}$")
HASH = re.compile(r"^[0-9a-f]{64}$")
REVIEWS = ("content", "rights", "security", "compatibility", "safety")


def load(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 200000:
        raise ValueError("UNTRUSTED_REGISTRY_OR_REVIEW_FILE")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("INVALID_OBJECT")
    return value


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(65536), b""):
            h.update(part)
    return h.hexdigest()


def verify_site(site):
    if not isinstance(site, dict) or not IDENT.fullmatch(str(site.get("id", ""))):
        raise ValueError("INVALID_SITE_ID")
    url = str(site.get("url", ""))
    u = urlsplit(url)
    if (u.scheme != "https" or not u.hostname or u.username or u.password
            or u.port or u.query or u.fragment or ".." in (u.path or "/").split("/")
            or not re.fullmatch(r"[a-z0-9.-]+", u.hostname)):
        raise ValueError("UNSAFE_SITE_ORIGIN")
    if site.get("status") not in ("pending", "active", "disabled"):
        raise ValueError("INVALID_SITE_STATUS")
    if not isinstance(site.get("topics"), list) or any(
        not IDENT.fullmatch(str(t)) for t in site["topics"]
    ):
        raise ValueError("INVALID_SITE_TOPICS")
    if site["status"] == "active" and not (
        site.get("owner_verified") is True and site.get("adapter_verified") is True
    ):
        raise ValueError("UNVERIFIED_ACTIVE_SITE")
    return site


def verify_product(root, approvals, recipe):
    if not IDENT.fullmatch(recipe):
        raise ValueError("INVALID_PRODUCT_SLUG")
    folder = root / "digital-products" / recipe
    manifest = load(folder / "manufacturing_manifest.json")
    archive = folder / (recipe + "-internal-qa.zip")
    if archive.is_symlink() or not archive.is_file() or archive.stat().st_size > 25 * 1024 * 1024:
        raise ValueError("ARTIFACT_MISSING_OR_UNSAFE")
    sha = digest(archive)
    if (manifest.get("recipe") != recipe or manifest.get("qa_status") != "passed"
            or manifest.get("artifact_sha256") != sha
            or not HASH.fullmatch(str(manifest.get("source_sha256", "")))):
        raise ValueError("TECHNICAL_QA_UNVERIFIED")
    with zipfile.ZipFile(archive) as zipped:
        entries = zipped.infolist()
        if not entries or len(entries) > 80 or sum(x.file_size for x in entries) > 100 * 1024 * 1024:
            raise ValueError("UNSAFE_ARCHIVE_SIZE")
        for entry in entries:
            parts = entry.filename.split("/")
            if (entry.is_dir() or len(parts) < 2 or parts[0] != recipe
                    or any(p in ("", ".", "..") for p in parts)
                    or "\\" in entry.filename or
                    (entry.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError("UNSAFE_ZIP_ENTRY")
        if zipped.testzip() is not None:
            raise ValueError("ZIP_CRC_FAILED")
    ticket = root / "qa-rework" / recipe / "ledger.json"
    if ticket.is_symlink():
        raise ValueError("UNSAFE_DEFECT_LEDGER")
    if ticket.exists() and load(ticket).get("current_status") in ("needs_rework", "expert_review"):
        raise ValueError("OPEN_QA_DEFECT")
    review = load(approvals / (recipe + ".json"))
    if (review.get("schema") != "saeit.factory.distribution-review.v1"
            or review.get("artifact_sha256") != sha
            or review.get("source_sha256") != manifest["source_sha256"]
            or review.get("status") != "approved"
            or review.get("sale_required") is not False
            or not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip()):
        raise ValueError("NO_APPROVED_NONCOMMERCIAL_RELEASE")
    checks = review.get("checks")
    if not isinstance(checks, dict) or any(
        not isinstance(checks.get(k), dict) or checks[k].get("passed") is not True
        or len(str(checks[k].get("evidence", "")).strip()) < 12
        for k in REVIEWS
    ):
        raise ValueError("DISTRIBUTION_QA_INCOMPLETE")
    topics = review.get("topics")
    if not isinstance(topics, list) or not topics or any(
        not IDENT.fullmatch(str(x)) for x in topics
    ):
        raise ValueError("UNREVIEWED_PRODUCT_TOPICS")
    return {"id": recipe, "sha256": sha, "topics": sorted(set(topics)),
            "release": "approved_noncommercial", "sale_required": False}


def save(path, value):
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink() or path.is_symlink():
        raise ValueError("UNSAFE_OUTPUT")
    os.chmod(path.parent, 0o700)
    if path.is_file() and path.read_text(encoding="utf-8") == data:
        return
    fd, temp = tempfile.mkstemp(prefix=".dist-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def build(registry, root, approvals, output):
    registry = load(Path(registry))
    if registry.get("schema") != "saeit.factory.sites.v1":
        raise ValueError("REGISTRY_SCHEMA")
    sites = registry.get("sites")
    if not isinstance(sites, list):
        raise ValueError("SITES_NOT_A_LIST")
    ids = set()
    for site in sites:
        verify_site(site)
        if site["id"] in ids:
            raise ValueError("DUPLICATE_SITE")
        ids.add(site["id"])
    root, approvals, output = Path(root), Path(approvals), Path(output)
    candidates = root / "digital-products"
    approved, blocked = [], []
    if candidates.is_dir():
        for folder in sorted(candidates.iterdir()):
            if folder.is_dir() and not folder.is_symlink():
                try:
                    approved.append(verify_product(root, approvals, folder.name))
                except (ValueError, OSError, KeyError, json.JSONDecodeError) as e:
                    blocked.append({"product": folder.name, "reason": str(e)[:90]})
    stats = {"schema": "saeit.factory.distribution-state.v1",
             "sites_known": len(sites), "sites_active": 0,
             "products_approved": len(approved),
             "products_blocked": blocked, "site_catalogs": [],
             "publications_verified": 0, "sales_required": False,
             "status": "private_catalog_staging_only"}
    for site in sites:
        if site["status"] != "active":
            continue
        stats["sites_active"] += 1
        catalog = sorted(approved, key=lambda p: p["id"])
        featured = [p["id"] for p in catalog if set(p["topics"]) & set(site["topics"])]
        save(output / "sites" / site["id"] / "catalog.json", {
            "site_id": site["id"], "site_url": site["url"], "catalog": catalog,
            "featured_ids": featured, "public_update": False,
            "publication_receipt": None, "checkout_required": False,
        })
        stats["site_catalogs"].append({"site_id": site["id"],
             "catalog_count": len(catalog), "featured_count": len(featured)})
    save(output / "distribution-state.json", stats)
    return stats


def main():
    p = argparse.ArgumentParser()
    for arg in ("registry", "root", "approvals", "output"):
        p.add_argument("--" + arg, required=True)
    args = p.parse_args()
    result = build(args.registry, args.root, args.approvals, args.output)
    print("VPS_FACTORY_KNOWN_SITES=" + str(result["sites_known"]))
    print("VPS_FACTORY_ACTIVE_SITES=" + str(result["sites_active"]))
    print("VPS_FACTORY_QA_RELEASED_PRODUCTS=" + str(result["products_approved"]))
    print("VPS_FACTORY_PRIVATE_CATALOGS=" + str(len(result["site_catalogs"])))
    print("VPS_FACTORY_PUBLICATIONS_VERIFIED=0")
    print("VPS_FACTORY_SALES_REQUIRED=false")


if __name__ == "__main__":
    main()
