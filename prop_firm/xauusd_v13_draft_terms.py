"""MOJ-PROP-01 v1.3 XAUUSD: deterministic NON-PAYABLE proposal fingerprint.

This is not an executed customer agreement and does not amend v1.2. The
historical conflicting pre-purchase text still requires independent legal
reconciliation before any customer-facing use.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json

from .plans import plan_for_code
from .rules import POLICY
from .order_readiness import TERMS_VERSION, PREPURCHASE_DISCLOSURES
from .plan1_buyer_no_social_amendment import buyer_no_social_post_amendment
from .xauusd_v13_preflight import DRAFT_CONTRACT_VERSION

SKU = "MOJ-PROP-01"
NETWORK = "TRON-mainnet"
ENTRY_SUN = 30_000_000
TOTAL_CLOSED_TRADES = 50
DAYS_PER_PHASE = 6
RISK_PER_ORDER_PCT = Decimal("3")
OPEN_RISK_PCT = Decimal("8")
MAX_BEST_DAY_SHARE_PCT = Decimal("32")
CANDIDATE_SCHEMA = "mojprop.plan1.xauusd.v13.review-only.fa-en.1"

FA = (
    "پیش‌نویس غیرقابل پرداخت MOJ-PROP-01؛ بهای پیشنهادی ۳۰ TRX بومی شبکه ترون. "
    "دو مرحله ارزیابی کاملاً شبیه‌سازی‌شده است. هدف مرحله اول ۹٫۶٪ و مرحله دوم ۶٪؛ "
    "حداقل ۵۰ معامله بسته‌شده و مستقل تأییدشده در مجموع دو مرحله و حداقل ۶ روز "
    "معاملاتی در هر مرحله، در بازه ۲۸ روزه؛ سود بهترین روز نباید بیش از "
    "۳۲٪ سود خالص تأییدشده هر مرحله باشد. فقط XAUUSD. ریسک هر معامله حداکثر "
    "۳٪ و مجموع ریسک باز حداکثر ۸٪ سرمایه مبناست؛ سقف افت روزانه ۴٪ و کل ۸٪ "
    "همواره مقدم است. کارمزد، اسپرد، لغزش و خطر شکاف قیمت نیز لحاظ می‌شود. "
    "الزام به انتشار پست در اینستاگرام یا فیس‌بوک وجود ندارد. تخصیص ریسک اولیه "
    "۱۰۰ دلار در حساب واقعی متعلق به برگزارکننده پس از قبولی دو مرحله، "
    "مشروط به احراز مستقل سرمایه، اجازه کارگزار، هویت، قرارداد و مجوز قانونی است. "
    "تقسیم سود تحقق‌یافته خالص پس از زیان‌های قبلی: ۷۰٪ معامله‌گر و ۳۰٪ برگزارکننده. "
    "این متن قرارداد امضاشده، فاکتور، مجوز معامله یا وعده حساب قطعی نیست."
)

EN = (
    "NONPAYABLE draft for MOJ-PROP-01; proposed price 30 native TRX. "
    "Both evaluation phases are DEMO/simulated. The first-phase net profit "
    "target is 9.6% and the second-phase target is 6%; at least 50 independently "
    "verified CLOSED positions TOTAL across both phases and at least six verified "
    "trading days in EACH phase within a 28-day evaluation window. The best "
    "profitable day must not exceed 32% of independently verified net profit "
    "of the relevant phase. XAUUSD only. "
    "Nominal single-order stop risk is at most 3% and total open stop risk is at most "
    "8% of starting tier capital; binding 4% daily and 8% total drawdown floors "
    "take priority. Fees, full spread and slippage reserve are included, with "
    "additional gap risk acknowledged. No Instagram or Facebook posting or links "
    "are required. A conditional initial USD 100 risk allocation on the organizer's "
    "existing REAL broker account follows TWO verified DEMO passes only after "
    "independent funding evidence, broker authorization, KYC, legal clearance "
    "and a separate signed contract. Independently reconciled realized net "
    "profit, after prior loss recovery, is allocated 70% to trader and 30% "
    "to organizer. No account, invoice, payment, order or payout is granted "
    "by this draft."
)


@dataclass(frozen=True)
class DraftV13GoldTerms:
    schema: str
    sku: str
    contract_version: str
    previous_contract_version: str
    network: str
    entry_sun: int
    initial_real_allocation_usd: Decimal
    stage_one_profit_target_pct: Decimal
    stage_two_profit_target_pct: Decimal
    min_closed_trades_total: int
    min_trading_days_per_stage: int
    evaluation_days: int
    instrument: str
    risk_per_order_pct: Decimal
    open_risk_pct: Decimal
    max_profitable_day_share_pct: Decimal
    social_waiver_digest_sha256: str
    daily_drawdown_pct: Decimal
    total_drawdown_pct: Decimal
    trader_share_pct: Decimal
    organizer_share_pct: Decimal
    instagram_posts_required: int
    facebook_posts_required: int
    fa: str
    en: str
    digest_sha256: str
    historical_terms_conflict_open: bool = True
    customer_contract_signed: bool = False
    independently_financed_account_verified: bool = False
    broker_live_trading_approved: bool = False
    checkout_enabled: bool = False
    invoice_created: bool = False
    enrollment_created: bool = False
    order_execution_enabled: bool = False
    payout_enabled: bool = False


def draft_gold_terms_v13() -> DraftV13GoldTerms:
    """Source-derived immutable preview, **never** sale authority."""
    p = plan_for_code(SKU)
    waiver = buyer_no_social_post_amendment()
    if (POLICY.version != TERMS_VERSION or
            TERMS_VERSION != "2026-11-15/v1.2" or
            POLICY.entry_trx != Decimal("30") or
            POLICY.phase_one_goal_pct != Decimal("9.6") or
            POLICY.phase_two_goal_pct != Decimal("6") or
            POLICY.min_closed_trades_per_challenge != TOTAL_CLOSED_TRADES or
            POLICY.min_challenge_days != DAYS_PER_PHASE or
            POLICY.completion_deadline_days != 28 or
            POLICY.max_daily_loss_pct != Decimal("4") or
            POLICY.best_day_share_pct != MAX_BEST_DAY_SHARE_PCT or
            p.max_consistency_pct != MAX_BEST_DAY_SHARE_PCT or
            POLICY.max_total_loss_pct != Decimal("8") or
            POLICY.trader_profit_share_pct != Decimal("70") or
            POLICY.company_profit_share_pct != Decimal("30") or
            POLICY.real_orders_enabled is not False or
            POLICY.trx_checkout_enabled is not False or
            p.starting_capital_usd != Decimal("100") or
            p.entry_fee_trx != Decimal("30") or
            p.checkout_enabled is not False or
            p.account_activation_enabled is not False):
        raise ValueError("canonical Plan1 v1.2 financial sources drift; review required")
    if (waiver.instagram_posts_required != 0 or
            waiver.facebook_posts_required != 0 or
            waiver.posting_a_condition_of_challenge_pass is not False or
            waiver.posting_a_condition_of_funded_profit is not False):
        raise ValueError("mandatory social-post waiver is not preserved")
    old_conflict = any(
        "50 independently verified closed positions in EACH" in x
        for x in PREPURCHASE_DISCLOSURES
    )
    if not old_conflict:
        # The *existing* pre-purchase source has changed. Do not infer that a
        # public buyer contract is automatically consistent or approved.
        raise ValueError("legacy pre-purchase copy changed; re-audit required")

    values = dict(
        schema=CANDIDATE_SCHEMA,
        sku=SKU, contract_version=DRAFT_CONTRACT_VERSION,
        previous_contract_version=TERMS_VERSION,
        network=NETWORK, entry_sun=ENTRY_SUN,
        initial_real_allocation_usd=Decimal("100"),
        stage_one_profit_target_pct=POLICY.phase_one_goal_pct,
        stage_two_profit_target_pct=POLICY.phase_two_goal_pct,
        min_closed_trades_total=TOTAL_CLOSED_TRADES,
        min_trading_days_per_stage=DAYS_PER_PHASE,
        evaluation_days=POLICY.completion_deadline_days,
        instrument="XAUUSD",
        risk_per_order_pct=RISK_PER_ORDER_PCT,
        open_risk_pct=OPEN_RISK_PCT,
        max_profitable_day_share_pct=MAX_BEST_DAY_SHARE_PCT,
        social_waiver_digest_sha256=waiver.digest_sha256,
        daily_drawdown_pct=POLICY.max_daily_loss_pct,
        total_drawdown_pct=POLICY.max_total_loss_pct,
        trader_share_pct=POLICY.trader_profit_share_pct,
        organizer_share_pct=POLICY.company_profit_share_pct,
        instagram_posts_required=0, facebook_posts_required=0,
        fa=FA, en=EN,
    )
    encoded = json.dumps(
        {k: str(v) if isinstance(v, Decimal) else v for k, v in values.items()},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return DraftV13GoldTerms(**values, digest_sha256=sha256(encoded).hexdigest())
