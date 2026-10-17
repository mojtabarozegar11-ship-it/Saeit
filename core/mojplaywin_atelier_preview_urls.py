"""Preview-only route coverage for selected live MojPlayWin legacy pages.

NEVER install this URLConf as production ROOT_URLCONF. These three routes
exist on the cPanel/live brand site but are not present in the shared
version-controlled config/urls.py. This module is solely for isolated visual
QA of preserved legacy brand templates with representative test data.
"""
from django.http import Http404
from django.shortcuts import render
from django.urls import path
from config.urls import urlpatterns as shared_urlpatterns
from core.mojplaywin_web_views import web_engineering
from core.services_views import services as shared_services

BRAND_HOSTS = {"mojplaywin.com", "www.mojplaywin.com"}
BRAND_PREVIEW_ROUTES = {
    "ai": {
        "title": "Artificial Intelligence",
        "headline": "Applied AI, with a clear purpose",
        "kicker": "SOFTWARE · AUTOMATION · RESEARCH",
        "body": "Review safe automation concepts, knowledge workflows, verifiable research and clear project deliverables for practical digital work.",
        "cards": [
            ("Reliable AI workflows", "ENGINEERING", "Set task boundaries, measurable acceptance criteria, error handling and human review before enabling unattended work."),
            ("Research and evidence", "SCIENCE", "Separate quoted evidence from interpretations. Track sources, uncertainty, corrections and reproducible data transformations."),
            ("Responsible deployment", "OPERATIONS", "Test permissions, protected data, logging, recovery and runtime ownership. A working demonstration does not prove production readiness."),
        ],
    },
    "blockchain": {
        "title": "Blockchain & Web3",
        "headline": "Digital networks and transparent verification",
        "kicker": "BLOCKCHAIN · TECHNOLOGY · SECURITY",
        "body": "Learn how distributed records, digital signatures, confirmation rules and responsible software design support auditable technical services.",
        "cards": [
            ("Distributed technology", "NETWORKS", "Understand transaction lifecycle, smart-contract behavior, confirmation time and infrastructure limits."),
            ("Wallet and key security", "RISK", "Protect private keys and recovery phrases, distinguish public identifiers from credentials, and test every authorization step."),
            ("Verification and delivery", "OPERATIONS", "Document idempotency, transaction evidence and fulfillment acceptance criteria in an isolated environment before selling services."),
        ],
    },
    "support": {
        "title": "MojPlayWin Support",
        "headline": "Practical help for digital work",
        "kicker": "SUPPORT · CUSTOMER CARE",
        "body": "Find structured help with product files, compatibility, order questions, project inquiries and responsible data handling.",
        "cards": [
            ("Digital product access", "DOWNLOADS", "Verify the intended file format, compatibility and delivery instructions without sharing account credentials."),
            ("Order and payment questions", "PAYMENT", "Retain public references to a transaction and consult verified order records before retrying a payment."),
            ("Technical projects", "PROJECTS", "Document the intended result, device or platform, reproducible steps, and appropriate confidentiality requirements."),
        ],
    },
}


def preview_page(request, page_key):
    if request.get_host().split(":")[0].lower() not in BRAND_HOSTS:
        raise Http404("Preview route is restricted to the main MojPlayWin host")
    data = BRAND_PREVIEW_ROUTES.get(page_key)
    if data is None:
        raise Http404("Unknown preview-only page")
    return render(request, "brands/mojplaywin/page.html", {"page": data, "page_key": page_key})


def main_services_preview(request):
    """Future main-host services destination; other brands keep original views."""
    if request.get_host().split(":")[0].lower() in BRAND_HOSTS:
        return web_engineering(request)
    return shared_services(request)


urlpatterns = [
    path("services/", main_services_preview, name="mojplaywin_preview_services"),
    path("web-engineering/", web_engineering, name="mojplaywin_preview_web_engineering"),
] + list(shared_urlpatterns) + [
    path(f"{page_key}/", preview_page, {"page_key": page_key}, name=f"mojplaywin_preview_{page_key}")
    for page_key in BRAND_PREVIEW_ROUTES
]
