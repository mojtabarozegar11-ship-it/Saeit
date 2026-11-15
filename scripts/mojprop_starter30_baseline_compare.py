#!/usr/bin/env python3
"""Compare sanitized, READ-ONLY cPanel public page hashes to reviewed source.

Never treats a matching GitHub file as proof of the actual served HTTP route,
verified independent restore, isolation, payment authorization, or release.
No network, filesystem writes, migrations, customer data or raw HTML output.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import sys

SCHEMA = "mojprop.starter30.live_readonly.v1"
FILES = {
    "home": ("baselines/index-v4.html", "index.html"),
    "catalog": ("baselines/catalog-index-v4.html", "catalog/index.html"),
    "signal_desk": ("baselines/signals-index-before-free.html", "signals/index.html"),
    "sample_prop_blueprint": ("samples/prop-blueprint/index.html",),
    "sample_gold_market_brief": ("samples/gold-market-brief/index.html",),
    "sample_educational_signal": ("samples/educational-signal/index.html",),
    "sample_commercial_gate_audit": ("samples/commercial-gate-audit/index.html",),
}
PRODUCT = {
    "index.html": "starter-30-trx/index.html",
    "journal-template.csv": "starter-30-trx/journal-template.csv",
    "journal-guide.txt": "starter-30-trx/journal-guide.txt",
}
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX16 = re.compile(r"[0-9a-f]{16}\Z")


def _sha(path: Path) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 512_000:
        raise ValueError("reviewed static source is missing, symlinked or oversized")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _observed_status(info: object, expected: set, digest_len: int) -> str:
    if not isinstance(info, dict) or type(info.get("readable")) is not bool:
        raise ValueError("untrusted read-only evidence shape")
    digest = info.get("sha256" if digest_len == 64 else "sha256_prefix")
    if not info["readable"]:
        if digest is not None:
            raise ValueError("missing file supplied an unexpected digest")
        return "absent_or_unreadable"
    regex = HEX64 if digest_len == 64 else HEX16
    if type(digest) is not str or not regex.fullmatch(digest):
        raise ValueError("invalid or truncated readable file digest")
    return "reviewed_baseline_or_source" if digest in expected else "unknown_or_owner_modified"


def classify(evidence: dict, source_dir: Path) -> dict:
    """Bounded SHA-only comparison. No certificate of safe publication."""
    if not isinstance(evidence, dict) or evidence.get("schema") != SCHEMA:
        raise ValueError("wrong or missing cPanel evidence schema")
    if (evidence.get("read_only") is not True
            or evidence.get("release_permitted") is not False
            or evidence.get("revenue_proven") is not False):
        raise ValueError("unsafe cPanel evidence flags")
    if not source_dir.is_dir() or source_dir.is_symlink():
        raise ValueError("untrusted source directory")
    real_root = source_dir.resolve(strict=True)
    paths = evidence.get("public_page_digests")
    assets = evidence.get("assets")
    if not isinstance(paths, dict) or set(paths) != set(FILES):
        raise ValueError("incomplete public static page inventory")
    if not isinstance(assets, dict) or set(assets) != set(PRODUCT):
        raise ValueError("incomplete Starter30 product inventory")
    pages = {}
    for key, known_names in FILES.items():
        candidate_hashes = set()
        for name in known_names:
            candidate = source_dir / name
            # Strictly fixed paths; reject symlinks and any path outside source_dir.
            try:
                candidate.resolve(strict=True).relative_to(real_root)
            except (OSError, ValueError) as exc:
                raise ValueError("reviewed source path escaped or is missing") from exc
            candidate_hashes.add(_sha(candidate))
        pages[key] = _observed_status(paths[key], candidate_hashes, 64)

    product = {}
    for key, name in PRODUCT.items():
        source = source_dir / name
        try:
            source.resolve(strict=True).relative_to(real_root)
        except (OSError, ValueError) as exc:
            raise ValueError("reviewed Starter30 asset escaped or is missing") from exc
        product[key] = _observed_status(assets[key], {_sha(source)[:16]}, 16)

    known_legacy_baseline = all(
        pages[key] == "reviewed_baseline_or_source" for key in
        ("home", "catalog", "signal_desk")
    )
    existing_unknown = any(x == "unknown_or_owner_modified" for x in
                           list(pages.values()) + list(product.values()))
    result = {
        "schema": "mojprop.starter30.baseline_compare.v1",
        "public_pages": pages,
        "product_assets": product,
        "existing_home_catalog_signal_match_reviewed_source_or_baseline": known_legacy_baseline,
        "owner_edit_or_unknown_content_detected": existing_unknown,
        "missing_product_asset_count": sum(v == "absent_or_unreadable" for v in product.values()),
        "known_source_baseline_only": True,
        "http_route_verified": False,
        "customer_consent_or_sale_verified": False,
        "independent_restore_verified": False,
        "passenger_tenant_isolation_verified": False,
        "tron_merchant_or_payment_verified": False,
        "release_permitted": False,
    }
    # This classification is STRICTLY an input to a later review. It cannot
    # authorize a merge, a production write or a payment.
    return result


def main() -> int:
    incoming = json.load(sys.stdin)
    report = classify(incoming, Path("templates/moj-prop-v4"))
    print(json.dumps(report, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
