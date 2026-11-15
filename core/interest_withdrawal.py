"""Signed, one-way customer opt-out without email or financial transactions."""
from django.core import signing
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.cache import patch_vary_headers
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from .signal_interest_models import CommercialInterest

SALT = "commercial-interest-withdraw-v1"
HOSTS = frozenset(("mojplaywin.com", "www.mojplaywin.com",
                   "zomorodmelal.ir", "www.zomorodmelal.ir"))
COPY = {
    "en": ("Withdraw contact consent", "Withdraw consent for this information request?",
           "Withdraw consent", "Your contact consent has been withdrawn."),
    "fa": ("لغو رضایت تماس", "آیا رضایت تماس برای این درخواست لغو شود؟",
           "لغو رضایت", "رضایت تماس برای این درخواست لغو شد."),
    "ar": ("سحب موافقة التواصل", "هل تريد سحب الموافقة لهذا الطلب؟",
           "سحب الموافقة", "تم سحب الموافقة على التواصل."),
    "de": ("Kontakt-Einwilligung widerrufen", "Einwilligung für diese Anfrage widerrufen?",
           "Widerrufen", "Die Kontakt-Einwilligung wurde widerrufen."),
}

def withdrawal_url(request, lead):
    if lead.pk is None:
        raise ValueError("Lead must be persisted")
    token = signing.dumps(
        {"id": lead.pk, "host": lead.source_host, "family": lead.offer_family}, salt=SALT
    )
    return request.build_absolute_uri(reverse("commercial_interest_withdraw",
                                              kwargs={"token": token}))

def _resolve(request, token):
    host = request.get_host().split(":")[0].lower()
    if host not in HOSTS or not request.is_secure():
        raise Http404("Unknown HTTPS merchant")
    try:
        payload = signing.loads(token, salt=SALT)
    except signing.BadSignature:
        raise Http404("Invalid revocation link") from None
    if (type(payload) is not dict or set(payload) != {"id", "host", "family"}
            or type(payload["id"]) is not int or payload["id"] <= 0
            or payload["host"] != host
            or payload["family"] not in ("signals", "moj_prop")):
        raise Http404("Invalid revocation scope")
    try:
        lead = CommercialInterest.objects.get(pk=payload["id"])
    except CommercialInterest.DoesNotExist:
        raise Http404("Unknown request") from None
    if lead.source_host != host or lead.offer_family != payload["family"]:
        raise Http404("Cross-merchant revocation not permitted")
    return lead

@never_cache
@csrf_protect
@require_http_methods(["GET", "POST"])
def withdrawal(request, token):
    lead = _resolve(request, token)
    lang = lead.source_language if lead.source_language in COPY else "en"
    confirmed = False
    if request.method == "POST":
        if set(request.POST) != {"csrfmiddlewaretoken"}:
            return HttpResponse("Unexpected form fields", status=400)
        with transaction.atomic():
            lead = CommercialInterest.objects.select_for_update().get(pk=lead.pk)
            if lead.status != "withdrawn":
                lead.status = "withdrawn"
                lead.save(update_fields=["status", "updated_at"])
        confirmed = True
    response = render(request, "core/interest_withdrawal.html", {
        "copy": COPY[lang], "lang": lang, "confirmed": confirmed,
        "direction": "rtl" if lang in ("fa", "ar") else "ltr",
    })
    patch_vary_headers(response, ("Cookie",))
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Referrer-Policy"] = "no-referrer"
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Frame-Options"] = "DENY"
    return response
