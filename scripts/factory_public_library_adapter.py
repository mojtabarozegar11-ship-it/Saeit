#!/usr/bin/env python3
"""Additive, site-scoped public directory for an ALREADY approved free release.

No Django, Passenger, .htaccess, customer orders, payment, database or site
template changes. Never replaces any pre-existing directory without this
script's own marker. All products link to canonical already-public files.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import os
import re
import tempfile

PRODUCT = "farm_enterprise_economics"
RELEASE = "farm-enterprise-economics-v1"
ZIP = "Farm_Enterprise_Economics_Toolkit_Free_v1.zip"
TITLE = "Farm Enterprise Economics Toolkit — Free Edition"
CANONICAL = "https://mojplaywin.com/factory-releases/" + RELEASE + "/index.html"
OWNER = "saeit.factory.public-resource-adapter.v1"
MARKER = ".saeit-factory-resource-owner.json"
ALLOWED = {
    "mojplaywin-main": ("mojplaywin.com", "MojPlayWin", "Digital tools"),
    "zomorod-main": ("public_html", "Zomorod Melal", "Research & tools"),
    "zomorod-tala": ("public_html/tala", "Zomorod Melal Gold", "Technical resources"),
}


def sha_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_release(home):
    root = home / "mojplaywin.com" / "factory-releases" / RELEASE
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("CANONICAL_RELEASE_ROOT_NOT_VERIFIED")
    checksum, archive, page = root / "SHA256SUMS.txt", root / ZIP, root / "index.html"
    for f in (checksum, archive, page):
        if f.is_symlink() or not f.is_file():
            raise RuntimeError("CANONICAL_RELEASE_ARTIFACT_MISSING")
    record = checksum.read_text(encoding="utf-8").strip()
    match = re.fullmatch(r"([0-9a-f]{64})  " + re.escape(ZIP), record)
    if not match or sha_file(archive) != match.group(1):
        raise RuntimeError("CANONICAL_RELEASE_HASH_NOT_VALID")
    body = page.read_text(encoding="utf-8")
    if "Farm Enterprise Economics Toolkit" not in body or match.group(1) not in body:
        raise RuntimeError("CANONICAL_RELEASE_CONTENT_NOT_VALID")
    return match.group(1)


def render(site_id, label, category, sha):
    url = html.escape(CANONICAL, quote=True)
    heading = html.escape(label)
    note = html.escape(category)
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="index,follow">
<title>Factory products | """ + heading + """</title>
<meta name="description" content="Reviewed free factory resources and tools.">
<style>
:root{color-scheme:light dark;font-family:system-ui,sans-serif}
body{margin:0;background:#111b25;color:#edf6fa;line-height:1.7}
main{max-width:880px;margin:0 auto;padding:50px 20px}
a{color:#aee5ff}a:focus-visible{outline:3px solid orange}
.card{padding:25px;background:#1c3140;border:1px solid #537181;border-radius:16px}
small{color:#c0d3dd}code{overflow-wrap:anywhere}
</style>
</head><body><main>
<a href="/">Home</a>
<h1>Factory products and resources</h1>
<p>""" + note + """. This is a shared resource library.
Products are distributed based on completed quality and usage checks, not sales.</p>
<section class="card" aria-label="Available resource">
<h2>Farm Enterprise Economics Toolkit — Free Edition</h2>
<p>A free offline farm-enterprise planning calculator. The examples are illustrative
and are not live market quotations or professional investment advice.</p>
<p><a href=\""""+url+"""\"><strong>Open the approved free toolkit and download</strong></a></p>
<small>Source verified by SHA-256: <code>""" + sha + """</code>.</small>
</section>
<p><small>No purchase, payment, registration, or API key is required.
Additional items are added only after their independent release checks pass.</small></p>
</main></body></html>
"""


def atomic_write(path, raw, *, mode=0o644):
    fd, temp = tempfile.mkstemp(prefix=".saeit-public-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(raw)
            file.flush()
            os.fsync(file.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def publish(home, site_id):
    home = Path(home).expanduser().resolve()
    if site_id not in ALLOWED:
        raise ValueError("SITE_NOT_ALLOWED")
    name, label, category = ALLOWED[site_id]
    root = home / name
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("SITE_ROOT_NOT_VERIFIED")
    if (root / "index.html").is_file() is False and (root / "passenger_wsgi.py").is_file() is False:
        # cPanel primary docroots may use PHP landing pages.
        if not (root / "index.php").is_file() and not (root / ".htaccess").is_file():
            raise RuntimeError("SITE_ROOT_NO_PROVEN_PUBLIC_ENTRY")
    checksum = verify_release(home)
    dest = root / "factory-products"
    if dest.is_symlink():
        raise RuntimeError("DESTINATION_SYMLINK")
    if dest.exists() and not dest.is_dir():
        raise RuntimeError("FACTORY_DIRECTORY_COLLISION")
    if dest.is_dir():
        marker = dest / MARKER
        if marker.is_symlink() or not marker.is_file():
            raise RuntimeError("EXISTING_NON_FACTORY_DIRECTORY_PROTECTED")
        owner = json.loads(marker.read_text(encoding="utf-8"))
        if owner != {"schema": OWNER, "site_id": site_id}:
            raise RuntimeError("FACTORY_DIRECTORY_OWNER_MISMATCH")
    else:
        dest.mkdir(mode=0o755)
    output = {
        "schema": OWNER,
        "site_id": site_id,
        "library_url": "/factory-products/index.html",
        "products": [{
            "id": PRODUCT, "title": TITLE, "free": True,
            "canonical_url": CANONICAL, "sha256": checksum,
            "status": "previously_publicly_released_and_checksum_verified",
            "quality_scope": "software_technical_QA_and_existing_release_review",
        }],
        "purchase_required": False,
    }
    atomic_write(dest / MARKER, (json.dumps({"schema": OWNER, "site_id": site_id},
                                           sort_keys=True) + "\n").encode(), mode=0o600)
    atomic_write(dest / "catalog.json", (json.dumps(output, sort_keys=True, indent=2) + "\n").encode())
    atomic_write(dest / "index.html", render(site_id, label, category, checksum).encode())
    return {"site_id": site_id, "status": "public_resource_page_prepared",
            "products": 1, "sha256": checksum}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--home", required=True)
    p.add_argument("--site-id", required=True, choices=sorted(ALLOWED))
    args = p.parse_args()
    print(json.dumps(publish(args.home, args.site_id), sort_keys=True))
