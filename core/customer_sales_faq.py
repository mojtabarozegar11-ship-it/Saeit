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
                "entry price is 30 TRX, but the landing page is not proof that "
                "checkout or funded access is ready. Do not send TRX until "
                "the server issues a unique invoice and the terms are verified. "
                f"Details: {MOJ_PROP_URL} | Free written terms request: {MOJ_PROP_TERMS_REQUEST_URL} | Checkout information: {MOJ_PROP_CHECKOUT_URL}"
            )
        return (
            "مج‌پراپ یک چالش معاملاتی شبیه‌سازی‌شده است. قیمت معرفی‌شدهٔ Starter30 "
            "برابر ۳۰ TRX است؛ نمایش صفحه به‌معنای آماده‌بودن پرداخت یا صدور حساب نیست. "
            "تا زمان دریافت فاکتور اختصاصی صادرشده از سرور و بررسی شرایط، هیچ TRX ارسال نکنید. "
            f"اطلاعات: {MOJ_PROP_URL} | درخواست رایگان شرایط کتبی: {MOJ_PROP_TERMS_REQUEST_URL} | صفحهٔ اطلاعات ثبت‌نام: {MOJ_PROP_CHECKOUT_URL}"
        )
    if signals:
        if re.search(r"\b(signals?|copy trading)\b", text) and not any("\u0600" <= c <= "\u06ff" for c in text):
            return (
                "For the MOJ PROP trading-signal information page, see "
                f"{MOJ_SIGNALS_URL}. Request free written scope: {MOJ_SIGNALS_REQUEST_URL}. Live subscription availability, performance and "
                "delivery have not been verified here; do not pay without a valid server invoice."
            )
        return (
            f"اطلاعات خدمات سیگنال معاملاتی: {MOJ_SIGNALS_URL}. درخواست رایگان پیشنهاد کتبی: {MOJ_SIGNALS_REQUEST_URL}. "
            "فعال‌بودن اشتراک، نتایج معاملات و تحویل سرویس در این پاسخ تأیید نمی‌شود. "
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
