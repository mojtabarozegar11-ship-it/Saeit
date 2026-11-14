"""Owner-only service economics calculator; no real quote or collection."""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from core.company_inquiry_models import CompanyInquiry
from core.models import Order
from command_center.models import WorkItem


def scenario(**kwargs):
    params = {
        "currency": "IRT",
        "base_unit_price": "450000",
        "discount_percent": "10",
        "direct_unit_cost": "110000",
        "delivery_unit_cost": "20000",
        "payment_unit_fee": "1000",
        "refund_unit_reserve": "5000",
        "tax_unit_reserve": "10000",
        "period_fixed_cost": "125000",
        "expected_units": "5",
    }
    params.update(kwargs)
    return params


@pytest.fixture
def owner(db):
    user = get_user_model()
    return user.objects.create_superuser(
        username="pricing-owner-c07", email="owner-pricing@example.invalid",
        password="test-only-local",
    )


@pytest.mark.django_db
def test_anonymous_pricing_is_private_and_not_a_public_sales_form():
    r = Client().get(reverse("command_center_service_pricing_workbench"))
    assert r.status_code == 302
    assert "/admin/login/" in r["Location"]


@pytest.mark.django_db
def test_non_owner_staff_is_denied_even_if_logged_in():
    staff = get_user_model().objects.create_user(
        username="pricing-staff", password="test-only-local", is_staff=True
    )
    client = Client()
    client.force_login(staff)
    assert client.get(reverse("command_center_service_pricing_workbench")).status_code == 302


@pytest.mark.django_db
def test_get_has_no_speculative_default_costs_and_no_write(owner):
    client = Client()
    client.force_login(owner)
    r = client.get(reverse("command_center_service_pricing_workbench"))
    html = r.content.decode()
    assert r.status_code == 200
    assert "کارگاه محاسبه قیمت و سودآوری خدمات" in html
    assert "هیچ هزینه‌ای پیش‌فرض صفر" in html
    assert 'name="direct_unit_cost"' in html
    assert "450000" not in html
    assert "نامعلوم" in html
    assert CompanyInquiry.objects.count() == 0
    assert WorkItem.objects.count() == 0


@pytest.mark.django_db
def test_realistic_hypothetical_costs_produce_bounded_result_no_sale(owner):
    client = Client()
    client.force_login(owner)
    r = client.post(reverse("command_center_service_pricing_workbench"), scenario())
    assert r.status_code == 200
    html = r.content.decode()
    assert "نتیجه محاسبه" in html
    assert "405000" in html
    assert "وصول وجه واقعی: نامعلوم" in html
    assert "قیمت دارای تأیید مالک: خیر" in html
    assert r["Cache-Control"].startswith("no-store")
    assert r["X-Robots-Tag"] == "noindex, nofollow, noarchive"
    assert CompanyInquiry.objects.count() == 0
    assert WorkItem.objects.count() == 0
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_missing_costs_are_validation_errors_not_zero_profit_assumptions(owner):
    client = Client()
    client.force_login(owner)
    incomplete = scenario()
    del incomplete["direct_unit_cost"]
    r = client.post(reverse("command_center_service_pricing_workbench"), incomplete)
    assert r.status_code == 200
    assert "نتیجه محاسبه" not in r.content.decode()
    assert "direct_unit_cost" in r.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("override", [
    {"currency": "EUR"},
    {"expected_units": "-1"},
    {"expected_units": "4.2"},
    {"discount_percent": "150"},
    {"direct_unit_cost": "-1"},
    {"base_unit_price": "0"},
    {"base_unit_price": "NaN"},
    {"direct_unit_cost": "inf"},
])
def test_bad_quote_inputs_fail_without_settlement(owner, override):
    client = Client()
    client.force_login(owner)
    r = client.post(reverse("command_center_service_pricing_workbench"), scenario(**override))
    html = r.content.decode()
    assert r.status_code == 200
    assert "نتیجه محاسبه" not in html
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_price_requires_no_customer_pii_and_never_creates_receipt(owner):
    client = Client()
    client.force_login(owner)
    p = scenario()
    p.update({
        "customer_email": "PRIVATE_BUYER_EMAIL_NEVER_LOG",
        "account_number": "PRIVATE_BANK_NUMBER",
    })
    r = client.post(reverse("command_center_service_pricing_workbench"), p)
    html = r.content.decode()
    assert r.status_code == 200
    assert "PRIVATE_BUYER_EMAIL_NEVER_LOG" not in html
    assert "PRIVATE_BANK_NUMBER" not in html
    assert WorkItem.objects.count() == 0
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_post_without_csrf_is_rejected(owner):
    client = Client(enforce_csrf_checks=True)
    client.force_login(owner)
    r = client.post(reverse("command_center_service_pricing_workbench"), scenario())
    assert r.status_code == 403


@pytest.mark.django_db
def test_oversized_post_is_rejected_and_does_not_persist(owner):
    client = Client()
    client.force_login(owner)
    r = client.post(reverse("command_center_service_pricing_workbench"),
                    scenario(currency="IRT" + " " * 15000))
    assert r.status_code == 413
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_currency_never_auto_converts_irt_to_irr(owner):
    client = Client()
    client.force_login(owner)
    r = client.post(reverse("command_center_service_pricing_workbench"), scenario(currency="IRR"))
    assert r.status_code == 200
    assert "IRR" in r.content.decode()
    assert "تبدیل نمی‌شوند" in r.content.decode()


@pytest.mark.django_db
def test_funnel_navigation_has_costing_link(owner):
    client = Client()
    client.force_login(owner)
    html = client.get(reverse("command_center_service_proposal_funnel_dashboard")).content.decode()
    assert reverse("command_center_service_pricing_workbench") in html
