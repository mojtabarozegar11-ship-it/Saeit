#!/usr/bin/env python3
"""Lossless, main-domain-only Zomorod Melal staging patch.

No command in this module writes to the supplied live web root. The release
workflow owns the independently backed-up and guarded atomic publication.
"""

import argparse
import base64
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


OLD_CLAIM = "بزرگ ترین شرکت تحقیقات و پژوهش های علمی و ژنتیکی بخش خصوصی فعال در حوزه های کشاورزی"
NEW_CLAIM = "پژوهش و توسعه علمی، ژنتیک و فناوری در حوزه‌های کشاورزی"
ASSET_PREFIX = "/static/site/zm-home-media-20261027/"
IMAGE = re.compile(r"data:image/(svg\+xml|webp);base64,([A-Za-z0-9+/=]+)")
# Live production verification (runs 40479155440, 40479833776 and
# 40480556798) confirmed root-scoped mod_headers changes do not reach the
# public response. Preserve .htaccess byte for byte until the actual host
# response-header layer is available for a scoped fix.
STORE_LINK = '<a href="/contact/">تماس با شرکت</a>'
STORE_ADDITION = '<a href="/ask-master/index.php">ثبت پرسش و استعلام همکاری</a>'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate_svg(blob):
    root = ET.fromstring(blob)
    assert root.tag == "{http://www.w3.org/2000/svg}svg", "Unexpected SVG namespace"
    for node in root.iter():
        assert node.tag.rsplit("}", 1)[-1].lower() not in {
            "script", "foreignobject", "iframe", "object", "embed", "image"
        }, "Active SVG element"
        assert not any(k.rsplit("}", 1)[-1].lower().startswith("on") for k in node.attrib), "Active SVG attribute"
        assert not any("javascript:" in v.lower() for v in node.attrib.values()), "Script URL in SVG"


def stage(web, output):
    assert web.is_dir() and not web.is_symlink(), "Invalid source root"
    assert not output.exists(), "Candidate already exists"
    original = {}
    for name in ("index.html", "sitemap.xml", "store/index.php", ".htaccess"):
        path = web / name
        assert path.is_file() and not path.is_symlink(), name
        original[name] = path.read_bytes()
    home = original["index.html"].decode("utf-8")
    assert home.count("window.ZOMOROD_ORBIT_DATA=") == 1
    assert home.count(OLD_CLAIM) == 1 and NEW_CLAIM not in home

    replacements = {}
    blobs = {}
    mime_counts = {"svg+xml": 0, "webp": 0}

    def replace_image(match):
        mime, encoded = match.groups()
        blob = base64.b64decode(encoded, validate=True)
        if mime == "svg+xml":
            validate_svg(blob)
            ext = "svg"
        else:
            assert blob[:4] == b"RIFF" and blob[8:12] == b"WEBP", "Invalid WebP"
            ext = "webp"
        filename = digest(blob) + "." + ext
        url = ASSET_PREFIX + filename
        assert filename not in blobs or blobs[filename] == blob
        blobs[filename] = blob
        replacements[url] = {"mime": mime, "sha256": digest(blob), "size": len(blob)}
        mime_counts[mime] += 1
        return url

    converted = IMAGE.sub(replace_image, home)
    assert mime_counts["svg+xml"] >= 600 and mime_counts["webp"] >= 2, mime_counts
    # Preserve the tiny percent-encoded decorative CSS pattern; only base64
    # card imagery is externalized, so its exact CSS bytes remain untouched.
    assert not IMAGE.search(converted), "Unconverted base64 imagery"
    converted = converted.replace(OLD_CLAIM, NEW_CLAIM)
    assert len(converted.encode("utf-8")) < len(original["index.html"]) * 0.4, "No useful payload reduction"

    # A byte-preserving XML edit: the old sitemap body and all previous URLs
    # remain unmodified; only the already-live public store and topics hubs join.
    sitemap = original["sitemap.xml"].decode("utf-8")
    old_xml = ET.fromstring(sitemap)
    ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    assert old_xml.tag == ns + "urlset"
    original_urls = [x.findtext(ns + "loc") for x in old_xml.findall(ns + "url")]
    assert len(original_urls) >= 100 and len(original_urls) == len(set(original_urls))
    additions = []
    for url in ("https://zomorodmelal.ir/store/", "https://zomorodmelal.ir/topics/"):
        if url not in original_urls:
            additions.append("<url><loc>" + url + "</loc></url>")
    assert sitemap.count("</urlset>") == 1
    revised_sitemap = sitemap.replace("</urlset>", "".join(additions) + "</urlset>")
    check_xml = ET.fromstring(revised_sitemap)
    check_urls = [x.findtext(ns + "loc") for x in check_xml.findall(ns + "url")]
    assert check_urls[:len(original_urls)] == original_urls
    assert set(check_urls) == set(original_urls) | set(x.split("<loc>")[1].split("</loc>")[0] for x in additions)

    store = original["store/index.php"].decode("utf-8")
    assert STORE_ADDITION not in store and store.count(STORE_LINK) == 1, "Unexpected store source"
    revised_store = store.replace(STORE_LINK, STORE_LINK + ' · ' + STORE_ADDITION)
    assert revised_store.count("پرداخت آنلاین") >= store.count("پرداخت آنلاین"), "Payment gate changed"
    output.mkdir(parents=True, mode=0o700)
    staged = {
        "index.html": converted.encode("utf-8"),
        "sitemap.xml": revised_sitemap.encode("utf-8"),
        "store/index.php": revised_store.encode("utf-8"),
        ".htaccess": original[".htaccess"],
    }
    for rel, content in staged.items():
        target = output / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    asset_dir = output / ASSET_PREFIX.lstrip("/")
    asset_dir.mkdir(parents=True)
    asset_dir.chmod(0o755)
    for name, blob in blobs.items():
        asset = asset_dir / name
        asset.write_bytes(blob)
        asset.chmod(0o644)

    manifest = {
        "original": {k: digest(v) for k, v in original.items()},
        "candidate": {k: digest(v) for k, v in staged.items()},
        "homepage_bytes_before": len(original["index.html"]),
        "homepage_bytes_after": len(staged["index.html"]),
        "image_occurrences": mime_counts,
        "assets": replacements,
        "sitemap_old_count": len(original_urls),
        "sitemap_new_count": len(check_urls),
        "store_payment_remains_disabled": True,
        "root_frame_header_pending_host_configuration": True,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    verify(web, output)
    print("ZM_SIX_STAGE=passed")
    print("HOME_BEFORE_BYTES=" + str(manifest["homepage_bytes_before"]))
    print("HOME_AFTER_BYTES=" + str(manifest["homepage_bytes_after"]))
    print("EXTERNALIZED_IMAGES=" + str(len(blobs)))
    print("SITEMAP_URLS=" + str(len(original_urls)) + "->" + str(len(check_urls)))


def verify(web, output):
    manifest = json.loads((output / "manifest.json").read_text("utf-8"))
    for rel, expected in manifest["original"].items():
        assert digest((web / rel).read_bytes()) == expected, "Source changed: " + rel
    for rel, expected in manifest["candidate"].items():
        assert digest((output / rel).read_bytes()) == expected, "Candidate changed: " + rel
    home = (output / "index.html").read_text("utf-8")
    for url, info in manifest["assets"].items():
        assert home.count(url) >= 1, "Unreferenced asset: " + url
        blob = (output / url.lstrip("/")).read_bytes()
        assert digest(blob) == info["sha256"] and len(blob) == info["size"]
        base64_url = "data:image/" + info["mime"] + ";base64," + base64.b64encode(blob).decode("ascii")
        home = home.replace(url, base64_url)
    home = home.replace(NEW_CLAIM, OLD_CLAIM)
    assert home.encode("utf-8") == (web / "index.html").read_bytes(), "Not losslessly reversible"
    print("ZM_SIX_REVERSIBILITY=byte_identical")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("stage", "verify"))
    p.add_argument("web", type=Path)
    p.add_argument("candidate", type=Path)
    a = p.parse_args()
    (stage if a.mode == "stage" else verify)(a.web, a.candidate)
