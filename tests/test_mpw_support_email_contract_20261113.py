"""Read-only regression contracts for MojPlayWin's official customer-support email.

These tests never send mail, access the network, edit orders, or alter production.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIL = "mojplaywin@gmail.com"
OLD_MAIL = "support@mojplaywin.com"


def source(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_shared_footer_shows_verified_contact_and_clickable_address():
    footer = source("core/templates/mojplaywin/footer.html")
    site_base = source("core/templates/mojplaywin/site_base.html")
    assert f'href="mailto:{MAIL}"' in footer
    assert "Questions about a purchase or any issue?" in footer
    assert '{% include "mojplaywin/footer.html" %}' in site_base
    assert OLD_MAIL not in footer


def test_store_help_precedes_catalog_and_remains_mobile_accessible():
    store = source("core/templates/mojplaywin/store.html")
    assert 'aria-labelledby="mpw-shop-help-title"' in store
    assert store.index('class="mpw-shop-help"') < store.index('class="mpw-shop-catalog"')
    assert f"mailto:{MAIL}?subject=MojPlayWin%20Store%20Support" in store
    assert "Email customer support" in store
    assert "@media(max-width:650px){.mpw-shop-help{" in store
    assert "Never email passwords, verification codes or wallet recovery phrases." in store


def test_contact_and_support_navigation_open_same_inbox_directly():
    for path in ("core/templates/mojplaywin/footer.html", "core/templates/mojplaywin/theme.html"):
        html = source(path)
        assert f'href="mailto:{MAIL}?subject=MojPlayWin%20Contact">Contact</a>' in html
        assert f'href="mailto:{MAIL}?subject=MojPlayWin%20Support">Support</a>' in html
        assert OLD_MAIL not in html


def test_legacy_support_cta_and_purchase_recovery_use_verified_inbox():
    html = source("core/templates/brands/mojplaywin/page.html")
    recovery = source("services/mpw_trx_guest_commerce.py")
    assert f"mailto:{MAIL}?subject=MojPlayWin%20Support" in html
    assert f"mailto:{MAIL}?subject=MojPlayWin%20Purchase%20Support" in recovery
    assert OLD_MAIL not in html
    assert OLD_MAIL not in recovery
    assert "with your invoice reference and transaction hash." in recovery
    assert "Never share a wallet recovery phrase or private key." in recovery
