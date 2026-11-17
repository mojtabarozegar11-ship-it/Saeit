"""Prospective owner-risk v1.3: bilingual MOJ-PROP-01 pre-contract review.

This NEVER amends or silently replaces an existing v1.2 agreement, enables
payments, sends orders, captures buyer data, or promises funding. Reviewer
must approve a NEW contract in the relevant jurisdiction and the buyer must
separately accept its exact digest. Current public v1.2 is unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json

from .plans import plan_for_code
from .owner_gold_risk_v13 import OWNER_GOLD_V13

SKU = "MOJ-PROP-01"
SCHEMA = "mojprop.plan1.gold-xauusd.prospective-risk.en-fa.v1.3"
NETWORK = "TRON-mainnet"
FEE_NATIVE_SUN = 30_000_000


@dataclass(frozen=True)
class ProposedBuyerRiskDisclosureV13:
    schema: str
    sku: str
    contract_version: str
    symbol: str
    native_fee_sun: int
    network: str
    risk_order_pct: str
    risk_open_pct: str
    daily_drawdown_pct: str
    total_drawdown_pct: str
    initial_capital_usd_conditional: str
    trader_profit_share_pct: str
    company_profit_share_pct: str
    fa: str
    en: str
    sha256_digest: str
    status: str = "PROPOSED_REQUIRES_SIGNED_NEW_CONTRACT"
    buyer_accepted: bool = False
    legal_approved: bool = False
    broker_symbol_verified: bool = False
    account_funding_verified: bool = False
    payment_enabled: bool = False
    invoice_issued: bool = False
    actual_order_enabled: bool = False


def proposed_disclosure_v13() -> ProposedBuyerRiskDisclosureV13:
    plan = plan_for_code(SKU)
    terms = OWNER_GOLD_V13
    # Anchor economics and immutable historical v1.2 contract separately.
    if (
        plan.code != SKU
        or plan.entry_fee_trx != Decimal("30")
        or plan.starting_capital_usd != Decimal("100")
        or plan.trader_profit_share_pct != Decimal("70")
        or plan.company_profit_share_pct != Decimal("30")
        or plan.max_risk_per_trade_pct != Decimal("0.8")
        or plan.max_open_risk_pct != Decimal("1.6")
        or terms.max_per_order_risk_pct != Decimal("3")
        or terms.max_aggregate_open_risk_pct != Decimal("8")
        or terms.max_daily_loss_pct != Decimal("4")
        or terms.max_total_loss_pct != Decimal("8")
        or terms.exact_broker_symbol != "XAUUSD"
        or terms.contract_version != "2026-11-17/v1.3"
        or terms.checkout_enabled
        or terms.real_execution_enabled
    ):
        raise ValueError("New gold terms or historical Plan 1 contract drift")
    fa = (
        "پیشنویس شرایط جدید مج پراپ (MOJ-PROP-01)، نسخه v1.3؛ مخصوص پذیرش آتی و "
        "نه اصلاح خودکار قراردادهای v1.2. این متن پیشنهاد پیش از قرارداد است؛ "
        "فروش، پرداخت و معامله حقیقی را فعال نمی‌کند.\n"
        "بازار مجاز: فقط انس جهانی طلا، نماد دقیق کارگزاری XAUUSD. "
        "ریسک برنامه‌ریزی‌شده هر معامله حداکثر ۳٪ سرمایه اولیه سطح و "
        "مجموع ریسک موقعیت‌های باز حداکثر ۸٪ است. با این وجود، سقف زیان روزانه "
        "۴٪ و سقف زیان کل ۸٪ مستقل و سخت‌گیرانه باقی می‌مانند؛ حتی ریسک ۳٪ "
        "ممکن است به‌دلیل فاصله کم تا حد افت سرمایه رد شود. اختلاف قیمت اجرا، "
        "هزینه معاملات و لغزش باید در ریسک توقف لحاظ شوند.\n"
        "قیمت پیشنهادی ارزیابی دو‌مرحله‌ای: ۳۰ واحد TRX بومی شبکه TRON "
        "Mainnet، معادل دقیق ۳۰٬۰۰۰٬۰۰۰ SUN؛ خود چالش شبیه‌سازی است. "
        "پس از قبولی، حساب حقیقی اولیه ۱۰۰ دلاری فقط در صورت احراز هویت، "
        "قانون، قرارداد کارگزار و تأمین واقعی سرمایه فراهم می‌شود. تقسیم "
        "سود واقعی واجد شرایط، ۷۰٪ معامله‌گر و ۳۰٪ شرکت است و سود تضمین‌شده نیست.\n"
        "قبل از هر خرید، قرارداد اختصاصی، شرایط استرداد وجه، صلاحیت اقامت "
        "مشتری، مجوزهای قانونی و تأیید دقیق نسخه جدید الزامی است. انتشار یا "
        "ذخیره این پیشنهاد به معنی رضایت مشتری یا دریافت وجه نیست."
    )
    en = (
        "PROPOSED MOJ PROP (MOJ-PROP-01) owner risk amendment v1.3, for "
        "future explicit buyer acceptance only. Historical v1.2 customer "
        "contracts are not automatically amended. This is a pre-contract "
        "information proposal; checkout and live order execution remain OFF.\n"
        "Permitted instrument: spot gold XAUUSD, with the exact broker symbol "
        "independently verified. The proposed maximum planned risk per "
        "trade is 3% of original tier capital; aggregate planned open "
        "stop-loss risk is at most 8%. However, the independent 4% daily "
        "and 8% total drawdown floors always override these static ceilings: "
        "even a 3% trade is rejected if its stop-out could exhaust drawdown "
        "headroom. Include slippage, fees and other execution losses.\n"
        "Proposed two-stage evaluation fee is 30 native TRX on TRON Mainnet "
        "(30,000,000 SUN); both challenge stages are simulated. An initial "
        "USD 100 real funded account after passing is CONDITIONAL on "
        "legal/KYC approval, documented actual capital and lawful broker "
        "availability. Eligible realized profits would be split 70% trader "
        "and 30% firm; returns and allocation are never guaranteed.\n"
        "Buyer-specific legal/jurisdiction checks, refund terms, broker "
        "documents and explicit acceptance of the exact revised contract "
        "must occur BEFORE any payable order. This draft issues no wallet, "
        "invoice, payment request or buyer enrollment."
    )
    payload = {
        "schema": SCHEMA,
        "sku": SKU,
        "contract_version": terms.contract_version,
        "symbol": terms.exact_broker_symbol,
        "native_fee_sun": FEE_NATIVE_SUN,
        "network": NETWORK,
        "risk_order_pct": str(terms.max_per_order_risk_pct),
        "risk_open_pct": str(terms.max_aggregate_open_risk_pct),
        "daily_drawdown_pct": str(terms.max_daily_loss_pct),
        "total_drawdown_pct": str(terms.max_total_loss_pct),
        "initial_capital_usd_conditional": str(plan.starting_capital_usd),
        "trader_profit_share_pct": str(plan.trader_profit_share_pct),
        "company_profit_share_pct": str(plan.company_profit_share_pct),
        "fa": fa,
        "en": en,
    }
    fingerprint = sha256(json.dumps(
        payload, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()
    result = ProposedBuyerRiskDisclosureV13(
        **payload, sha256_digest=fingerprint,
    )
    assert not any((
        result.buyer_accepted, result.legal_approved,
        result.broker_symbol_verified, result.account_funding_verified,
        result.payment_enabled, result.invoice_issued,
        result.actual_order_enabled,
    ))
    return result
