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
