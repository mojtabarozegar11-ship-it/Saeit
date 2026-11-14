"""C06: one-source company portal intake, no second lead database."""
from unittest.mock import patch

import pytest
from django.core.exceptions import DisallowedHost
from django.test import Client, override_settings
from django.urls import reverse

from core.company_inquiry_models import CompanyInquiry
from core.company_content_views import COMPANY_LEGACY_SOURCE_MARKER

ENABLE_FLAGS = {
    "DEBUG": True,
    "SERVICE_INTAKE_DJANGO_ENABLED": True,
    "SERVICE_INTAKE_SINGLE_SOURCE_APPROVED": True,
    "SERVICE_INTAKE_ROLLBACK_VERIFIED": True,
    "SERVICE_INTAKE_PRIVACY_REVIEWED": True,
    "SERVICE_INTAKE_SOURCE_OF_TRUTH": "django_company_inquiry_v1",
}

DISABLE_FLAGS = {
    "DEBUG": True,
    "SERVICE_INTAKE_DJANGO_ENABLED": False,
    "SERVICE_INTAKE_SINGLE_SOURCE_APPROVED": False,
    "SERVICE_INTAKE_ROLLBACK_VERIFIED": False,
    "SERVICE_INTAKE_PRIVACY_REVIEWED": False,
    "SERVICE_INTAKE_SOURCE_OF_TRUTH": "legacy_ask_master_unverified",
}

def payload(**changes):
    value = {
        "kind": "commercial",
        "name": "Private Customer",
        "organization": "Local Business",
        "email": "Customer@Example.COM",
        "phone": "",
        "subject": "Professional audit request",
        "message": "Please review the scope of our business website and propose an audit.",
        "consent": "on",
        "website": "",
    }
    value.update(changes)
    return value


@pytest.mark.django_db
@override_settings(**DISABLE_FLAGS)
def test_company_page_has_one_canonical_cta_not_shadow_form():
    response = Client().get(reverse("company"))
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "/ask-master/index.php?service=1" in html
    assert 'action="/company/"' not in html
    assert "company-inquiry-single-source" in html


@pytest.mark.django_db
@override_settings(**DISABLE_FLAGS)
def test_legacy_source_refuses_parallel_company_post_without_mutation():
    r = Client().post(reverse("company"), data=payload())
    assert r.status_code == 503
    assert "/ask-master/index.php?service=1" in r.content.decode("utf-8")
    assert CompanyInquiry.objects.count() == 0
    assert r["Cache-Control"].startswith("no-store")
    assert r["X-Content-Type-Options"] == "nosniff"


@pytest.mark.django_db
@pytest.mark.parametrize("missing_gate", [
    "SERVICE_INTAKE_DJANGO_ENABLED",
    "SERVICE_INTAKE_SINGLE_SOURCE_APPROVED",
    "SERVICE_INTAKE_ROLLBACK_VERIFIED",
    "SERVICE_INTAKE_PRIVACY_REVIEWED",
])
def test_any_missing_single_source_gate_blocks_company_capture(missing_gate):
    flags = dict(ENABLE_FLAGS)
    flags[missing_gate] = False
    with override_settings(**flags):
        response = Client().post(reverse("company"), payload())
    assert response.status_code == 503
    assert CompanyInquiry.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("bad_flag", ["True", 1, "yes", None])
def test_truthy_non_boolean_source_gate_is_not_authorization(bad_flag):
    flags = dict(ENABLE_FLAGS)
    flags["SERVICE_INTAKE_SINGLE_SOURCE_APPROVED"] = bad_flag
    with override_settings(**flags):
        r = Client().post(reverse("company"), payload())
    assert r.status_code == 503
    assert CompanyInquiry.objects.count() == 0


@pytest.mark.django_db
@override_settings(**ENABLE_FLAGS)
def test_unknown_source_label_still_blocks_when_all_flags_true():
    with override_settings(SERVICE_INTAKE_SOURCE_OF_TRUTH="legacy_ask_master_unverified"):
        r = Client().post(reverse("company"), payload())
    assert r.status_code == 503
    assert CompanyInquiry.objects.count() == 0


@pytest.mark.django_db
@override_settings(**ENABLE_FLAGS)
def test_enabled_company_page_has_informed_consent_and_honeypot():
    r = Client().get(reverse("company"))
    assert r.status_code == 200
    html = r.content.decode("utf-8")
    assert 'action="/company/"' in html
    assert 'name="consent"' in html
    assert 'name="website"' in html
    assert "company-inquiry-single-source" not in html


@pytest.mark.django_db
@override_settings(**ENABLE_FLAGS)
def test_consent_is_mandatory_and_missing_consent_cannot_create_lead():
    r = Client().post(reverse("company"), payload(consent=""))
    assert r.status_code == 302
    assert CompanyInquiry.objects.count() == 0


@pytest.mark.django_db
@override_settings(**ENABLE_FLAGS)
def test_honeypot_is_required_empty():
    r = Client().post(reverse("company"), payload(website="http://bot.example"))
    assert r.status_code == 302
    assert CompanyInquiry.objects.count() == 0


@pytest.mark.django_db
@override_settings(**ENABLE_FLAGS)
def test_consent_validated_company_request_creates_one_nonbinding_record():
    r = Client().post(reverse("company"), payload())
    assert r.status_code == 302
    row = CompanyInquiry.objects.get()
    assert row.status == "new"
    assert row.kind == "commercial"
    assert row.email == "customer@example.com"
    assert COMPANY_LEGACY_SOURCE_MARKER in row.internal_note
    assert "automatic_contact: false" in row.internal_note


@pytest.mark.django_db
@override_settings(**ENABLE_FLAGS)
def test_exact_repeat_within_window_does_not_duplicate_company_lead():
    client = Client()
    assert client.post(reverse("company"), payload()).status_code == 302
    assert client.post(reverse("company"), payload()).status_code == 302
    assert CompanyInquiry.objects.count() == 1


@pytest.mark.django_db
@override_settings(**ENABLE_FLAGS)
def test_different_customer_question_is_not_suppressed_by_same_email():
    client = Client()
    client.post(reverse("company"), payload())
    client.post(reverse("company"), payload(
        message="Please review a separate website with a different technical audit goal."
    ))
    assert CompanyInquiry.objects.count() == 2


@pytest.mark.django_db
@override_settings(**ENABLE_FLAGS)
@pytest.mark.parametrize("bad", [
    {"kind": "not-a-real-kind"},
    {"email": "not-email"},
    {"name": " "},
    {"subject": "no"},
    {"message": "too short"},
    {"subject": "x" * 301},
    {"message": "x" * 5001},
])
def test_malformed_customer_inquiries_cannot_create_records(bad):
    r = Client().post(reverse("company"), payload(**bad))
    assert r.status_code == 302
    assert CompanyInquiry.objects.count() == 0


@pytest.mark.django_db
@override_settings(**ENABLE_FLAGS)
def test_oversize_request_never_creates_lead():
    r = Client().post(reverse("company"), payload(message="x" * 30_000))
    assert r.status_code == 400
    assert CompanyInquiry.objects.count() == 0


@pytest.mark.django_db
@override_settings(**ENABLE_FLAGS)
def test_form_upload_is_not_allowed_even_if_fields_valid():
    from django.core.files.uploadedfile import SimpleUploadedFile
    file = SimpleUploadedFile("private.pdf", b"restricted attachment")
    r = Client().post(reverse("company"), payload(attachment=file))
    assert r.status_code == 400
    assert CompanyInquiry.objects.count() == 0


@pytest.mark.django_db
@override_settings(**ENABLE_FLAGS)
def test_json_and_unknown_media_types_cannot_create_form_lead():
    r = Client().post(reverse("company"), '{"name":"unknown"}',
                      content_type="application/json")
    assert r.status_code == 415
    assert CompanyInquiry.objects.count() == 0


@pytest.mark.django_db
@override_settings(**ENABLE_FLAGS, ALLOWED_HOSTS=[
    "testserver", "mojplaywin.com", "zomorodmelal.ir"
])
def test_company_post_is_not_reachable_from_mojplaywin_host():
    r = Client().post(reverse("company"), payload(), HTTP_HOST="mojplaywin.com")
    assert r.status_code == 404
    assert CompanyInquiry.objects.count() == 0


@pytest.mark.django_db
@override_settings(**ENABLE_FLAGS)
def test_request_does_not_send_contact_email_or_invoice():
    with patch("django.core.mail.send_mail", side_effect=AssertionError("outbound")):
        response = Client().post(reverse("company"), payload())
    assert response.status_code == 302
    assert CompanyInquiry.objects.count() == 1


@pytest.mark.django_db
@override_settings(**ENABLE_FLAGS)
def test_company_portal_receipt_is_not_spoofed_as_c05_service_consent():
    from core.service_quote_draft import preview_candidates
    Client().post(reverse("company"), payload())
    assert preview_candidates()["eligible_count"] == 0


@pytest.mark.django_db
@override_settings(**ENABLE_FLAGS)
def test_company_portal_response_is_no_store_after_valid_post():
    response = Client().post(reverse("company"), payload())
    assert "no-store" in response["Cache-Control"]
    assert response["X-Robots-Tag"] == "noindex, nofollow, noarchive"
    assert response["X-Content-Type-Options"] == "nosniff"


@pytest.mark.django_db
@override_settings(**ENABLE_FLAGS)
def test_unknown_host_returns_no_data_and_not_a_redirect():
    with override_settings(ALLOWED_HOSTS=["testserver", "unknown.example"]):
        response = Client().post(reverse("company"), payload(), HTTP_HOST="unknown.example")
    assert response.status_code == 404
    assert CompanyInquiry.objects.count() == 0


@pytest.mark.django_db
@override_settings(**DISABLE_FLAGS)
def test_legacy_reply_does_not_echo_any_submitted_private_fields():
    secret = "PRIVATE_CUSTOMER_REFERENCE_912471"
    r = Client().post(reverse("company"), payload(message=secret))
    assert secret not in r.content.decode("utf-8")
    assert CompanyInquiry.objects.count() == 0
