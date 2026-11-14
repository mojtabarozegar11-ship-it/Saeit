"""Offline tests for public-only MojPlayWin support acceptance gate."""
import pytest

from scripts.mpw_customer_support_live_gate_20261114 import (
    CHECKOUT_GET_ROUTES, INBOX, LEGACY, ORIGIN, ROUTES, ROUTE_IDENTITY,
    _RejectRedirects, _same_public_url, assess, assess_checkout_get, fetch_public
)


def _valid_page(path):
    catalog = ""
    if path == "/store/":
        catalog = "".join(
            '<a href="/store/product/' + str(sku) + '/">View product</a>'
            for sku in (72, 225, 879)
        )
    return ('<html><body>' + ' '.join(ROUTE_IDENTITY[path]) +
            catalog + '<a href="mailto:' + INBOX + '">' + INBOX + '</a></body></html>')


def test_all_seven_routes_must_expose_new_mailto_without_legacy():
    pages = {ORIGIN + path: _valid_page(path) for path in ROUTES}
    report = assess(lambda url: pages[url])
    assert report["support_ready"] is True
    assert report["live_release_confirmed"] is True
    assert report["ready_routes"] == 7
    assert report["required_routes"] == 7
    assert all(x["status"] == "READY" for x in report["observations"])


def test_current_static_fallback_and_legacy_inbox_are_not_misreported_as_ready():
    pages = {ORIGIN + p: _valid_page(p) for p in ROUTES}
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
    for bad in (ORIGIN + "/store/product/879/checkout/", ORIGIN + "/admin/",
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
    pages = {ORIGIN + path: _valid_page(path) for path in ROUTES}
    target = ORIGIN + "/store/"
    pages[target] = pages[target].replace("/store/product/72/", "/broken-product-route/")
    result = assess(lambda url: pages[url])
    assert result["ready_routes"] == 6
    assert result["support_ready"] is False
    store = next(x for x in result["observations"] if x["route"] == "/store/")
    assert store["status"] == "UNRECOGNIZED_PAGE"
    assert store["page_identity_verified"] is False


def test_text_or_comment_mailto_does_not_pass_live_acceptance():
    base = {ORIGIN + path: _valid_page(path) for path in ROUTES}
    route = ORIGIN + "/support/"
    for spoof in (
        '<p>mailto:' + INBOX + '</p>',
        '<!-- <a href="mailto:' + INBOX + '">' + INBOX + '</a> -->',
        '<script>const x = "mailto:' + INBOX + '";</script>',
        '<template><a href="mailto:' + INBOX + '">hidden</a></template>',
    ):
        pages = dict(base)
        pages[route] = ' '.join(ROUTE_IDENTITY["/support/"]) + spoof
        report = assess(lambda url: pages[url])
        assert report["ready_routes"] == 6
        assert report["support_ready"] is False
        support = next(item for item in report["observations"] if item["route"] == "/support/")
        assert support["mailto_visible"] is False


def test_mailto_requires_exact_address_and_single_href_attribute():
    base = {ORIGIN + path: _valid_page(path) for path in ROUTES}
    route = ORIGIN + "/contact/"
    for bad in (
        '<a href="mailto:' + INBOX + '.attacker.example">' + INBOX + '</a>',
        '<a href="mailto:' + INBOX + '" href="https://example.com">' + INBOX + '</a>',
    ):
        pages = dict(base)
        pages[route] = ' '.join(ROUTE_IDENTITY["/contact/"]) + bad
        report = assess(lambda url: pages[url])
        assert report["ready_routes"] == 6
        assert report["support_ready"] is False
    pages = dict(base)
    pages[route] = ' '.join(ROUTE_IDENTITY["/contact/"]) + (
        '<a href="mailto:' + INBOX + '?subject=Support">' + INBOX + '</a>')
    assert assess(lambda url: pages[url])["ready_routes"] == 7


def test_redirect_handler_rejects_external_redirect_before_following():
    with pytest.raises(RuntimeError, match="UNEXPECTED_REDIRECT"):
        _RejectRedirects().redirect_request(
            None, None, 302, "Found", {}, "https://example.com/redirected")


def test_all_three_store_products_require_real_same_origin_anchors():
    pages = {ORIGIN + path: _valid_page(path) for path in ROUTES}
    store = ORIGIN + "/store/"
    assert assess(lambda url: pages[url])["support_ready"] is True
    for sku in (72, 225, 879):
        anchor = '<a href="/store/product/' + str(sku) + '/">View product</a>'
        pages[store] = _valid_page("/store/").replace(anchor, "")
        # Remaining source copy can still mention the product ID.
        pages[store] += "/store/product/" + str(sku) + "/"
        report = assess(lambda url: pages[url])
        entry = next(item for item in report["observations"] if item["route"] == "/store/")
        assert not entry["store_product_links_verified"]
        assert entry["status"] == "UNRECOGNIZED_PAGE"
        assert report["ready_routes"] == 6


def test_external_insecure_and_javascript_store_links_never_count():
    pages = {ORIGIN + path: _valid_page(path) for path in ROUTES}
    store = ORIGIN + "/store/"
    original = '<a href="/store/product/225/">View product</a>'
    for spoof in (
        '<a href="https://example.org/store/product/225/">View product</a>',
        '<a href="http://mojplaywin.com/store/product/225/">View product</a>',
        '<a href="javascript:location.href=\'/store/product/225/\'">View product</a>',
        '<a href="/store/product/225/" href="https://example.org/">View product</a>',
        '<!-- ' + original + ' -->',
    ):
        pages[store] = _valid_page("/store/").replace(original, spoof)
        result = assess(lambda url: pages[url])
        entry = next(item for item in result["observations"] if item["route"] == "/store/")
        assert entry["store_product_links_verified"] is False
        assert result["support_ready"] is False


def test_html_base_tag_cannot_redirect_local_product_links():
    pages = {ORIGIN + path: _valid_page(path) for path in ROUTES}
    pages[ORIGIN + "/store/"] = pages[ORIGIN + "/store/"].replace(
        "<html>", '<html><head><base href="https://example.org/"></head>', 1)
    result = assess(lambda url: pages[url])
    entry = next(item for item in result["observations"] if item["route"] == "/store/")
    assert entry["store_product_links_verified"] is False
    assert result["support_ready"] is False


def test_product_links_can_use_https_absolute_same_origin_urls():
    pages = {ORIGIN + path: _valid_page(path) for path in ROUTES}
    pages[ORIGIN + "/store/"] = pages[ORIGIN + "/store/"].replace(
        'href="/store/product/879/"', 'href="' + ORIGIN + '/store/product/879/"')
    result = assess(lambda url: pages[url])
    store = next(item for item in result["observations"] if item["route"] == "/store/")
    assert store["store_product_links_verified"] is True
    assert result["support_ready"] is True


def _checkout_html(product_id: int) -> str:
    path = "/store/product/" + str(product_id) + "/checkout/"
    return (
        '<html><body><h1>' + CHECKOUT_GET_ROUTES[path] +
        '</h1><p>Pay with TRX</p><form method="post" action="/commerce/trx-easy/start/' +
        str(product_id) + '/"><input name="csrfmiddlewaretoken" type="hidden" value="example">'
        '<input name="email" type="email" required><button>Continue</button>'
        '</form></body></html>'
    )


def test_two_checkout_gets_expose_visible_email_post_forms_without_payment():
    pages = {ORIGIN + route: _checkout_html(int(route.split("/")[3]))
             for route in CHECKOUT_GET_ROUTES}
    report = assess_checkout_get(lambda url: pages[url])
    assert report["observed_checkout_forms"] == 2
    assert report["required_products"] == 2
    assert all(row["status"] == "GET_FORM_PRESENT" for row in report["observations"])
    assert report["network_methods"] == ["GET"]
    assert report["orders_created"] == 0
    assert report["payments_attempted"] == 0
    assert report["emails_sent"] == 0
    assert report["delivery_verified"] is False
    assert report["on_chain_payment_verified"] is False
    assert report["live_purchase_ready"] is False


def test_checkout_get_cannot_accept_hidden_or_missing_email_inputs():
    pages = {ORIGIN + route: _checkout_html(int(route.split("/")[3]))
             for route in CHECKOUT_GET_ROUTES}
    route = ORIGIN + "/store/product/72/checkout/"
    for spoof in ('<input type="hidden" name="email" required>',
                  '<p>Type your email to continue</p>'):
        pages[route] = _checkout_html(72).replace(
            '<input name="email" type="email" required>', spoof)
        result = assess_checkout_get(lambda url: pages[url])
        assert result["observed_checkout_forms"] == 1
        assert result["observations"][0]["status"] == "GET_FORM_INCOMPLETE"


def test_checkout_get_requires_csrf_and_post_method():
    pages = {ORIGIN + route: _checkout_html(int(route.split("/")[3]))
             for route in CHECKOUT_GET_ROUTES}
    route = ORIGIN + "/store/product/72/checkout/"
    for changed in (
        _checkout_html(72).replace('method="post"', 'method="get"'),
        _checkout_html(72).replace('name="csrfmiddlewaretoken"', 'name="not_csrf"'),
    ):
        pages[route] = changed
        result = assess_checkout_get(lambda url: pages[url])
        assert result["observed_checkout_forms"] == 1


def test_external_insecure_and_duplicate_form_actions_fail_closed():
    pages = {ORIGIN + route: _checkout_html(int(route.split("/")[3]))
             for route in CHECKOUT_GET_ROUTES}
    route = ORIGIN + "/store/product/225/checkout/"
    for action in (
        'https://evil.example/start', 'http://mojplaywin.com/start',
        '//evil.example/start', 'javascript:alert(1)',
    ):
        pages[route] = _checkout_html(225).replace(
            '/commerce/trx-easy/start/225/', action)
        result = assess_checkout_get(lambda url: pages[url])
        assert result["observed_checkout_forms"] == 1
    pages[route] = _checkout_html(225).replace(
        'method="post" action=', 'method="post" action="/wrong/" action=')
    assert assess_checkout_get(lambda url: pages[url])["observed_checkout_forms"] == 1


def test_checkout_get_requires_correct_product_identity():
    pages = {ORIGIN + route: _checkout_html(int(route.split("/")[3]))
             for route in CHECKOUT_GET_ROUTES}
    route = ORIGIN + "/store/product/72/checkout/"
    pages[route] = _checkout_html(72).replace(
        CHECKOUT_GET_ROUTES["/store/product/72/checkout/"], "Unrelated item")
    assert assess_checkout_get(lambda url: pages[url])["observed_checkout_forms"] == 1


def test_checkout_get_does_not_include_sku879_or_mutating_endpoints():
    assert len(CHECKOUT_GET_ROUTES) == 2
    assert "/store/product/879/checkout/" not in CHECKOUT_GET_ROUTES
    for url in (
        ORIGIN + "/commerce/trx-easy/start/72/",
        ORIGIN + "/commerce/trx-easy/invoice/1/",
        ORIGIN + "/store/product/879/checkout/",
    ):
        with pytest.raises(ValueError, match="NON_ALLOWLISTED_URL"):
            fetch_public(url)


def test_checkout_get_fetch_failure_is_unknown_not_verified_sale():
    def blocked(_):
        raise TimeoutError("connection unavailable")
    result = assess_checkout_get(blocked)
    assert result["observed_checkout_forms"] == 0
    assert all(row["status"] == "FETCH_FAILED" for row in result["observations"])
    assert all(row["error_class"] == "TimeoutError" for row in result["observations"])
    assert result["live_purchase_ready"] is False


def test_checkout_form_rejects_foreign_base_tag_and_same_origin_login_action():
    pages = {ORIGIN + route: _checkout_html(int(route.split("/")[3]))
             for route in CHECKOUT_GET_ROUTES}
    route = ORIGIN + "/store/product/72/checkout/"
    pages[route] = _checkout_html(72).replace(
        "<html>", '<html><head><base href="https://evil.example/"></head>', 1)
    assert assess_checkout_get(lambda url: pages[url])["observed_checkout_forms"] == 1
    pages[route] = _checkout_html(72).replace(
        "/commerce/trx-easy/start/72/", "/accounts/login/")
    assert assess_checkout_get(lambda url: pages[url])["observed_checkout_forms"] == 1


def test_checkout_form_cannot_post_to_other_product_or_create_invoice_url():
    pages = {ORIGIN + route: _checkout_html(int(route.split("/")[3]))
             for route in CHECKOUT_GET_ROUTES}
    route = ORIGIN + "/store/product/72/checkout/"
    for action in ("/commerce/trx-easy/start/225/",
                   "/commerce/trx-easy/invoice/1/",
                   "/store/product/879/checkout/"):
        pages[route] = _checkout_html(72).replace(
            "/commerce/trx-easy/start/72/", action)
        assert assess_checkout_get(lambda url: pages[url])["observed_checkout_forms"] == 1


def test_checkout_requires_mandatory_editable_email_in_post_form():
    pages = {ORIGIN + route: _checkout_html(int(route.split("/")[3]))
             for route in CHECKOUT_GET_ROUTES}
    route = ORIGIN + "/store/product/72/checkout/"
    for replacement in (
        '<input name="email" type="email">',
        '<input name="email" type="email" disabled required>',
        '<input name="email" type="email" readonly required>',
    ):
        pages[route] = _checkout_html(72).replace(
            '<input name="email" type="email" required>', replacement)
        assert assess_checkout_get(lambda url: pages[url])["observed_checkout_forms"] == 1


def test_optional_non_email_input_cannot_stand_in_for_buyer_email():
    pages = {ORIGIN + route: _checkout_html(int(route.split("/")[3]))
             for route in CHECKOUT_GET_ROUTES}
    route = ORIGIN + "/store/product/225/checkout/"
    pages[route] = _checkout_html(225).replace(
        '<input name="email" type="email" required>',
        '<input name="delivery_note" type="text" required>')
    assert assess_checkout_get(lambda url: pages[url])["observed_checkout_forms"] == 1
