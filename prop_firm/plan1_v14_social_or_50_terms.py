"""Prospective MOJ-PROP-01 FA/EN customer terms: 50 TOTAL + social OR 28 days.

Additive to v1.2 and v1.3; never changes an existing customer agreement.
Not a signed contract, marketing authorization, payment, enrollment, brokerage
allocation, profit entitlement, or release permission. External legal review
must determine whether mandatory financial-promotion posts are lawful.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from decimal import Decimal
import json
import re

from .xauusd_v13_draft_terms import draft_gold_terms_v13

VERSION = "2026-11-17/v1.4.1-50-OR-28D-DRAFT"
SCHEMA = "mojprop.plan1.bilingual.50-total.social-or-28d.review.v1"
MIN_VERIFIED_CLOSED_TOTAL = 50
MIN_TRADING_DAYS_EACH_PHASE = 6
MIN_SOCIAL_POSTS = 1
SOCIAL_PLATFORMS = ("instagram", "facebook")
SOCIAL_DURATION_HOURS = 28 * 24
SOCIAL_LOGICAL_OPERATOR = "OR"

FA = (
    "شرایط پیشنهادی غیرقابل فروش MOJ-PROP-01 (نسخه پیش‌نویس جدید): "
    "هزینه شرکت در چالش ۳۰ TRX بومی شبکه TRON است و فعلاً دریافت نمی‌شود. "
    "ارزیابی شامل دو مرحله دمو به‌ترتیب با هدف سود خالص ۹٫۶٪ و ۶٪، "
    "حداقل ۵۰ موقعیت معاملاتی بسته‌شده و مستقلاً تطبیق‌شده در مجموع هر دو مرحله "
    "(نه ۵۰ معامله در هر مرحله)، حداقل ۶ روز معاملاتی تأییدشده در هر مرحله "
    "و مهلت ۲۸ روز برای ارزیابی است. "
    "شرط تبلیغاتی پیشنهادی: شرکت‌کننده باید حداقل یک پست اصلی واجد شرایط "
    "در اینستاگرام یا فیس‌بوک (یکی از این دو کافی است و هر دو الزامی نیست) منتشر کند "
    "و آن را حداقل ۲۸ روز متوالی (۶۷۲ ساعت) در دسترس عمومی نگه دارد. "
    "مهلت ۲۸روزه ارزیابی معامله و مهلت ۲۸روزه ماندگاری پست مستقل هستند؛ "
    "اگر پست دیرتر منتشر شود، تأیید نهایی تا پایان ۶۷۲ ساعت به تعویق می‌افتد. "
    "پست باید رابطه شرکت‌کننده با چالش را شفاف اعلام کند، وعده سود ندهد، "
    "مستلزم انتشار اطلاعات مالی شخصی نباشد و با مقررات پلتفرم و قوانین تبلیغات مالی سازگار باشد. "
    "محتوا، زمان انتشار و استمرار رؤیت فقط با مدرک معتبر مستقل تأیید می‌شود. "
    "در صورت غیرقانونی بودن این شرط، هیچ فروش یا الزام تبلیغاتی اجرا نمی‌شود "
    "تا قرارداد پس از بررسی حقوقی اصلاح گردد. "
    "XAUUSD تنها نماد پیشنهادی است؛ ریسک هر معامله حداکثر ۳٪ و مجموع ریسک باز "
    "حداکثر ۸٪، با رعایت حد ضرر روزانه ۴٪ و کل ۸٪، اسپرد، کارمزد و لغزش قیمت. "
    "سود بهترین روز نباید بیش از ۳۲٪ سود خالص هر مرحله باشد. "
    "پذیرش در دو مرحله به‌خودی‌خود تضمین تخصیص ۱۰۰ دلار یا حساب واقعی نیست؛ "
    "گواهی سرمایه، مجوز کتبی کارگزار، KYC، قرارداد قانونی جداگانه و تأیید انتشار لازم است. "
    "تقسیم سود خالص تحقق‌یافته پس از رفع زیان‌ها، در صورت امضای قرارداد مجاز، "
    "۷۰٪ معامله‌گر و ۳۰٪ برگزارکننده است."
)

EN = (
    "MOJ-PROP-01 prospective NONPAYABLE buyer terms, DRAFT version only: "
    "proposed entry fee 30 native TRX, with checkout disabled. "
    "Two sequential DEMO phases with net-profit goals of 9.6% and 6%, "
    "at least 50 distinct independently reconciled CLOSED positions TOTAL "
    "across BOTH phases (NOT 50 per phase), and at least SIX independently "
    "verified trading days in EACH phase, within a 28-day evaluation window. "
    "Proposed social-post condition: at least ONE qualifying original post on EITHER "
    "Instagram OR Facebook (one platform is sufficient; both are not required), continuously publicly "
    "visible for at least 28 consecutive days (672 hours). The trading evaluation "
    "28-day window and the social post 28-day hold use SEPARATE clocks; when "
    "the post is published later, final social qualification must wait for "
    "all 672 hours independently of evaluation completion. The post must "
    "transparently disclose challenge participation, make no profit promises, "
    "avoid sensitive financial data, and comply with applicable platform and "
    "financial-advertising law. Posting time, authorship and continuous visibility "
    "require independent evidence. If a mandatory post is not legally allowed, "
    "the contract remains ON HOLD; no post requirement or customer sale is imposed. "
    "XAUUSD only in the proposed real-risk stage: at most 3% single-order "
    "and 8% open aggregate nominal risk, subject to stricter 4% daily and "
    "8% total drawdown constraints, fees, full spread and slippage reserve. "
    "The most profitable day may not exceed 32% of each phase's verified net "
    "profit. Passing simulated challenges does NOT automatically fund or "
    "activate a USD 100 live account. Independent capital proof, explicit "
    "broker permissions, KYC, signed lawful terms and release authorization "
    "are mandatory. Proposed realized net-profit split after loss recovery "
    "is 70% trader / 30% organizer, only under a separate executed contract."
)


@dataclass(frozen=True)
class ProspectiveV14Review:
    sku: str
    version: str
    supersedes_unsigned_draft_version: str
    source_draft_sha256: str
    contract_candidate_sha256: str
    closed_trades_total: int
    trading_days_each_phase: int
    social_platforms: tuple[str, str]
    social_platform_operator: str
    social_posts_required: int
    public_post_hours: int
    social_post_disclosure_required: bool
    fa: str
    en: str
    legal_social_advertising_clearance: bool = False
    existing_agreements_amended: bool = False
    customer_terms_signed: bool = False
    social_proof_independently_verified: bool = False
    broker_permission_verified: bool = False
    cash_reserves_verified: bool = False
    checkout_enabled: bool = False
    enrollment_enabled: bool = False
    real_trading_enabled: bool = False
    payout_enabled: bool = False


def review_prospective_terms() -> ProspectiveV14Review:
    prior = draft_gold_terms_v13()
    if (prior.sku != "MOJ-PROP-01"
            or prior.min_closed_trades_total != MIN_VERIFIED_CLOSED_TOTAL
            or prior.min_trading_days_per_stage != MIN_TRADING_DAYS_EACH_PHASE
            or prior.evaluation_days != 28
            or prior.entry_sun != 30_000_000
            or prior.risk_per_order_pct != Decimal("3")
            or prior.open_risk_pct != Decimal("8")
            or prior.max_profitable_day_share_pct != Decimal("32")
            or prior.checkout_enabled is not False
            or prior.enrollment_created is not False
            or prior.customer_contract_signed is not False):
        raise ValueError("unexpected underlying versioned draft: independent review required")
    payload = dict(
        schema=SCHEMA, sku=prior.sku, version=VERSION,
        previous_unsigned_version=prior.contract_version,
        prior_digest=prior.digest_sha256,
        closed_trades_total=MIN_VERIFIED_CLOSED_TOTAL,
        trading_days_each_phase=MIN_TRADING_DAYS_EACH_PHASE,
        social_platforms=SOCIAL_PLATFORMS, social_operator=SOCIAL_LOGICAL_OPERATOR,
        social_posts_required=MIN_SOCIAL_POSTS,
        public_post_hours=SOCIAL_DURATION_HOURS,
        social_post_disclosure_required=True, fa=FA, en=EN,
    )
    digest = sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                               separators=(",", ":")).encode("utf-8")).hexdigest()
    return ProspectiveV14Review(
        sku=prior.sku, version=VERSION,
        supersedes_unsigned_draft_version=prior.contract_version,
        source_draft_sha256=prior.digest_sha256,
        contract_candidate_sha256=digest,
        closed_trades_total=MIN_VERIFIED_CLOSED_TOTAL,
        trading_days_each_phase=MIN_TRADING_DAYS_EACH_PHASE,
        social_platforms=SOCIAL_PLATFORMS,
        social_platform_operator=SOCIAL_LOGICAL_OPERATOR,
        social_posts_required=MIN_SOCIAL_POSTS,
        public_post_hours=SOCIAL_DURATION_HOURS,
        social_post_disclosure_required=True,
        fa=FA, en=EN,
    )
