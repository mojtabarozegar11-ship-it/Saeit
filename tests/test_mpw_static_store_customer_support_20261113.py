"""Regression gates for an *existing* MojPlayWin static store; no host writes."""
from pathlib import Path
import re

import pytest
from scripts.mpw_static_store_customer_support_20261113 import (
    BANNER, CSS, CATALOG_ANCHOR, EMAIL, HEAD_ANCHOR,
    SUPPORT_ID, SKU879_OLD_CHECKOUT_CTA, SKU879_INQUIRY_CTA,
    digest, patched_html, install, rollback
)

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / ".github/workflows/vps-store-identity-audit.yml"


def original_static_fallback() -> bytes:
    workflow = GENERATOR.read_text("utf-8")
    match = re.search(
        r'cat > "\$STORE/index.html" <<\x27HTML\x27\n(.*?)\n          HTML',
        workflow, flags=re.DOTALL
    )
    assert match, "Existing main store fallback source not found"
    return (match.group(1) + "\n").encode("utf-8")


def test_in_place_support_notice_preserves_existing_store_products_and_design():
    old = original_static_fallback()
    new = patched_html(old)
    assert new != old
    html = new.decode("utf-8")
    assert html.count(SUPPORT_ID) == 1
    assert html.count("mailto:" + EMAIL) == 2
    assert SKU879_OLD_CHECKOUT_CTA not in html
    assert html.count(SKU879_INQUIRY_CTA) == 1
    assert html.index(SUPPORT_ID) < html.index(CATALOG_ANCHOR)
    assert (html.replace(CSS, "", 1).replace(BANNER, "", 1)
            .replace(SKU879_INQUIRY_CTA, SKU879_OLD_CHECKOUT_CTA, 1)
            .encode("utf-8") == old)
    for preserved in ("US $7.50", "US $4.00", "US $6.80",
                      "/store/product/72/checkout/", "/store/product/225/checkout/",
                      "/store/product/879/", "MPW_STATIC_STORE_FALLBACK_V1"):
        assert preserved.encode() in new
    assert digest(new) != digest(old)


def test_idempotent_and_fail_closed_against_unrecognized_versions():
    original = original_static_fallback()
    updated = patched_html(original)
    assert patched_html(updated) == updated
    for old in (
        original.replace(b"MPW_STATIC_STORE_FALLBACK_V1", b"UNOWNED_STORE", 1),
        original.replace(CATALOG_ANCHOR.encode(), b'<section class="new-catalog">', 1),
        original.replace(b"/store/product/72/checkout/", b"/external-purchase/", 1),
        original + original,
    ):
        with pytest.raises(RuntimeError):
            patched_html(old)


def test_owner_approval_mandatory_even_if_called_as_a_library():
    with pytest.raises(RuntimeError, match="EXPLICIT_OWNER_APPROVAL_REQUIRED"):
        install("123456789", "0" * 64, owner_approved=False)
    with pytest.raises(RuntimeError, match="EXPLICIT_OWNER_APPROVAL_REQUIRED"):
        rollback("123456789", owner_approved=False)


def test_no_automatic_production_publish_trigger_added():
    source=(ROOT / "scripts/mpw_static_store_customer_support_20261113.py").read_text("utf-8")
    assert "if __name__ == \"__main__\":" in source
    assert "MPW_STATIC_STORE_FALLBACK_V1" in source
    assert "mpw-static-shop-support-20261113" in source
    assert ".htaccess" in source  # explicit do-not-edit declaration only
    assert "requests.post" not in source and "urlopen(" not in source
    assert ".github/workflows" not in source


def test_sku879_inquiry_prevents_premature_direct_checkout_but_keeps_other_two():
    updated = patched_html(original_static_fallback()).decode("utf-8")
    assert 'href="/store/product/72/checkout/"' in updated
    assert 'href="/store/product/225/checkout/"' in updated
    assert 'href="/store/product/879/"' in updated
    assert 'href="/store/product/879/checkout/"' not in updated
    assert "SKU%20879%20Availability" in updated
    assert 'Ask about availability before buying' in updated


def test_sku879_modified_direct_checkout_baseline_fails_closed():
    original = original_static_fallback()
    for tampered in (
        original.replace(SKU879_OLD_CHECKOUT_CTA.encode(), b'<a href="/external-pay/">Pay</a>', 1),
        original.replace(SKU879_OLD_CHECKOUT_CTA.encode(), b'', 1),
        original + SKU879_INQUIRY_CTA.encode(),
    ):
        with pytest.raises(RuntimeError, match="STORE_PRODUCT_OR_PAYMENT_GUARD_MISMATCH"):
            patched_html(tampered)


def test_sku879_prepared_notice_cannot_reintroduce_checkout_cta():
    updated = patched_html(original_static_fallback())
    html = updated.decode("utf-8").replace(
        SKU879_INQUIRY_CTA, SKU879_OLD_CHECKOUT_CTA, 1)
    with pytest.raises(RuntimeError, match="PARTIAL_SUPPORT_EDIT"):
        patched_html(html.encode("utf-8"))
