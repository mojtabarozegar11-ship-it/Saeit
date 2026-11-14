"""Single-source, nonbinding company service intake routing contract.

The legacy company /ask-master form is the only default destination. Django
lead capture cannot be enabled by adding routes or merging a PR alone.

This module never checks the live PHP host, never claims external parity, and
does not migrate any personal data. Four settings are necessary but not proof of
readiness; release management must independently verify source-of-truth.
"""
from __future__ import annotations

from django.conf import settings
from django.urls import reverse

from .service_sales_controls import SERVICE_CARDS


LEGACY_INQUIRY_PATH = "/ask-master/index.php?service=1"
EXPECTED_SOURCE = "django_company_inquiry_v1"
_ACTIVE_FLAGS = (
    "SERVICE_INTAKE_DJANGO_ENABLED",
    "SERVICE_INTAKE_SINGLE_SOURCE_APPROVED",
    "SERVICE_INTAKE_ROLLBACK_VERIFIED",
    "SERVICE_INTAKE_PRIVACY_REVIEWED",
)


def _feature_flags() -> dict[str, bool]:
    """Exact bool True, not truthy strings, controls release routing."""
    return {
        flag: getattr(settings, flag, False) is True
        for flag in _ACTIVE_FLAGS
    }


def django_service_intake_active() -> bool:
    """Default OFF; all four explicit gates and exact source must be aligned."""
    return (
        all(_feature_flags().values())
        and getattr(settings, "SERVICE_INTAKE_SOURCE_OF_TRUTH", "") == EXPECTED_SOURCE
    )


def service_contact_url(service_code: str) -> str:
    """Return one canonical, in-domain destination; never mix lead stores."""
    if not isinstance(service_code, str) or service_code not in SERVICE_CARDS:
        raise ValueError("service code must match the authoritative catalogue")
    if django_service_intake_active():
        return reverse("service_inquiry", args=[service_code])
    return LEGACY_INQUIRY_PATH


def service_contact_card(service_code: str) -> dict:
    """Presentation metadata only, no falsified payment or live-host claims."""
    destination = service_contact_url(service_code)
    active = django_service_intake_active()
    return {
        "service_code": service_code,
        "contact_url": destination,
        "intake_source": EXPECTED_SOURCE if active else "legacy_ask_master_unverified",
        "review_request_only": True,
        "prices_approved": False,
        "contract_active": False,
        "customer_payment_taken": False,
        "live_origin_health": None,
    }


def service_intake_source_snapshot() -> dict:
    """No server secrets or private customer records; owner-only callers."""
    flags = _feature_flags()
    activated = django_service_intake_active()
    return {
        "agent": "mojtaba.bot.ai",
        "schema_version": 1,
        "read_only": True,
        "privacy": "no_customer_data_no_secrets",
        "authoritative_catalogue_count": len(SERVICE_CARDS),
        "django_new_leads_enabled": activated,
        "routing_mode": EXPECTED_SOURCE if activated else "legacy_ask_master_unverified",
        # The historic /company/ form used to bypass the same source policy.
        # Expose the actual POST and UI behavior without accessing customer PII.
        "company_portal_django_form_visible": activated,
        "company_portal_django_post_enabled": activated,
        "company_portal_post_when_disabled": "503_no_store_no_pii_forward",
        "company_portal_external_fallback": LEGACY_INQUIRY_PATH,
        "company_portal_legacy_php_health_verified": None,
        "fallback_path": LEGACY_INQUIRY_PATH,
        "django_gate_flags": flags,
        "source_configuration_match": (
            getattr(settings, "SERVICE_INTAKE_SOURCE_OF_TRUTH", "")
            == EXPECTED_SOURCE
        ),
        "live_php_form_verified": None,
        "live_django_db_verified": None,
        "live_cross_system_reconciliation": None,
        "real_revenue_collected": None,
        "production_release_authorized_by_this_report": False,
    }
