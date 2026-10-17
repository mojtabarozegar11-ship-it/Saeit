"""Verified double-entry trial balance, by business unit and currency."""
import csv
from collections import OrderedDict
from decimal import Decimal

from django.db.models import Sum
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .models import BusinessUnit, CURRENCIES, JournalLine
from .views import office_access, required_permission, page, no_cache

ZERO = Decimal("0.00")


def filters(request):
    if set(request.GET) - {"unit", "currency"}:
        raise ValueError("پارامتر گزارش نامعتبر است.")
    unit = request.GET.get("unit", "")
    currency = request.GET.get("currency", "")
    if unit and not BusinessUnit.objects.filter(code=unit).exists():
        raise ValueError("واحد شرکت نامعتبر است.")
    if currency and currency not in dict(CURRENCIES):
        raise ValueError("ارز نامعتبر است.")
    return unit, currency


def calculate(unit="", currency=""):
    qs = JournalLine.objects.filter(entry__status="posted")
    if unit:
        qs = qs.filter(entry__unit__code=unit)
    if currency:
        qs = qs.filter(entry__currency=currency)
    rows = qs.values(
        "entry__unit__code", "entry__unit__name", "entry__currency",
        "account__code", "account__name", "account__category",
    ).annotate(
        debit=Sum("debit"), credit=Sum("credit"),
    ).order_by("entry__unit__code", "entry__currency", "account__code")
    accounts, totals = [], OrderedDict()
    for source in rows:
        debit, credit = source["debit"] or ZERO, source["credit"] or ZERO
        net = debit - credit
        key = (source["entry__unit__code"], source["entry__currency"])
        account = {
            "unit_code": key[0], "unit_name": source["entry__unit__name"],
            "currency": key[1], "code": source["account__code"],
            "name": source["account__name"], "category": source["account__category"],
            "debit": debit, "credit": credit,
            "closing_debit": max(net, ZERO), "closing_credit": max(-net, ZERO),
        }
        accounts.append(account)
        if key not in totals:
            totals[key] = {
                "unit_code": key[0], "unit_name": account["unit_name"],
                "currency": key[1], "debit": ZERO, "credit": ZERO,
                "closing_debit": ZERO, "closing_credit": ZERO,
            }
        for field in ("debit", "credit", "closing_debit", "closing_credit"):
            totals[key][field] += account[field]
    return accounts, list(totals.values())


def safe_csv(value):
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


@never_cache
@office_access
@require_GET
def trial_balance(request):
    required_permission(request, "view_journalentry")
    try:
        unit, currency = filters(request)
    except ValueError as error:
        return no_cache(HttpResponseBadRequest(str(error)))
    accounts, totals = calculate(unit, currency)
    return page(request, "trial_balance", {
        "records": accounts, "totals": totals,
        "units": BusinessUnit.objects.order_by("code"),
        "currencies": CURRENCIES,
        "selected_unit": unit, "selected_currency": currency,
    })


@never_cache
@office_access
@require_GET
def trial_balance_csv(request):
    required_permission(request, "view_journalentry")
    try:
        unit, currency = filters(request)
    except ValueError as error:
        return no_cache(HttpResponseBadRequest(str(error)))
    accounts, totals = calculate(unit, currency)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="zomorod-trial-balance.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(("کد واحد", "نام واحد", "ارز", "کد حساب", "شرح حساب",
                     "گردش بدهکار", "گردش بستانکار", "مانده بدهکار", "مانده بستانکار"))
    for row in accounts:
        writer.writerow((safe_csv(row["unit_code"]), safe_csv(row["unit_name"]),
                         row["currency"], safe_csv(row["code"]), safe_csv(row["name"]),
                         str(row["debit"]), str(row["credit"]),
                         str(row["closing_debit"]), str(row["closing_credit"])))
    for row in totals:
        writer.writerow((safe_csv(row["unit_code"]), safe_csv(row["unit_name"]),
                         row["currency"], "", "جمع تفکیکی", str(row["debit"]),
                         str(row["credit"]), str(row["closing_debit"]),
                         str(row["closing_credit"])))
    return no_cache(response)
