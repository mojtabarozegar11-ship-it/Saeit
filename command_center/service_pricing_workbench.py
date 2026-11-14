"""Owner-only, side-effect-free commercial service unit economics workbench.

Uses the existing deterministic model, never a payment gateway or lead body.
Never pre-fills unknown unit costs with zero or approves a customer quotation.
"""
from django import forms
from django.contrib.auth.decorators import user_passes_test
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from core.revenue_unit_economics import compute_quote_scenario


FIELDS = (
    "currency", "base_unit_price", "discount_percent", "direct_unit_cost",
    "delivery_unit_cost", "payment_unit_fee", "refund_unit_reserve",
    "tax_unit_reserve", "period_fixed_cost", "expected_units",
)
CURRENCIES = (("IRT", "تومان"), ("IRR", "ریال"), ("USD", "دلار آمریکا"), ("TRX", "ترون"))
PRICING_LABELS = {
    "currency": "واحد پولی (تمام ورودی‌ها در همین واحد)",
    "base_unit_price": "قیمت پایه هر واحد خدمت",
    "discount_percent": "تخفیف درصدی",
    "direct_unit_cost": "هزینه مستقیم اجرای یک واحد",
    "delivery_unit_cost": "هزینه تحویل یک واحد",
    "payment_unit_fee": "کارمزد پرداخت هر واحد",
    "refund_unit_reserve": "ذخیره مرجوعی/بازپرداخت هر واحد",
    "tax_unit_reserve": "ذخیره مالیات هر واحد",
    "period_fixed_cost": "هزینه ثابت کل دوره",
    "expected_units": "تعداد فروش مفروض همان دوره",
}


class ServicePricingScenarioForm(forms.Form):
    currency = forms.ChoiceField(choices=CURRENCIES, label=PRICING_LABELS["currency"])
    expected_units = forms.IntegerField(
        min_value=0, max_value=1_000_000,
        label=PRICING_LABELS["expected_units"],
    )

    for_name = None  # no lead ID, person or other customer field accepted

    base_unit_price = forms.DecimalField(
        min_value=0, max_digits=23, decimal_places=12,
        label=PRICING_LABELS["base_unit_price"],
    )
    discount_percent = forms.DecimalField(
        min_value=0, max_value=100, max_digits=5, decimal_places=2,
        label=PRICING_LABELS["discount_percent"],
    )
    direct_unit_cost = forms.DecimalField(
        min_value=0, max_digits=23, decimal_places=12,
        label=PRICING_LABELS["direct_unit_cost"],
    )
    delivery_unit_cost = forms.DecimalField(
        min_value=0, max_digits=23, decimal_places=12,
        label=PRICING_LABELS["delivery_unit_cost"],
    )
    payment_unit_fee = forms.DecimalField(
        min_value=0, max_digits=23, decimal_places=12,
        label=PRICING_LABELS["payment_unit_fee"],
    )
    refund_unit_reserve = forms.DecimalField(
        min_value=0, max_digits=23, decimal_places=12,
        label=PRICING_LABELS["refund_unit_reserve"],
    )
    tax_unit_reserve = forms.DecimalField(
        min_value=0, max_digits=23, decimal_places=12,
        label=PRICING_LABELS["tax_unit_reserve"],
    )
    period_fixed_cost = forms.DecimalField(
        min_value=0, max_digits=23, decimal_places=12,
        label=PRICING_LABELS["period_fixed_cost"],
    )


@user_passes_test(
    lambda u: bool(u.is_active and u.is_superuser),
    login_url="/admin/login/",
)
@csrf_protect
@require_http_methods(["GET", "POST"])
def service_pricing_workbench(request):
    if request.method == "POST" and len(request.body) > 12_288:
        return HttpResponse("invalid_request_size", status=413)
    form = ServicePricingScenarioForm(
        request.POST if request.method == "POST" else None
    )
    scenario = None
    if request.method == "POST" and form.is_valid():
        raw = {
            name: (str(form.cleaned_data[name]) if name != "expected_units"
                   else form.cleaned_data[name])
            for name in FIELDS
        }
        try:
            scenario = compute_quote_scenario(raw)
        except (ValueError, ArithmeticError):
            form.add_error(None, "سناریو با محدودیت‌های محاسبه سازگار نیست.")
    response = render(
        request, "command_center/service_pricing_workbench.html",
        {
            "form": form,
            "scenario": scenario,
            "financial_claims_verified": False,
            "service_quote_approved": False,
        },
    )
    response["Cache-Control"] = "no-store, private, max-age=0"
    response["Pragma"] = "no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response["Vary"] = "Cookie"
    return response
