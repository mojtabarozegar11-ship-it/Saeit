"""Private, read-only MOJ PROP virtual statement. No orders or payments.

This view intentionally renders only already-persisted DEMO fills and
REALIZED cash accounting. It cannot attest external market prices/equity,
execute a trade, enroll a buyer, or authorize a broker payout.

Flag is FALSE until a separately reviewed deployment + live DB recovery.
"""
from datetime import timedelta
import re

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from prop_firm.plan1_v141_virtual_tenant_models import PropV141VirtualBook


_ALLOWED_HOSTS = frozenset(("mojplaywin.com", "www.mojplaywin.com"))
_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
_LIMIT = 25
_DEFAULT_LANGUAGE = "en"

_LOCALIZED = {
    "en": {
        "title": "MOJ PROP | Private virtual statement",
        "demo": "DEMO RECORDS ONLY — NOT LIVE TRADING",
        "intro": "Private statement of recorded simulated fills. No independent price/equity verification has been completed.",
        "challenge": "Challenge reference",
        "stage": "Unlocked demo stage",
        "events": "Recorded virtual fill events",
        "closed": "Fully closed virtual positions",
        "realized": "Recorded realized virtual net P&L (USD)",
        "deadline": "Evaluation deadline (UTC; overall 28-day window)",
        "activity": "Latest 25 recorded fills",
        "number": "Sequence",
        "action": "Action",
        "side": "Side",
        "quantity": "Quantity (oz)",
        "price": "Recorded fill price (USD/oz)",
        "timestamp": "Recorded timestamp (UTC)",
        "empty": "No simulated fill events have been recorded.",
        "warning": "This is NOT live market equity, funded capital, an official challenge pass, a payment receipt, or a right to withdraw.",
        "copyright": "No client order entry, brokerage access, deposits or payouts are available on this page.",
    },
    "fa": {
        "title": "مج پراپ | صورتحساب خصوصی معاملات مجازی",
        "demo": "صرفاً سوابق دمو — بدون معامله واقعی",
        "intro": "صورتحساب خصوصی رویدادهای ثبت‌شده شبیه‌سازی؛ صحت مستقل قیمت و ارزش روز حساب هنوز تأیید نشده است.",
        "challenge": "شناسه چالش",
        "stage": "مرحله دمو فعال‌شده",
        "events": "تعداد رویدادهای معاملات مجازی",
        "closed": "موقعیت‌های مجازی کاملاً بسته‌شده",
        "realized": "سود/زیان خالص تحقق‌یافته مجازی (دلار)",
        "deadline": "پایان کل فرصت ارزیابی ۲۸روزه (UTC)",
        "activity": "۲۵ رویداد ثبت‌شده اخیر",
        "number": "ترتیب",
        "action": "عملیات",
        "side": "جهت",
        "quantity": "مقدار (اونس)",
        "price": "قیمت ثبت‌شده (دلار/اونس)",
        "timestamp": "زمان ثبت‌شده (UTC)",
        "empty": "هنوز معامله مجازی ثبت نشده است.",
        "warning": "این صفحه ارزش لحظه‌ای حساب، سرمایه واقعی، قبولی رسمی چالش، رسید پرداخت یا حق برداشت نیست.",
        "copyright": "در این صفحه ثبت سفارش، اتصال به کارگزار، واریز و برداشت فعال نیست.",
    },
}


def _allowed_statement_request(request, challenge_ref):
    if getattr(settings, "MOJ_PROP_V141_PORTFOLIO_ENABLED", False) is not True:
        raise Http404("Private statement is disabled")
    try:
        host = request.get_host().split(":", 1)[0].lower()
    except Exception as exc:
        raise Http404("Invalid host") from exc
    if host not in _ALLOWED_HOSTS or request.is_secure() is not True:
        raise Http404("MojPlayWin HTTPS only")
    if request.META.get("QUERY_STRING", "") or _REF.fullmatch(challenge_ref) is None:
        raise Http404("Invalid private reference")


@login_required
@never_cache
def moj_prop_v141_private_statement(request, challenge_ref):
    """Authenticated, tenant-scoped read-only template with a bounded history."""
    _allowed_statement_request(request, challenge_ref)
    if request.method not in ("GET", "HEAD"):
        return HttpResponseNotAllowed(["GET", "HEAD"])
    book = (PropV141VirtualBook.objects
            .select_related("state")
            .filter(owner_id=request.user.pk,
                    state__challenge_ref=challenge_ref)
            .first())
    if book is None or book.owner_id != request.user.pk:
        raise Http404("No matching private challenge")
    # Query never selects arbitrary other users: book comes from owner filter.
    recent = tuple(
        book.virtual_fills.order_by("-sequence").values(
            "sequence", "action", "direction", "quantity_ounces",
            "price_usd_per_ounce", "executed_at_utc",
        )[:_LIMIT]
    )
    language_header = request.headers.get("Accept-Language", "")
    lang = "fa" if language_header.lower().startswith("fa") else _DEFAULT_LANGUAGE
    deadline = book.evaluation_started_at + timedelta(days=28)
    response = render(request, "mojprop/v141-private-demo-statement.html", {
        "labels": _LOCALIZED[lang],
        "lang": lang,
        "direction": "rtl" if lang == "fa" else "ltr",
        "challenge_ref": book.state.challenge_ref,
        "stage": book.max_unlocked_stage,
        "event_count": book.last_sequence,
        "closed_count": book.last_fully_closed_count,
        "realized_usd": book.last_realized_net_usd,
        "deadline": deadline,
        "deadline_passed": timezone.now() >= deadline,
        "recent": recent,
    })
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Pragma"] = "no-cache"
    response["Referrer-Policy"] = "no-referrer"
    response["X-Frame-Options"] = "DENY"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'self'; base-uri 'none'; "
        "frame-ancestors 'none'; form-action 'none'; connect-src 'none'"
    )
    response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
    return response
