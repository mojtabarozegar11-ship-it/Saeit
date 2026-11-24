"""Deterministic, API-free commercial navigation for the single central bot.

These replies are pointers to verified public site routes, not claims that
checkout, an invoice, a paid signal subscription or an entitlement succeeded.
Never ask a customer to transfer TRX merely because a page/CTA exists.
"""
from __future__ import annotations

import re

MOJ_PROP_URL = "https://mojplaywin.com/moj-prop/"
MOJ_PROP_CHECKOUT_URL = "https://mojplaywin.com/mojprop-starter30-checkout/"
MOJ_PROP_TERMS_REQUEST_URL = "https://mojplaywin.com/moj-prop-intake/?format=html&service=blueprint&package=starter-30-trx"
MOJ_SIGNALS_REQUEST_URL = "https://mojplaywin.com/moj-prop-intake/?format=html&service=signals"
MOJ_SIGNALS_URL = "https://mojplaywin.com/moj-prop/signals/"
MOJ_STORE_URL = "https://mojplaywin.com/store/"


def _clean(message):
    text = str(message or "").casefold().replace("ي", "ی").replace("ك", "ک")
    text = re.sub(r"[\u200c\u200d\u200e\u200f]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def local_sales_answer(message):
    """Return a bounded, non-generative answer only for known intents.

    Do not collect wallet identifiers or personal information. If intent is
    ambiguous, caller must use its normal truthful message-intake flow.
    """
    text = _clean(message)
    if len(text) > 2000:
        return None
    # A price inquiry from a Bulgarian-speaking buyer must not fall back to
    # an English-only answer simply because it also contains "Moj Prop".
    # Restrict multilingual matching to the explicit brand/Starter30 intent:
    # never answer arbitrary Bulgarian questions, and never create an invoice.
    brand = bool(re.search(r"\b(moj[ -]?prop|starter30)\b", text))
    bulgarian = brand and any(term in text for term in (
        "колко струва", "цената", "цена", "такса", "плащане",
        "как да платя", "виртуален", "баланс", "етап", "български",
    ))
    if bulgarian:
        return (
            "MOJ PROP Starter30 е симулирано търговско предизвикателство, "
            "а не реална брокерска сметка. Обявената начална такса е 30 TRX. "
            "Стартовият виртуален баланс е 1 000 USD; при успешно преминаване "
            "на следващи етапи виртуалният лимит може условно да нарасне "
            "до 100 000 USD. Това не е гаранция за одобрение, доход или награда. "
            "Наличността на платено записване не е потвърдена тук. "
            "НЕ изпращайте TRX преди уникална фактура от сървъра и проверка "
            "на писмените условия. "
            f"Правила: {MOJ_PROP_URL} | Безплатно искане на условия: "
            f"{MOJ_PROP_TERMS_REQUEST_URL}"
        )
    en = bool(re.search(r"\b(moj[ -]?prop|starter30|prop firm|funded challenge|trading challenge)\b", text))
    prop = en or any(word in text for word in ("مج پراپ", "مج‌پراپ", "پراپ", "چالش معامله"))
    signals = bool(re.search(r"\b(signals?|copy trading)\b", text)) or any(
        word in text for word in ("سیگنال", "ربات معامله", "اشتراک ترید")
    )
    store = bool(re.search(r"\b(store|shop|digital products?)\b", text)) or any(
        word in text for word in ("فروشگاه", "دانلود محصول", "محصول دیجیتال")
    )
    if prop:
        if en and not any("\u0600" <= c <= "\u06ff" for c in text):
            return (
                "MOJ PROP offers a simulated trading challenge. The listed Starter30 "
                "entry price is 30 TRX, with a $1,000 virtual starting balance. "
                "Later stages may conditionally increase virtual limits up to $100,000; "
                "passing a stage, receiving a payout or being enrolled is not guaranteed. "
                "The landing page is not proof that checkout or funded access is ready. "
                "Do not send TRX until "
                "the server issues a unique invoice and the terms are verified. "
                f"Details: {MOJ_PROP_URL} | Free written terms request: {MOJ_PROP_TERMS_REQUEST_URL} | Checkout information: {MOJ_PROP_CHECKOUT_URL}"
            )
        return (
            "مج‌پراپ یک چالش معاملاتی شبیه‌سازی‌شده است. قیمت معرفی‌شدهٔ Starter30 "
            "برابر ۳۰ TRX است و سرمایه آغازین فقط ۱٬۰۰۰ دلار مجازی است. "
            "در صورت موفقیت در مراحل بعدی، سقف سرمایه مجازی می‌تواند به‌صورت مشروط تا ۱۰۰٬۰۰۰ دلار افزایش یابد؛ "
            "قبولی، سود، پاداش یا فعال‌بودن خرید تضمین نمی‌شود. "
            "نمایش صفحه به‌معنای آماده‌بودن پرداخت یا صدور حساب نیست. "
            "تا زمان دریافت فاکتور اختصاصی صادرشده از سرور و بررسی شرایط، هیچ TRX ارسال نکنید. "
            f"اطلاعات: {MOJ_PROP_URL} | درخواست رایگان شرایط کتبی: {MOJ_PROP_TERMS_REQUEST_URL} | صفحهٔ اطلاعات ثبت‌نام: {MOJ_PROP_CHECKOUT_URL}"
        )
    if signals:
        if re.search(r"\b(signals?|copy trading)\b", text) and not any("\u0600" <= c <= "\u06ff" for c in text):
            return (
                "For the one-time MOJ PROP Educational Weekly Brief, use "
                "https://mojplaywin.com/commerce/book/1467/?utm_source=mojtaba_bot&utm_medium=faq_response&utm_campaign=signal_weekly_brief&utm_content=customer_sales_faq. The trading-signal information page is "
                f"{MOJ_SIGNALS_URL}. Monthly or quarterly research remains a written-scope request: {MOJ_SIGNALS_REQUEST_URL}. "
                "For your security, do not pay without a valid server invoice."
            )
        return (
            "خرید گزارش هفتگی آموزشی سیگنال: https://mojplaywin.com/commerce/book/1467/. "
            f"صفحهٔ سیگنال: {MOJ_SIGNALS_URL}. درخواست کتبی خدمات ماهانه یا فصلی: {MOJ_SIGNALS_REQUEST_URL}. "
            "بدون فاکتور معتبر سرور پرداخت نکنید."
        )
    if store:
        if re.search(r"\b(store|shop|digital products?)\b", text) and not any("\u0600" <= c <= "\u06ff" for c in text):
            return (
                f"Digital product listings: {MOJ_STORE_URL}. "
                "Order, payment and download access must each be confirmed by the store."
            )
        return (
            f"صفحهٔ محصولات دیجیتال مج‌پلی‌وین: {MOJ_STORE_URL}. "
            "ثبت سفارش، پرداخت و تحویل دانلود باید هرکدام در خود فروشگاه تأیید شوند."
        )
    return None
