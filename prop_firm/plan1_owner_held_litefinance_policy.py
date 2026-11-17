"""MOJ-PROP-01 owner-controlled EXISTING LiteFinance account, policy-only.

This is an owner DECLARATION, not independent broker approval. There is no
new funded customer trading account, principal transfer or broker login.
A post-demo-pass participant can propose trades ONLY through a distinct
broker-authorized, audited access mechanism. Never give the buyer the owner's
password, 2FA, withdrawal access or custody of the trading principal.

LiteFinance's AML withdrawal-to-original-source restriction applies to the
broker withdrawal; any later trader-profit crypto payout is a separate lawful
payment from the authorized business treasury, not a broker-to-buyer transfer.
"""
from dataclasses import dataclass
from hashlib import sha256
import json

from .order_readiness import SKU, TERMS_VERSION

VERSION = "2026-11-17/owner-controlled-existing-litefinance-account-v1"
FA = (
    "مج پراپ — اصلاحیه حساب واقعی: هر دو مرحله چالش با حساب دمو انجام می‌شود. "
    "پس از قبولی مستقل در هر دو مرحله، معامله‌گر فقط در صورت مجوز رسمی کارگزار و "
    "قرارداد قانونی می‌تواند از روش دسترسی معاملاتی مجاز و قابل حسابرسی در "
    "حساب واقعی موجود و احرازشده لایت‌فایننس تحت کنترل صاحب حساب استفاده کند. "
    "هیچ سرمایه‌ای، از جمله ۱۰۰ دلار اولیه، به حساب یا کیف پول خریدار واریز "
    "نمی‌شود و حساب واقعی جدیدی به نام خریدار وعده داده نمی‌شود. "
    "رقم ۱۰۰ دلار صرفاً سرمایه/حد ریسک تخصیصی برنامه است و وجود و قابلیت تخصیص "
    "آن به شواهد مستقل سرمایه و مجوز کارگزار وابسته است. "
    "خریدار نام کاربری، گذرواژه، کد دومرحله‌ای یا اختیار برداشت حساب مالک را "
    "دریافت نمی‌کند. در پایان هر دوره قراردادی، صرفاً سود خالص تحقق‌یافته "
    "و قابل انتساب به معاملات همان معامله‌گر، پس از بررسی زیان انتقالی و "
    "تسویه دفتر معاملات، به نسبت ۷۰ درصد معامله‌گر و ۳۰ درصد برگزارکننده "
    "تقسیم می‌شود. کارمزد واقعی و از پیش اعلام‌شده انتقال رمزارزی فقط یک‌بار "
    "از سهم خریدار کسر می‌شود؛ در نبود سود واجد شرایط، پرداختی وجود ندارد. "
    "پرداخت احتمالی از مسیر خزانه قانونی برگزارکننده و کیف پول تأییدشده "
    "خریدار است، نه برداشت مستقیم LiteFinance به کیف پول شخص ثالث. "
    "پرداخت منوط به رعایت احراز هویت، تحریم‌ها، مجوزها و مقررات انتقال "
    "رمزارز، مدارک واقعی کارگزار و تأیید نهایی دوره است. "
    "مدت دوره، تعریف سود خالص، هزینه‌های مجاز، اختلافات و استرداد باید "
    "پیش از خرید در قرارداد مشخص و جداگانه پذیرفته شوند. "
    "هیچ سود یا دسترسی معاملاتی تضمین نمی‌شود."
)
EN = (
    "MOJ PROP — existing real-account amendment: BOTH evaluation stages use "
    "DEMO accounts. ONLY after independently passing both stages, and only "
    "where explicitly permitted by the broker and applicable law, may a trader "
    "submit orders through a broker-authorized, audited and individually "
    "attributed mechanism on an EXISTING identity-verified LiteFinance real "
    "account controlled by its lawful holder. NO trading principal, including "
    "the nominal USD 100 initial risk allocation, is deposited into a buyer's "
    "bank, wallet or brokerage account; no new real account in the buyer's name "
    "is promised. The USD 100 starting allocation is an internal, separately "
    "funding-proven risk/capital limit, not a payout or an independently "
    "verified balance. A trader receives NO owner's credentials, 2FA, "
    "withdrawal rights or custody of the trading capital. At the end of each "
    "contractually defined settlement period, independently reconciled, "
    "attributable REALIZED net trading profit, after valid loss carryforward "
    "and disclosed trading costs, is split 70% trader / 30% organizer. Only "
    "the documented, pre-disclosed actual crypto transfer fee may be deducted "
    "once from the trader's payout; no eligible profit means no payout. "
    "Broker withdrawals must respect the holder's original funding/withdrawal "
    "method rules. Any eventual crypto profit payment is a separate legal "
    "business-treasury transfer to the verified beneficiary wallet, NOT a "
    "direct LiteFinance withdrawal to a third-party buyer. Trading authority "
    "and payouts require broker approval, legal/KYC/sanctions and crypto "
    "beneficiary checks, independent profit reports and authorized treasury "
    "settlement. Settlement period, fee calculation, disputes, refunds and "
    "costs must be specified and independently accepted before a purchase. "
    "No trading access, income or profit is guaranteed."
)

REVIEW_GATES = (
    "both_demo_phases_independently_passed",
    "owner_broker_account_identity_verified_by_broker",
    "owner_account_control_and_custody_independently_confirmed",
    "broker_explicitly_authorized_delegated_order_mechanism",
    "buyer_specific_order_attribution_and_execution_audit",
    "broker_risk_limits_and_loss_controls_approved",
    "genuine_available_capital_and_usd100_risk_allocation_proven",
    "buyer_identity_and_country_eligibility_verified_for_real_trading",
    "real_trader_agreement_signed_under_current_amendments",
    "no_owner_password_2fa_or_withdrawal_access_to_trader",
    "broker_withdrawal_to_own_funding_destination_permitted",
    "separate_crypto_treasury_payout_legally_permitted",
)

@dataclass(frozen=True)
class OwnerHeldBrokerPolicy:
    sku: str
    historic_contract_version: str
    amendment_version: str
    fa: str
    en: str
    digest_sha256: str
    broker: str = "LiteFinance"
    buyer_owns_or_receives_principal: bool = False
    buyer_gets_account_password_or_2fa: bool = False
    buyer_gets_broker_withdrawal_authority: bool = False
    broker_directly_pays_buyer_wallet: bool = False
    live_trading_only_after_both_demo_passes: bool = True
    existing_broker_account_owner_declared: bool = True
    broker_delegation_independently_authorized: bool = False
    broker_balance_independently_verified: bool = False
    crypto_transfer_from_separate_treasury_only: bool = True
    payout_without_realized_eligible_profit: bool = False
    marketing_or_social_post_required: bool = False
    buyer_contract_signed_by_this_code: bool = False
    invoice_issued_by_this_code: bool = False
    trading_enabled_by_this_code: bool = False
    payout_enabled_by_this_code: bool = False

def owner_held_real_account_policy():
    payload = {
        "sku":SKU,"historic_contract_version":TERMS_VERSION,
        "amendment_version":VERSION,"fa":FA,"en":EN,
    }
    digest=sha256(json.dumps(
        payload,sort_keys=True,separators=(",",":"),
        ensure_ascii=False,allow_nan=False).encode("utf-8")).hexdigest()
    return OwnerHeldBrokerPolicy(**payload,digest_sha256=digest)

@dataclass(frozen=True)
class AuthorizedTradingMechanismReview:
    eligible_for_independent_broker_review: bool
    missing: tuple[str,...]
    signed_terms_ready_by_this_code: bool = False
    broker_permission_proved_by_this_code: bool = False
    trading_enabled: bool = False
    buyer_receives_principal: bool = False
    payout_enabled: bool = False

def review_existing_broker_trading_mechanism(*, trusted_evidence):
    """Require independent gate attestations; all True still only a REVIEW.

    Browser-provided flags, broker login access and owner declarations alone
    are NOT proof of broker permission or merchant financial legality.
    """
    if type(trusted_evidence) is not dict or set(trusted_evidence) != set(REVIEW_GATES):
        raise ValueError("exact trusted broker-access review evidence required")
    missing=tuple(k for k in REVIEW_GATES if trusted_evidence[k] is not True)
    return AuthorizedTradingMechanismReview(
        eligible_for_independent_broker_review=not missing,missing=missing)
