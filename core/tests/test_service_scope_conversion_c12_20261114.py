"""C12: six buyer-ready service scope pages without extra CRM or fake checkout."""
import json
import re

import pytest
from django.test import Client, override_settings
from django.urls import reverse

from core.company_inquiry_models import CompanyInquiry
from core.service_intake_routing import LEGACY_INQUIRY_PATH
from core.service_sales_controls import SERVICE_CARDS
from core.service_scope_pages import SCOPE_GUIDES
from core.models import Order

OFF = {
    "DEBUG": True,
    "SERVICE_INTAKE_DJANGO_ENABLED": False,
    "SERVICE_INTAKE_SINGLE_SOURCE_APPROVED": False,
    "SERVICE_INTAKE_ROLLBACK_VERIFIED": False,
    "SERVICE_INTAKE_PRIVACY_REVIEWED": False,
    "SERVICE_INTAKE_SOURCE_OF_TRUTH": "legacy_ask_master_unverified",
}
ON = {
    "DEBUG": True,
    "SERVICE_INTAKE_DJANGO_ENABLED": True,
    "SERVICE_INTAKE_SINGLE_SOURCE_APPROVED": True,
    "SERVICE_INTAKE_ROLLBACK_VERIFIED": True,
    "SERVICE_INTAKE_PRIVACY_REVIEWED": True,
    "SERVICE_INTAKE_SOURCE_OF_TRUTH": "django_company_inquiry_v1",
}


def url(code):
    return reverse("service_scope_page", args=[code])


@pytest.mark.django_db
@override_settings(**OFF)
@pytest.mark.parametrize("code", SERVICE_CARDS)
def test_six_scoped_offers_show_provable_service_details_and_real_php_cta(code):
    response = Client().get(url(code))
    html = response.content.decode()
    assert response.status_code == 200
    assert SERVICE_CARDS[code]["title_fa"] in html
    assert code in html
    assert LEGACY_INQUIRY_PATH in html
    assert SERVICE_CARDS[code]["limitation"] in html
    assert SERVICE_CARDS[code]["customer"] in html
    assert "کد" in html
    assert "فرم رسمی شرکت" in html
    for deliverable in SERVICE_CARDS[code]["deliverables"]:
        assert deliverable in html
    assert CompanyInquiry.objects.count() == 0
    assert Order.objects.count() == 0


@pytest.mark.django_db
@override_settings(**OFF)
@pytest.mark.parametrize("code", SERVICE_CARDS)
def test_each_service_has_three_decision_questions_three_inputs_and_acceptance(code):
    html = Client().get(url(code)).content.decode()
    assert len(SCOPE_GUIDES[code]["questions"]) == 3
    assert len(SCOPE_GUIDES[code]["intake"]) == 3
    for item in SCOPE_GUIDES[code]["questions"] + SCOPE_GUIDES[code]["intake"]:
        assert item in html
    assert SCOPE_GUIDES[code]["acceptance"] in html


@pytest.mark.django_db
@override_settings(**OFF)
def test_services_index_exposes_six_detail_pages_and_unbroken_legacy_cta():
    html = Client().get(reverse("services")).content.decode()
    for code in SERVICE_CARDS:
        assert url(code) in html
    assert html.count(LEGACY_INQUIRY_PATH) >= 6
    assert "ثبت استعلام" in html


@pytest.mark.django_db
@override_settings(**ON)
@pytest.mark.parametrize("code", SERVICE_CARDS)
def test_enabled_single_django_source_resolves_only_official_scoped_intake(code):
    html = Client().get(url(code)).content.decode()
    assert reverse("service_inquiry", args=[code]) in html
    assert LEGACY_INQUIRY_PATH not in html
    assert "فرم اصلی فعال شرکت روی مسیر موجود PHP" not in html
    assert CompanyInquiry.objects.count() == 0


@pytest.mark.django_db
@override_settings(**OFF)
@pytest.mark.parametrize("code", SERVICE_CARDS)
def test_disabled_source_does_not_accidentally_reenable_django_form(code):
    html = Client().get(url(code)).content.decode()
    assert "فرم اصلی فعال شرکت روی مسیر موجود PHP" in html
    assert 'name="consent"' not in html
    assert '<form method="post"' not in html.lower()
    assert "قیمت قطعی هنوز تعیین نشده" in html


@pytest.mark.django_db
@override_settings(**OFF)
def test_bad_service_identifier_is_404_not_indirect_open_redirect():
    for value in ("BAD-99", "AGR-99", "AGR", "web-01", "AGR-01extra"):
        response = Client().get(url(value))
        assert response.status_code == 404
    assert CompanyInquiry.objects.count() == 0


@pytest.mark.django_db
@override_settings(**OFF)
def test_post_cannot_create_parallel_lead_or_sales_record():
    response = Client().post(url("AGR-01"), {
        "email": "private@example.invalid", "message": "Private source",
    })
    assert response.status_code == 405
    assert CompanyInquiry.objects.count() == 0
    assert Order.objects.count() == 0


@pytest.mark.django_db
@override_settings(**OFF)
def test_source_scope_does_not_force_login_before_reading_real_offer():
    response = Client().get(url("AGR-01"))
    assert response.status_code == 200
    assert "/admin/login" not in response["Location"] if "Location" in response else True


@pytest.mark.django_db
@override_settings(DEBUG=True, ALLOWED_HOSTS=["testserver", "mojplaywin.com", "www.mojplaywin.com"])
def test_company_offer_not_published_on_mojplaywin_domain():
    for host in ("mojplaywin.com", "www.mojplaywin.com"):
        response = Client().get(url("AGR-01"), HTTP_HOST=host)
        assert response.status_code == 404


@pytest.mark.django_db
@override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
def test_noncompany_test_domain_is_denied_in_production_mode():
    response = Client().get(url("AGR-01"))
    assert response.status_code == 404


@pytest.mark.django_db
@override_settings(**OFF)
@pytest.mark.parametrize("code", SERVICE_CARDS)
def test_canonical_is_exact_company_url_and_valid_service_json_ld(code):
    html = Client().get(url(code)).content.decode()
    canonical = "https://zomorodmelal.ir" + url(code)
    assert '<link rel="canonical" href="' + canonical + '">' in html
    matches = re.findall(
        r'<script type="application/ld\+json">(.*?)</script>',
        html, flags=re.DOTALL,
    )
    schemas = [json.loads(text) for text in matches]
    service = next(schema for schema in schemas if schema.get("@type") == "Service")
    assert service["@id"] if "@id" in service else True
    assert service["url"] == canonical
    assert service["name"] == SERVICE_CARDS[code]["title_fa"]
    assert service["provider"]["url"] == "https://zomorodmelal.ir/"
    assert "offers" not in service
    assert "price" not in service
    assert "merchantReturnPolicy" not in service


@pytest.mark.django_db
@override_settings(**OFF)
def test_service_landing_contains_accessible_headings_and_two_genuine_ctas():
    html = Client().get(url("WEB-01")).content.decode()
    for token in (
        "این بررسی به چه تصمیم‌هایی پاسخ می‌دهد؟",
        "برای تعیین دامنه، چه داده‌هایی لازم است؟",
        "مراحل همکاری، بدون تعهد زودهنگام",
        "پرسش‌های رایج",
        "زمان تحویل",
        "ورود به فرم رسمی درخواست بررسی",
    ):
        assert token in html
    assert html.count(LEGACY_INQUIRY_PATH) >= 2


@pytest.mark.django_db
@override_settings(**OFF)
def test_price_scarcity_claims_and_unearned_revenue_never_appear():
    html = Client().get(url("AGR-01")).content.decode()
    for unsupported in (
        "سود تضمینی", "درآمد تضمینی", "قیمت ثابت", "پرداخت شد",
        "تسویه انجام شد", "خرید با موفقیت انجام شد",
    ):
        assert unsupported not in html
    assert "قیمت قطعی هنوز تعیین نشده" in html


@pytest.mark.django_db
@override_settings(**OFF)
def test_service_scope_has_no_forms_no_hidden_customer_capture():
    html = Client().get(url("SEO-01")).content.decode()
    assert "<form" not in html.lower()
    assert 'name="email"' not in html
    assert 'name="phone"' not in html
    assert "از ارسال رمز" in html


@pytest.mark.django_db
@override_settings(**OFF)
def test_all_scope_guids_have_exact_catalogue_parity():
    assert set(SCOPE_GUIDES) == set(SERVICE_CARDS)
    assert all(len(guide["pain"]) > 65 for guide in SCOPE_GUIDES.values())
    assert all(len(guide["acceptance"]) > 25 for guide in SCOPE_GUIDES.values())


@pytest.mark.django_db
@override_settings(**OFF)
def test_json_schema_stays_in_script_context_not_customer_supplied_html():
    r = Client().get(url("AGR-01"))
    html = r.content.decode()
    assert '<script type="application/ld+json">' in html
    assert "text/html" in r["Content-Type"]
    assert r["X-Content-Type-Options"] == "nosniff"
    assert CompanyInquiry.objects.count() == 0


@pytest.mark.django_db
@override_settings(**OFF)
def test_legacy_php_service_code_is_explicitly_displayed_without_claiming_prefill():
    html = Client().get(url("RS-02")).content.decode()
    assert "کد" in html
    assert "RS-02" in html
    assert "در توضیحات فرم" in html
    assert "داده‌های" in html


@pytest.mark.django_db
@override_settings(**OFF)
def test_no_external_merchant_gateway_integrated_into_service_page():
    html = Client().get(url("WEB-01")).content.decode()
    assert "stripe.com/checkout" not in html
    assert "پرداخت در این مرحله" in html
    assert "پیش‌فاکتور" in html


@pytest.mark.django_db
@override_settings(**OFF)
def test_seo_meta_description_uses_actual_problem_not_fake_marketing_metric():
    html = Client().get(url("SEO-01")).content.decode()
    assert SCOPE_GUIDES["SEO-01"]["pain"] in html
    assert SERVICE_CARDS["SEO-01"]["title_fa"] in html
    assert "<meta" in html


@pytest.mark.django_db
@override_settings(**OFF)
def test_service_page_works_without_request_user_session(db):
    client = Client()
    response = client.get(url("AGR-01"))
    assert response.status_code == 200
    assert CompanyInquiry.objects.count() == 0
