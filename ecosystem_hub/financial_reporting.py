"""Internal period income/expense analysis. No statutory profit claim.

Read only posted journals. Every amount remains in its originating legal
business unit and currency; there is no automatic FX or intercompany
elimination. Direct ledger account categories supply management figures.
"""
import csv
from collections import OrderedDict
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.http import HttpResponse, HttpResponseBadRequest, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from enterprise_portal.models import CURRENCIES, JournalLine
from enterprise_portal.trial_balance import safe_csv
from enterprise_portal.views import office_access, no_cache
from .access import user_units
from .views import page, require_hub

ZERO = Decimal("0.00")


def _require_financial_access(request):
    require_hub(request)
    if not (request.user.is_superuser or (
        request.user.has_perm("enterprise_portal.view_journalentry")
        and request.user.has_perm("enterprise_portal.view_ledgeraccount")
    )):
        raise PermissionDenied("برای گزارش درآمد و هزینه، مجوز مشاهده دفتر کل و حساب‌ها لازم است.")


def _parameters(request):
    if set(request.GET) - {"unit", "currency", "start", "end"}:
        raise ValueError("پارامتر گزارش نامعتبر است.")
    if any(len(request.GET.getlist(key)) > 1 for key in request.GET):
        raise ValueError("تکرار فیلتر گزارش مجاز نیست.")
    today = timezone.localdate()
    first = date(today.year, 1, 1)
    start_raw = request.GET.get("start")
    end_raw = request.GET.get("end")
    start = parse_date(start_raw) if start_raw else first
    end = parse_date(end_raw) if end_raw else today
    if (start is None or end is None or end < start or
            end - start > timedelta(days=3660) or
            start.year < 1900 or end.year > 2100):
        raise ValueError("بازه تاریخ گزارش معتبر نیست.")
    currency = request.GET.get("currency", "")
    if currency and currency not in dict(CURRENCIES):
        raise ValueError("ارز انتخاب‌شده پشتیبانی نمی‌شود.")
    code = request.GET.get("unit", "")
    allowed = user_units(request.user)
    # A nonexistent or another tenant's code has the same 404 response.
    chosen = get_object_or_404(allowed, code=code) if code else None
    return {"start": start, "end": end, "currency": currency,
            "unit": chosen, "unit_code": code, "allowed_units": allowed}


def calculate_management_income(*, allowed_units, start, end, currency="", unit=None):
    """No summation across currencies or units. Negative reversals are valid."""
    records = JournalLine.objects.filter(
        entry__status="posted",
        entry__unit__in=allowed_units,
        entry__booked_on__gte=start,
        entry__booked_on__lte=end,
        account__category__in=("income", "expense"),
    )
    if unit is not None:
        records = records.filter(entry__unit=unit)
    if currency:
        records = records.filter(entry__currency=currency)

    grouped = records.values(
        "entry__unit__code", "entry__unit__name", "entry__currency",
        "account__code", "account__name", "account__category",
    ).annotate(debit=Sum("debit"), credit=Sum("credit")).order_by(
        "entry__unit__code", "entry__currency", "account__category", "account__code"
    )
    details, totals = [], OrderedDict()
    for record in grouped:
        debit = record["debit"] or ZERO
        credit = record["credit"] or ZERO
        category = record["account__category"]
        amount = credit - debit if category == "income" else debit - credit
        key = (record["entry__unit__code"], record["entry__currency"])
        if key not in totals:
            totals[key] = {
                "unit_code": key[0], "unit_name": record["entry__unit__name"],
                "currency": key[1], "income": ZERO, "expense": ZERO, "result": ZERO,
            }
        totals[key][category] += amount
        details.append({
            "unit_code": key[0], "unit_name": record["entry__unit__name"],
            "currency": key[1], "account_code": record["account__code"],
            "account_name": record["account__name"],
            "category": category, "debit": debit, "credit": credit, "amount": amount,
        })
    for item in totals.values():
        item["result"] = item["income"] - item["expense"]
    return details, list(totals.values())


def _report(request):
    _require_financial_access(request)
    try:
        selected = _parameters(request)
    except ValueError as error:
        return None, no_cache(HttpResponseBadRequest(str(error)))
    details, totals = calculate_management_income(
        allowed_units=selected["allowed_units"],
        start=selected["start"], end=selected["end"],
        currency=selected["currency"], unit=selected["unit"],
    )
    return {**selected, "details": details, "totals": totals}, None


@never_cache
@office_access
@require_GET
def income_report(request):
    data, error = _report(request)
    if error is not None:
        return error
    return page(request, "income", {
        **data, "units": data["allowed_units"].order_by("code"),
        "currencies": CURRENCIES, "section": "income",
    })


@never_cache
@office_access
@require_GET
def income_csv(request):
    data, error = _report(request)
    if error is not None:
        return error
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="zomorod-management-income.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow((
        "واحد", "نام واحد", "ارز", "حساب", "نام حساب", "طبقه",
        "گردش بدهکار", "گردش بستانکار", "مقدار خالص در طبقه",
    ))
    for item in data["details"]:
        writer.writerow((
            safe_csv(item["unit_code"]), safe_csv(item["unit_name"]),
            item["currency"], safe_csv(item["account_code"]),
            safe_csv(item["account_name"]), item["category"],
            str(item["debit"]), str(item["credit"]), str(item["amount"]),
        ))
    writer.writerow(())
    writer.writerow(("واحد", "نام واحد", "ارز", "درآمد خالص", "هزینه خالص", "نتیجه مدیریتی"))
    for item in data["totals"]:
        writer.writerow((
            safe_csv(item["unit_code"]), safe_csv(item["unit_name"]), item["currency"],
            str(item["income"]), str(item["expense"]), str(item["result"]),
        ))
    return no_cache(response)
