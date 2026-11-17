"""Current Plan1 FA/EN buyer copy for EXISTING owner-held LiteFinance real account.

Historical v1.2 packet and the earlier no-social/no-demo-live amendment retain
their original digests. The latest, dated amendment replaces obsolete wording
which promised creation of a buyer real account, not the historic audit text.
Any future buyer acceptance must bind THIS fresh digest, not older copy alone.
"""
from dataclasses import dataclass
from hashlib import sha256
import json

from .plan1_buyer_no_social_amendment import (
    current_plan1_buyer_copy, DEMO_TO_REAL_FA, DEMO_TO_REAL_EN,
)
from .plan1_owner_held_litefinance_policy import (
    owner_held_real_account_policy, VERSION,
)

OLD_FA = (
    "بعد از قبولی در هر دو مرحله، حساب حقیقی اولیه با ۱۰۰ دلار سرمایه فقط در صورت "
    "احراز شرایط قرارداد، هویت، تأمین و تخصیص واقعی سرمایه و امکان اجرای کارگزار ایجاد می‌شود. "
    "وجود ۱۴ سطح سرمایه تا سقف ۱۰۰٬۰۰۰ دلار، تضمین ارتقا یا تأمین مالی نیست. "
    "تقسیم ۷۰٪ معامله‌گر و ۳۰٪ شرکت فقط برای سود واقعی واجد شرایطِ حساب تأمین‌شده است.\n"
)
OLD_EN = (
    "After BOTH stages are passed, a real USD 100 initial funded account is CONDITIONAL "
    "on documented eligibility and KYC, genuine available capital allocation, and "
    "lawful broker feasibility. A 14-level ladder to USD 100,000 is not a guarantee "
    "of future funding. A 70% trader / 30% firm split concerns only eligible realized "
    "profit under an actually funded and agreed account.\n"
)

@dataclass(frozen=True)
class CurrentOwnerAccountBuyerCopy:
    sku: str
    historical_terms_version: str
    prior_no_social_demo_copy_digest_sha256: str
    owner_account_amendment_version: str
    owner_account_amendment_sha256: str
    fa: str
    en: str
    digest_sha256: str
    demo_stages: int = 2
    buyer_principal_transfer_enabled: bool = False
    new_buyer_broker_account_promised: bool = False
    live_owner_account_use_authorized_by_this_code: bool = False
    customer_acceptance_verified_by_this_code: bool = False
    payment_enabled: bool = False
    invoice_enabled: bool = False
    crypto_payout_enabled: bool = False
    status: str = "NEW_BUYER_COPY_NEEDS_NEW_SIGNED_TERMS_AND_BROKER_AUTHORITY"


def current_owner_account_buyer_copy():
    previous = current_plan1_buyer_copy()
    policy = owner_held_real_account_policy()
    if (previous.sku != "MOJ-PROP-01" or previous.fee_sun != 30_000_000
            or previous.network != "TRON-mainnet"
            or policy.sku != previous.sku or len(previous.digest_sha256) != 64
            or policy.buyer_owns_or_receives_principal is not False
            or policy.broker_directly_pays_buyer_wallet is not False
            or previous.invoice_enabled is not False):
        raise ValueError("prior buyer disclosure or owner policy differs from canonical terms")
    if (previous.fa.count(OLD_FA) != 1 or previous.en.count(OLD_EN) != 1
            or previous.fa.count(DEMO_TO_REAL_FA) != 1
            or previous.en.count(DEMO_TO_REAL_EN) != 1):
        raise ValueError("obsolete new-customer real-account paragraph changed")
    fa = previous.fa.replace(OLD_FA, "", 1).replace(DEMO_TO_REAL_FA, policy.fa, 1)
    en = previous.en.replace(OLD_EN, "", 1).replace(DEMO_TO_REAL_EN, policy.en, 1)
    if (OLD_FA in fa or OLD_EN in en
            or DEMO_TO_REAL_FA in fa or DEMO_TO_REAL_EN in en
            or "owner's credentials" not in en
            or "NO trading principal" not in en
            or "NOT a direct LiteFinance withdrawal" not in en
            or "۱۳ سطح" in fa
            or "۱۴ سطح" not in fa
            or "30 native TRX" not in en
            or "BOTH evaluation stages are simulated" not in en):
        raise ValueError("buyer copy no longer safely discloses the exact offer")
    data = {
        "sku": previous.sku,
        "historical_terms_version": previous.historical_terms_version,
        "prior_no_social_demo_copy_digest_sha256": previous.digest_sha256,
        "owner_account_amendment_version": VERSION,
        "owner_account_amendment_sha256": policy.digest_sha256,
        "fa": fa, "en": en,
    }
    digest = sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False, allow_nan=False
                               ).encode("utf-8")).hexdigest()
    return CurrentOwnerAccountBuyerCopy(**data, digest_sha256=digest)
