#!/usr/bin/env python3
"""Publish ONE QA-tested Saeit offline toolkit as a free public download.

Uses already-delivered, checksum-verified private cPanel warehouse artifacts.
Creates a new isolated static versioned directory beneath a verified web root.
Never changes Django, store product active state, payment APIs, or other sites.
Publication is deliberately limited to farm_enterprise_economics version 1.
"""
import argparse
import hashlib
import html
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

RECIPE = "farm_enterprise_economics"
PUBLIC_SLUG = "farm-enterprise-economics-v1"
PUBLIC_FILENAME = "Farm_Enterprise_Economics_Toolkit_Free_v1.zip"
PUBLIC_URL = "https://mojplaywin.com/factory-releases/" + PUBLIC_SLUG + "/"
MAX_BYTES = 25 * 1024 * 1024


def _receiver():
    path = Path(__file__).resolve().parent / "store_receiver.py"
    if not path.is_file():
        raise ValueError("STORE_RECEIVER_NOT_INSTALLED")
    spec = importlib.util.spec_from_file_location("saeit_publication_verifier", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def landing_page(sha):
    if not re.fullmatch("[0-9a-f]{64}", sha):
        raise ValueError("INVALID_SHA256")
    title = "Farm Enterprise Economics Toolkit — Free Edition"
    description = ("A practical offline calculator for farm enterprise contributions, "
                   "break-even quantities and price/volume sensitivity scenarios.")
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="index,follow">
<title>""" + html.escape(title) + """ | MojPlayWin</title>
<meta name="description" content=\"""" + html.escape(description, quote=True) + """\">
<link rel="canonical" href=\"""" + PUBLIC_URL + """\">
<style>
:root{color-scheme:dark;font-family:system-ui,-apple-system,Segoe UI,Arial,sans-serif}
*{box-sizing:border-box}
body{margin:0;background:#101b24;color:#ecf4f4;line-height:1.55}
main{max-width:970px;margin:auto;padding:40px 22px 85px}
nav{font-size:.92rem;color:#c7d8e2;margin-bottom:55px}
nav a{color:#b9e4f8;text-decoration:none}
.eyebrow{color:#f6c981;letter-spacing:.12em;text-transform:uppercase;font-size:.82rem}
h1{font-size:clamp(2.2rem,6vw,4rem);letter-spacing:-.04em;line-height:1.15;margin:.45em 0}
p{max-width:730px}
.lead{font-size:1.2rem;color:#d7e5e9}
.cta{display:inline-block;margin-top:20px;padding:15px 23px;background:#f4c76c;
color:#13202b;border-radius:10px;text-decoration:none;font-weight:800}
.cta:focus,.cta:hover{background:#ffe2a7;outline-offset:4px}
.card{border:1px solid #344752;border-radius:16px;background:#182a35;padding:22px;margin:25px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:18px}
h2{font-size:1.4rem}
ul{padding-left:1.2em}
li{margin:.4em 0}
small,.muted{color:#bdd0d9}
code{overflow-wrap:anywhere;word-break:break-word}
footer{margin-top:50px;border-top:1px solid #344752;padding-top:25px;color:#c2d1d6;font-size:.95rem}
</style>
</head>
<body>
<main>
<nav><a href="https://mojplaywin.com/">MojPlayWin</a> / Digital Tools / Farm Enterprise Economics</nav>
<p class="eyebrow">Independent Factory Release · Version 1.0</p>
<h1>Farm Enterprise<br>Economics Toolkit</h1>
<p class="lead">An offline, downloadable calculator that helps compare farm business units
using your own selling prices, units sold and operating costs.</p>
<a class="cta" href=\"""" + PUBLIC_FILENAME + """" download>Download the Free Toolkit (ZIP)</a>
<p class="muted">No account, payment, API key, or internet connection is needed to run the calculator.</p>
<section class="grid">
<div class="card"><h2>Enterprise economics</h2><p>Calculate gross revenue, selling fees,
variable costs, contribution margin and operating profit for up to 100 enterprises.</p></div>
<div class="card"><h2>Break-even analysis</h2><p>Estimate the units needed to cover allocated
fixed costs when contribution per unit is positive.</p></div>
<div class="card"><h2>Scenario analysis</h2><p>Examine nine combinations of selling-price and
volume changes for each enterprise and export results to JSON or CSV.</p></div>
</section>
<section class="card">
<h2>Get started</h2>
<ol>
<li>Download and extract the ZIP archive.</li>
<li>Install Python 3.8 or newer (standard library only).</li>
<li>Replace all sample inputs in <code>example_inputs.json</code> with your own data.</li>
<li>Run <code>python calculator.py example_inputs.json --json-output results.json --csv-output scenarios.csv</code>.</li>
<li>Read the bundled README and run <code>python -m unittest -v test_calculator.py</code> if desired.</li>
</ol>
</section>
<section class="card">
<h2>Important limitations</h2>
<p>This is a deterministic educational planning tool, not an investment or yield
forecast. The example figures are synthetic, not current market prices.
Depreciation, taxes, borrowing costs, working capital, capital expenditure,
inflation and cash-flow timing are not modeled. Validate your inputs and seek
qualified professional advice for investment decisions.</p>
<p>The downloadable edition is provided for evaluation without charge.
There is no paid checkout associated with this release.</p>
</section>
<section class="card">
<h2>File integrity</h2>
<p>SHA-256 checksum of the downloadable ZIP:</p>
<p><code>""" + sha + """</code></p>
<p><a href="SHA256SUMS.txt" style="color:#b9e4f8">Download checksum record</a></p>
</section>
<footer>© 2026 Saeit Factory · An independent MojPlayWin digital tools release.
<a href="https://mojplaywin.com/" style="color:#b9e4f8">Back to MojPlayWin</a></footer>
</main>
</body>
</html>
"""


def secure_parent(webroot):
    webroot = Path(webroot).expanduser().absolute()
    if webroot.is_symlink() or not webroot.is_dir():
        raise ValueError("PUBLIC_ROOT_NOT_VERIFIED")
    if webroot.name != "mojplaywin.com":
        raise ValueError("WRONG_STOREFRONT_ROOT")
    parent = webroot / "factory-releases"
    if parent.is_symlink():
        raise ValueError("PARENT_SYMLINK_FORBIDDEN")
    if not parent.exists():
        parent.mkdir(mode=0o755)
    if not parent.is_dir() or parent.is_symlink():
        raise ValueError("PARENT_NOT_DIRECTORY")
    os.chmod(str(parent), 0o755)
    return parent


def prepare_private_product(inbox):
    inbox = Path(inbox).expanduser().absolute()
    if inbox.is_symlink() or not inbox.is_dir():
        raise ValueError("SOURCE_INBOX_NOT_VERIFIED")
    receiver = _receiver()
    receipt_dir = inbox / "receipts" / RECIPE
    receipts = sorted(receipt_dir.glob("*.json")) if receipt_dir.is_dir() else []
    verified = []
    for receipt in receipts:
        digest = receipt.stem
        if re.fullmatch(r"[0-9a-f]{64}", digest) and receiver.status(inbox, RECIPE, digest):
            verified.append(digest)
    if len(verified) != 1:
        raise ValueError("REQUIRE_EXACTLY_ONE_VERIFIED_RELEASE")
    digest = verified[0]
    src = inbox / "packages" / RECIPE / (digest + ".zip")
    manifest_path = inbox / "packages" / RECIPE / (digest + ".json")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not (data.get("qa_status") == "passed"
            and data.get("recipe") == RECIPE
            and data.get("commercial_status") == "private_internal_qa_pass_not_published"
            and data.get("price") is None
            and data.get("owner_publication_approval") is False
            and data.get("public_listing_enabled") is False):
        raise ValueError("PRODUCT_RELEASE_GATE_FAILED")
    if not 0 < src.stat().st_size <= MAX_BYTES or digest_file(src) != digest:
        raise ValueError("BAD_SOURCE_PACKAGE")
    guardpath=Path(__file__).resolve().with_name("factory_commercial_quality_release_guard_v1.py")
    if guardpath.is_symlink() or not guardpath.is_file():
        raise ValueError("SIGNED_1000_PUBLICATION_GUARD_UNAVAILABLE")
    spec=importlib.util.spec_from_file_location("factory_1000_public_guard",str(guardpath))
    guard=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    clearance=guard.require_quality_clearance(inbox,RECIPE,digest,data,src)
    if (clearance.get("status")!="VERIFIED_SIGNED_PREMIUM_1000"
            or clearance.get("1000_quality_verified") is not True):
        raise ValueError("QC1000_REQUIRED_FOR_FACTORY_EXIT")
    return digest, src


def publish(inbox, webroot, *, release_authorized=False):
    if release_authorized is not True:
        raise ValueError("EXPLICIT_PUBLICATION_AUTHORIZATION_REQUIRED")
    digest, source = prepare_private_product(inbox)
    parent = secure_parent(webroot)
    public_dir = parent / PUBLIC_SLUG
    if public_dir.is_symlink():
        raise ValueError("PUBLIC_RELEASE_SYMLINK_FORBIDDEN")
    if public_dir.exists():
        checksums = public_dir / "SHA256SUMS.txt"
        package = public_dir / PUBLIC_FILENAME
        if (checksums.is_file() and not checksums.is_symlink()
                and package.is_file() and not package.is_symlink()
                and digest_file(package) == digest
                and checksums.read_text(encoding="utf-8").strip() ==
                  digest + "  " + PUBLIC_FILENAME):
            return {"status": "existing_valid_release", "sha256": digest, "url": PUBLIC_URL}
        raise ValueError("REFUSING_TO_REPLACE_EXISTING_PUBLIC_RELEASE")
    stage = Path(tempfile.mkdtemp(prefix=".saeit-release-", dir=str(parent)))
    try:
        stage.chmod(0o755)
        package = stage / PUBLIC_FILENAME
        with source.open("rb") as src, package.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        if digest_file(package) != digest:
            raise ValueError("PUBLIC_PACKAGE_HASH_MISMATCH")
        package.chmod(0o644)
        checksum = stage / "SHA256SUMS.txt"
        checksum.write_text(digest + "  " + PUBLIC_FILENAME + "\n", encoding="utf-8")
        checksum.chmod(0o644)
        home = stage / "index.html"
        home.write_text(landing_page(digest), encoding="utf-8")
        home.chmod(0o644)
        os.replace(str(stage), str(public_dir))
    finally:
        if stage.exists():
            shutil.rmtree(str(stage))
    return {"status": "published_public_free_download", "sha256": digest, "url": PUBLIC_URL}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--inbox", required=True)
    parser.add_argument("--webroot", required=True)
    parser.add_argument("--authorize-publication", action="store_true")
    args = parser.parse_args(argv)
    result = publish(args.inbox, args.webroot, release_authorized=args.authorize_publication)
    print("FACTORY_RELEASE_STATUS=" + result["status"])
    print("FACTORY_RELEASE_URL=" + result["url"])
    print("FACTORY_RELEASE_SHA256=" + result["sha256"])
    print("FACTORY_RELEASE_PRICE=FREE")
    print("FACTORY_RELEASE_PAYMENT_ENABLED=false")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError) as error:
        print("FACTORY_PUBLICATION_FAILED=" + type(error).__name__ + ":" + str(error)[:140],
              file=sys.stderr)
        sys.exit(1)
