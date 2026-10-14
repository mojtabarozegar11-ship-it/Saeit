"""Read-only, deterministic MojPlayWin storefront preflight.

Fixes the isolated Django template API used by the failed 2026-10-14
live-preflight runner: django.template.Engine templates need Context(...).
Never imports production settings, writes database records or deploys files.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from django.template import Context, Engine, TemplateSyntaxError
from scripts.mpw_branded_store_targeted_patch import prepare


def check_brand_release(source: Path, partial: Path) -> dict:
    if not source.is_file() or source.is_symlink():
        raise ValueError("ACTIVE_BRAND_SOURCE_MISSING_OR_LINK")
    if not partial.is_file() or partial.is_symlink():
        raise ValueError("FACTORY_RELEASE_PARTIAL_MISSING_OR_LINK")
    raw = source.read_bytes()
    if len(raw) > 500000 or len(raw) < 64:
        raise ValueError("ACTIVE_BRAND_SOURCE_UNEXPECTED_SIZE")
    text = raw.decode("utf-8")
    candidate, changed = prepare(text)
    if changed != 1 or candidate == text:
        raise RuntimeError("EXACT_ONE_FUNCTION_PATCH_REQUIRED")
    fragment = partial.read_text(encoding="utf-8")
    if len(fragment) > 30000 or "mpw-verified-factory" not in fragment:
        raise ValueError("FACTORY_RELEASE_PARTIAL_INVALID")

    # Engine is deliberately standalone. Its Template.render accepts a Django
    # Context, NOT a plain dict (that was the earlier failed audit's own bug).
    engine = Engine(autoescape=True, debug=False)
    template = engine.from_string(fragment)
    blank = template.render(Context({"factory_cards": []}))
    if blank.strip():
        raise RuntimeError("UNAUTHORIZED_FACTORY_SECTION_APPEARED")
    safe = template.render(Context({"factory_cards": [{
        "name": "Verified Farm Toolkit",
        "price": "Free",
        "kind": "free",
        "discount_claim": None,
        "url": "/factory-releases/farm-enterprise-economics-v1/",
        "button": "Free download",
    }]}))
    if not all(v in safe for v in (
        "Verified Farm Toolkit",
        "Free download",
        "/factory-releases/farm-enterprise-economics-v1/",
    )):
        raise RuntimeError("VERIFIED_FREE_SECTION_DID_NOT_RENDER")
    if "Proceed to secure checkout" in safe:
        raise RuntimeError("UNVERIFIED_PAYMENT_BUTTON_APPEARED")
    xss = template.render(Context({"factory_cards": [{
        "name": "<script>bad()</script>",
        "price": "Free",
        "kind": "free",
        "discount_claim": None,
        "url": "/factory-releases/farm-enterprise-economics-v1/",
        "button": "Free download",
    }]}))
    if "<script>bad()</script>" in xss:
        raise RuntimeError("USER_CONTENT_NOT_ESCAPED")
    return {
        "active_brand_view_sha256": hashlib.sha256(raw).hexdigest(),
        "candidate_brand_view_sha256": hashlib.sha256(candidate.encode("utf-8")).hexdigest(),
        "partial_sha256": hashlib.sha256(partial.read_bytes()).hexdigest(),
        "exactly_one_branded_store_function_modified": True,
        "empty_release_renders_no_extra_section": True,
        "verified_free_template_renders": True,
        "unverified_paid_checkout_hidden": True,
        "html_autoescape_checked": True,
        "writes_performed": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand-source", type=Path, required=True)
    parser.add_argument("--factory-partial", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(check_brand_release(args.brand_source,args.factory_partial), sort_keys=True))


if __name__ == "__main__":
    main()
