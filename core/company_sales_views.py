"""Native Zomorod Melal public inquiry endpoint; no external side effects."""
from django import forms
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from .company_sales_intake import (
    CompanySalesInquiryForm, require_company_host, save_inbound_inquiry,
    validate_body_size,
)


def _private(response):
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["Referrer-Policy"] = "same-origin"
    return response


@never_cache
@csrf_protect
@require_http_methods(["GET", "POST"])
def company_contact(request):
    require_company_host(request)
    if request.method == "GET":
        # Only a server session flag, never a query parameter, proves that
        # this browser has just submitted the form.
        received = request.session.pop("_company_inquiry_received", False) is True
        form = CompanySalesInquiryForm()
        return _private(render(request, "core/company_contact.html", {
            "form": form, "inquiry_received": received,
        }))
    try:
        validate_body_size(request)
    except forms.ValidationError:
        return _private(HttpResponse(
            "درخواست بیش از حد مجاز یا نامعتبر است.",
            status=413, content_type="text/plain; charset=utf-8",
        ))
    form = CompanySalesInquiryForm(request.POST)
    if not form.is_valid():
        return _private(render(request, "core/company_contact.html", {
            "form": form, "inquiry_received": False,
        }, status=422))
    save_inbound_inquiry(form)
    request.session["_company_inquiry_received"] = True
    response = redirect("contact")
    return _private(response)
