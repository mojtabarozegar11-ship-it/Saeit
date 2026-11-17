"""MOJ-PROP-01 v1.2: canonical, buyer-readable *pre-contract* disclosure.

This module is source-only. It cannot issue payment instructions, accept a
purchase, process personal data, send email or start a trading challenge.
The disclosure fingerprint ties the full FA+EN text to canonical Plan 1
policy. The terms are an information packet, NOT an executed customer contract.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from decimal import Decimal
import hashlib
import json

from .plans import plan_for_code
from .rules import LEVELS
from .social_policy import NEW_CONTRACT_VERSION

SKU = "MOJ-PROP-01"
NETWORK = "TRON-mainnet"
NATIVE_SUN = 30_000_000
DOC_SCHEMA = "mojprop.plan1.buyer-disclosure.fa-en.v1"
NO_CHECKOUT = "INFORMATION_ONLY_NOT_PAYABLE"


@dataclass(frozen=True)
class Plan1BuyerDisclosure:
    """Copy + immutable digest for eventual specific buyer contract attachment."""

    schema: str
    sku: str
    contract_version: str
    fee_sun: int
    network: str
    two_phases_simulated: bool
    initial_real_usd_conditional: str
    max_funded_usd_conditional: str
    currency: str
    fa: str
    en: str
    digest_sha256: str
    status: str = NO_CHECKOUT
    invoice_issued: bool = False
    checkout_enabled: bool = False
    customer_identity_verified: bool = False
    customer_contract_signed: bool = False
    settlement_confirmed: bool = False
    challenge_enrollment_created: bool = False
    real_capital_allocated: bool = False
    customer_marketing_opt_in: bool = False


def _source_values():
    p = plan_for_code(SKU)
    assert p.code == SKU and p.number == 1
    # Guard all meaningful price, scope and participation values; if another
    # cycle changes policy, the buyer copy must be reviewed and re-digested.
    expected = (
        (p.entry_fee_trx, "30"),
        (p.starting_capital_usd, "100"),
        (p.maximum_capital_usd, "100000"),
        (p.stage_one_profit_target_pct, "9.6"),
        (p.stage_two_profit_target_pct, "6"),
        (p.daily_loss_limit_pct, "4"),
        (p.total_loss_limit_pct, "8"),
        (p.max_consistency_pct, "32"),
        (p.max_risk_per_trade_pct, "0.8"),
        (p.max_open_risk_pct, "1.6"),
        (p.trader_profit_share_pct, "70"),
        (p.company_profit_share_pct, "30"),
    )
    if any(Decimal(x) != Decimal(target) for x, target in expected):
        raise ValueError("Plan 1 finance and risk rules drift from signed v1.2 copy")
    if (p.duration_days != 28
            or p.minimum_verified_closed_trades != 50
            or p.min_trading_days_per_stage != 6
            or p.instagram_posts_per_challenge != 1
            or p.facebook_posts_per_challenge != 1
            or not p.entry_fee_owner_confirmed
            or not p.business_active_owner_declared
            or NEW_CONTRACT_VERSION != "2026-11-15/v1.2"
            or len(LEVELS) != 14
            or LEVELS[0] != Decimal("100")
            or LEVELS[-1] != Decimal("100000")):
        raise ValueError("Plan 1 version, simulated windows, or capital ladder drift")
    return p


def buyer_disclosure() -> Plan1BuyerDisclosure:
    p = _source_values()
    fa = (
        "مج پراپ — طرح ۱ (MOJ-PROP-01). این محصول چالش ارزیابی معامله‌گر است، "
        "نه گزارش آموزشی MOJPROP-STARTER30 و نه حساب واقعی در زمان خرید.\n"
        "هزینه دقیق یک چالش: ۳۰ واحد TRX بومی شبکه TRON Mainnet، برابر ۳۰٬۰۰۰٬۰۰۰ SUN. "
        "این مبلغ تبدیل یا معادل دلاری و ریالی نیست.\n"
        "هر دو مرحله ارزیابی شبیه‌سازی هستند؛ معامله با سرمایه حقیقی در مراحل ارزیابی انجام نمی‌شود. "
        "مهلت مجموع دو مرحله، ۲۸ روز متوالی از زمان تأیید مستقل تسویه پرداخت است، نه زمان ارسال درخواست. "
        "حداقل ۵۰ موقعیت مجزای بسته‌شده و آشتی‌داده‌شده در مجموع دو مرحله و دست‌کم "
        "۶ روز معاملاتی تأییدشده در هر مرحله لازم است.\n"
        "هدف سود مرحله اول ۹٫۶٪ و مرحله دوم ۶٪؛ حداکثر زیان روزانه ۴٪، "
        "زیان کل ۸٪، سهم بهترین روز ۳۲٪، ریسک هر معامله ۰٫۸٪ و ریسک باز کل ۱٫۶٪ است. "
        "سود شبیه‌سازی به معنی بازده واقعی یا تضمین‌شده نیست.\n"
        "بعد از قبولی در هر دو مرحله، حساب حقیقی اولیه با ۱۰۰ دلار سرمایه فقط در صورت "
        "احراز شرایط قرارداد، هویت، تأمین و تخصیص واقعی سرمایه و امکان اجرای کارگزار ایجاد می‌شود. "
        "وجود ۱۴ سطح سرمایه تا سقف ۱۰۰٬۰۰۰ دلار، تضمین ارتقا یا تأمین مالی نیست. "
        "تقسیم ۷۰٪ معامله‌گر و ۳۰٪ شرکت فقط برای سود واقعی واجد شرایطِ حساب تأمین‌شده است.\n"
        "سیاست نسخه v1.2 برای کل چالش، یک پست اصیل اینستاگرام و یک پست اصیل فیس‌بوک "
        "را با افشای شفاف رابطه تبلیغاتی در نظر دارد؛ اجرای آن تابع قوانین قابل اعمال و "
        "سیاست پلتفرم است، هیچ تعریف یا نظر مثبت اجباری نیست و حساب‌های شخصی مالک "
        "برای انتشار یا داده‌برداری استفاده نمی‌شوند. پست‌ها طبق قرارداد باید ۲۸ روز "
        "پس از انتشار در دسترس باشند.\n"
        "کشور و سن مجاز، احراز هویت، شیوه استرداد و انصراف، حمایت از داده‌ها و "
        "پشتیبانی و نحوه حل اختلاف باید در قرارداد مخصوص خریدار روشن و پذیرفته شود. "
        "ثبت علاقه‌مندی، رضایت بازاریابی یا عقد قرارداد و پرداخت تلقی نمی‌شود. "
        "این متن صرفاً اطلاع‌رسانی پیش از قرارداد است و هیچ نشانی پرداخت یا فاکتور صادر نمی‌کند."
    )
    en = (
        "MOJ PROP Plan 1 (MOJ-PROP-01) is a trader evaluation challenge, not the "
        "MOJPROP-STARTER30 educational report and not an immediately funded account.\n"
        "Exact one-time challenge price: 30 native TRX on TRON Mainnet = 30,000,000 SUN. "
        "This is not a USD or IRR converted quote.\n"
        "BOTH evaluation stages are simulated; no real capital is traded in either evaluation. "
        "The shared 28-consecutive-day deadline starts only after independently finalized payment, "
        "not at inquiry. At least 50 distinct, reconciled CLOSED positions in total across both "
        "stages and at least 6 verified trading days IN EACH stage are required.\n"
        "Stage profit goals: 9.6% then 6%; daily maximum loss 4%, total maximum loss 8%, "
        "best profitable day share 32%, maximum risk per order 0.8%, and total open risk 1.6%. "
        "Simulated performance does not guarantee any real return.\n"
        "After BOTH stages are passed, a real USD 100 initial funded account is CONDITIONAL "
        "on documented eligibility and KYC, genuine available capital allocation, and "
        "lawful broker feasibility. A 14-level ladder to USD 100,000 is not a guarantee "
        "of future funding. A 70% trader / 30% firm split concerns only eligible realized "
        "profit under an actually funded and agreed account.\n"
        "The v1.2 policy proposes ONE original Instagram and ONE original Facebook post "
        "for the entire challenge, each retained for 28 days after posting, with clear "
        "commercial-relationship disclosure and only where applicable law and platform "
        "terms permit. No forced positive endorsement; the owner's private social "
        "accounts must not be accessed, scraped or used.\n"
        "Buyer-specific contract terms must identify eligibility, age/country restrictions, "
        "identity checks, cancellation and fair refunds, privacy, support, and dispute routes "
        "before acceptance. An information inquiry is neither marketing consent nor a signed "
        "purchase. This pre-contract information issues NO invoice, wallet or payment request."
    )
    payload = {
        "schema": DOC_SCHEMA, "sku": SKU, "contract_version": NEW_CONTRACT_VERSION,
        "fee_sun": NATIVE_SUN, "network": NETWORK, "two_phases_simulated": True,
        "initial_real_usd_conditional": str(p.starting_capital_usd),
        "max_funded_usd_conditional": str(p.maximum_capital_usd),
        "currency": "TRX_NATIVE", "fa": fa, "en": en,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    result = Plan1BuyerDisclosure(**payload, digest_sha256=digest)
    # Fail-closed: keep a review artifact from being confused with a paid order.
    if any((result.invoice_issued, result.checkout_enabled,
            result.customer_contract_signed, result.settlement_confirmed,
            result.challenge_enrollment_created, result.real_capital_allocated,
            result.customer_marketing_opt_in)):
        raise RuntimeError("pre-contract disclosure has financial side effects")
    return result
