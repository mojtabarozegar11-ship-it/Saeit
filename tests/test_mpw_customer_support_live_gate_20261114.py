"""Offline tests for public-only MojPlayWin support acceptance gate."""
import pytest

from scripts.mpw_customer_support_live_gate_20261114 import (
    INBOX, LEGACY, ORIGIN, ROUTES, ROUTE_IDENTITY, _same_public_url, assess, fetch_public
)


def test_all_seven_routes_must_expose_new_mailto_without_legacy():
    pages = {ORIGIN + path: (
        '<html><body>' + ' '.join(ROUTE_IDENTITY[path]) +
        '<a href="mailto:' + INBOX + '">' + INBOX + '</a></body></html>'
    ) for path in ROUTES}
    report = assess(lambda url: pages[url])
    assert report["support_ready"] is True
    assert report["live_release_confirmed"] is True
    assert report["ready_routes"] == 7
    assert report["required_routes"] == 7
    assert all(x["status"] == "READY" for x in report["observations"])


def test_current_static_fallback_and_legacy_inbox_are_not_misreported_as_ready():
    pages = {ORIGIN + p: (
        '<html><body>' + ' '.join(ROUTE_IDENTITY[p]) +
        '<a href="mailto:' + INBOX + '">' + INBOX + '</a></body></html>'
    ) for p in ROUTES}
    pages[ORIGIN + "/store/"] = "MPW_STATIC_STORE_FALLBACK_V1"
    pages[ORIGIN + "/contact/"] = '<p>' + LEGACY + '</p>'
    pages[ORIGIN + "/support/"] = '<p>' + LEGACY + '</p>'
    pages[ORIGIN + "/mpw-editorial/revenue/inquiry.php?service=general"] = LEGACY
    result = assess(lambda url: pages[url])
    assert result["support_ready"] is False
    assert result["ready_routes"] == 3
    store = next(x for x in result["observations"] if x["route"] == "/store/")
    assert store["store_source_indicator"] == "STATIC_STORE_FALLBACK_VISIBLE"
    assert len([x for x in result["observations"] if x["legacy_visible"]]) == 3


def test_plain_address_or_http_error_do_not_count_as_verified_customer_link():
    def page(url):
        if url.endswith("/contact/"):
            raise TimeoutError("blocked")
        return INBOX
    result = assess(page)
    assert result["support_ready"] is False
    assert result["ready_routes"] == 0
    contact = next(x for x in result["observations"] if x["route"] == "/contact/")
    assert contact["status"] == "FETCH_FAILED"
    assert contact["error_class"] == "TimeoutError"
    assert all(not x["mailto_visible"] for x in result["observations"])


def test_get_only_allowlist_prevents_accidental_form_submission_or_remote_fetch():
    for bad in (ORIGIN + "/store/product/72/checkout/", ORIGIN + "/admin/",
                "https://example.com/contact/", ORIGIN + "/support/?submit=1"):
        with pytest.raises(ValueError, match="NON_ALLOWLISTED_URL"):
            fetch_public(bad)
    assert _same_public_url(ORIGIN + "/store/", ORIGIN + "/store/")
    assert not _same_public_url(ORIGIN + "/store/", "https://example.com/store/")
    assert not _same_public_url(ORIGIN + "/support/", ORIGIN + "/contact/")
    assert not _same_public_url(ORIGIN + "/support/", "http://mojplaywin.com/support/")


def test_report_is_non_sensitive_and_read_only():
    result = assess(lambda _: LEGACY)
    assert result["production_files_modified"] is False
    assert result["emails_sent"] is False
    assert result["payments_attempted"] is False
    assert not result["support_ready"]
    assert "mailto:" not in str(result)
    assert "customer_password" not in str(result)


def test_generic_support_placeholder_does_not_fake_functional_pages():
    html = '<html><body><a href="mailto:' + INBOX + '">' + INBOX + '</a></body></html>'
    result = assess(lambda _: html)
    assert result["ready_routes"] == 0
    assert result["support_ready"] is False
    assert all(not entry["page_identity_verified"] for entry in result["observations"])
    assert all(entry["status"] == "UNRECOGNIZED_PAGE" for entry in result["observations"])


def test_store_catalog_must_still_have_original_buyer_path_after_release():
    pages = {ORIGIN + path: (
        '<body>' + ' '.join(ROUTE_IDENTITY[path]) +
        '<a href="mailto:' + INBOX + '">' + INBOX + '</a></body>'
    ) for path in ROUTES}
    target = ORIGIN + "/store/"
    pages[target] = pages[target].replace("/store/product/72/", "/broken-product-route/")
    result = assess(lambda url: pages[url])
    assert result["ready_routes"] == 6
    assert result["support_ready"] is False
    store = next(x for x in result["observations"] if x["route"] == "/store/")
    assert store["status"] == "UNRECOGNIZED_PAGE"
    assert store["page_identity_verified"] is False
