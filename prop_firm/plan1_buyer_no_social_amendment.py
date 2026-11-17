"""MOJ-PROP-01: buyer-friendly no-social-posting amendment (17 Nov 2026).

Historical v1.2 source disclosure is immutable and remains accessible for audit.
The owner's new instruction WAIVES all buyer Instagram/Facebook posting and
submission obligations. The previous v1.2 post clause cannot be used for new
buyer terms without this visible amendment or a fully reissued agreement.
This file is an information-only source artifact, NOT signed customer terms.
"""
from dataclasses import dataclass
from hashlib import sha256
import json

from .plan1_buyer_disclosure_v12 import buyer_disclosure

SKU = "MOJ-PROP-01"
AMENDMENT_VERSION = "2026-11-17/no-social-post-waiver-v1"
HISTORICAL_TERMS_VERSION = "2026-11-15/v1.2"
STATUS = "NONPAYABLE_BUYER_AMENDMENT_REQUIRES_SIGNED_TERMS_INTEGRATION"
FA_NO_POST = (
    "اصلاحیه بدون الزام تبلیغاتی مج پراپ (۱۷ آبان ۱۴۰۵): "
    "خریدار چالش MOJ-PROP-01 موظف به انتشار، ارسال، بارگذاری یا "
    "ارائه لینک هیچ پستی در اینستاگرام یا فیس‌بوک نیست. "
    "عدم انتشار هیچ پستی باعث رد صلاحیت، عدم قبولی، محرومیت از "
    "پرداخت سود واجد شرایط یا از بین رفتن حق استرداد نمی‌شود. "
    "هرگونه فعالیت تبلیغاتی صرفاً اختیاری و با رضایت جداگانه است. "
    "استفاده از حساب شخصی مالک یا برداشت اطلاعات آن ممنوع است. "
    "این اصلاحیه تعهدات قبلی انتشار دو پست را برای خریدار حذف می‌کند، "
    "اما الزامات مستقل و قانونی احراز هویت، قرارداد، ارزیابی و "
    "تأمین واقعی حساب را حذف نمی‌کند. "
    "این متن فاکتور یا تأیید دریافت وجه یا قرارداد امضاشده نیست."
)
EN_NO_POST = (
    "MOJ PROP buyer-friendly amendment (17 November 2026): "
    "A buyer of MOJ-PROP-01 is NOT required to create, publish, submit, "
    "upload, maintain, or provide links to any Instagram or Facebook posts. "
    "Not posting cannot cause rejection, a challenge failure, loss of an "
    "otherwise eligible real funded profit share, or denial of fair refunds. "
    "Any separate promotional participation is entirely voluntary and needs "
    "separate informed consent. The owner's personal social accounts cannot "
    "be accessed, scraped, or used. This amendment waives the earlier "
    "two-post obligation for buyers without waiving independent legal KYC, "
    "signed terms, evaluation, or proof of genuine funding. "
    "This information is NOT a signed buyer contract, invoice or payment receipt."
)


@dataclass(frozen=True)
class NoBuyerSocialPostAmendment:
    sku: str
    historical_terms_version: str
    amendment_version: str
    historical_disclosure_digest_sha256: str
    fa: str
    en: str
    instagram_posts_required: int
    facebook_posts_required: int
    buyer_post_links_required: bool
    buyer_media_upload_required: bool
    posting_a_condition_of_challenge_pass: bool
    posting_a_condition_of_funded_profit: bool
    posting_a_condition_of_fair_refund: bool
    marketing_consent_inferred: bool
    personal_owner_social_use_allowed: bool
    current_signed_terms_verified_by_this_module: bool
    payable_invoice_enabled: bool
    paid_enrollment_enabled: bool
    digest_sha256: str
    status: str = STATUS


def buyer_no_social_post_amendment():
    history = buyer_disclosure()
    if (history.sku != SKU or history.contract_version != HISTORICAL_TERMS_VERSION
            or history.fee_sun != 30_000_000 or history.network != "TRON-mainnet"
            or history.two_phases_simulated is not True
            or history.invoice_issued is not False
            or history.customer_contract_signed is not False
            or len(history.digest_sha256) != 64):
        raise ValueError("historical v1.2 disclosure reference has drifted")
    payload = {
        "sku": SKU,
        "historical_terms_version": HISTORICAL_TERMS_VERSION,
        "amendment_version": AMENDMENT_VERSION,
        "historical_disclosure_digest_sha256": history.digest_sha256,
        "fa": FA_NO_POST,
        "en": EN_NO_POST,
        "instagram_posts_required": 0,
        "facebook_posts_required": 0,
        "buyer_post_links_required": False,
        "buyer_media_upload_required": False,
        "posting_a_condition_of_challenge_pass": False,
        "posting_a_condition_of_funded_profit": False,
        "posting_a_condition_of_fair_refund": False,
        "marketing_consent_inferred": False,
        "personal_owner_social_use_allowed": False,
        "current_signed_terms_verified_by_this_module": False,
        "payable_invoice_enabled": False,
        "paid_enrollment_enabled": False,
    }
    digest = sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                               separators=(",", ":"), allow_nan=False
                               ).encode("utf-8")).hexdigest()
    return NoBuyerSocialPostAmendment(**payload, digest_sha256=digest)


_HISTORICAL_POST_CLAUSE_FA = (
    "سیاست نسخه v1.2 برای کل چالش، یک پست اصیل اینستاگرام و یک پست اصیل فیس‌بوک "
    "را با افشای شفاف رابطه تبلیغاتی در نظر دارد؛ اجرای آن تابع قوانین قابل اعمال و "
    "سیاست پلتفرم است، هیچ تعریف یا نظر مثبت اجباری نیست و حساب‌های شخصی مالک "
    "برای انتشار یا داده‌برداری استفاده نمی‌شوند. پست‌ها طبق قرارداد باید ۲۸ روز "
    "پس از انتشار در دسترس باشند.\\n"
)
_HISTORICAL_POST_CLAUSE_EN = (
    "The v1.2 policy proposes ONE original Instagram and ONE original Facebook post "
    "for the entire challenge, each retained for 28 days after posting, with clear "
    "commercial-relationship disclosure and only where applicable law and platform "
    "terms permit. No forced positive endorsement; the owner's private social "
    "accounts must not be accessed, scraped or used.\\n"
)


@dataclass(frozen=True)
class CurrentPlan1BuyerCopy:
    """Fresh informational copy without obsolete mandatory-post language."""
    sku: str
    fee_sun: int
    network: str
    historical_terms_version: str
    amendment_version: str
    fa: str
    en: str
    digest_sha256: str
    instagram_posts_required: int = 0
    facebook_posts_required: int = 0
    requires_separate_buyer_contract_acceptance: bool = True
    requires_independent_kyc_and_funding: bool = True
    payment_enabled: bool = False
    invoice_enabled: bool = False
    enrollment_enabled: bool = False
    status: str = STATUS


def current_plan1_buyer_copy():
    """Build replacement FA+EN *information*, not retroactive signed buyer terms.

    Fails closed if the immutable v1.2 source language ever changes, rather than
    accidentally showing both a post obligation and its waiver.
    """
    historical = buyer_disclosure()
    waiver = buyer_no_social_post_amendment()
    if (historical.fa.count(_HISTORICAL_POST_CLAUSE_FA) != 1
            or historical.en.count(_HISTORICAL_POST_CLAUSE_EN) != 1
            or historical.digest_sha256 != waiver.historical_disclosure_digest_sha256):
        raise ValueError("historical mandatory social clause drift requires legal copy review")
    fa = historical.fa.replace(
        _HISTORICAL_POST_CLAUSE_FA, waiver.fa + "\\n", 1)
    en = historical.en.replace(
        _HISTORICAL_POST_CLAUSE_EN, waiver.en + "\\n", 1)
    if (fa == historical.fa or en == historical.en
            or "یک پست اصیل اینستاگرام" in fa
            or "ONE original Instagram and ONE original Facebook" in en
            or "NOT required" not in en or "موظف" not in fa):
        raise ValueError("buyer disclosure still contains a mandatory social clause")
    payload = {
        "sku": SKU, "fee_sun": historical.fee_sun,
        "network": historical.network,
        "historical_terms_version": historical.contract_version,
        "amendment_version": waiver.amendment_version,
        "fa": fa, "en": en,
    }
    digest = sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                               separators=(",", ":"), allow_nan=False
                               ).encode("utf-8")).hexdigest()
    return CurrentPlan1BuyerCopy(**payload, digest_sha256=digest)
