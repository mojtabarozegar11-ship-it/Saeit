"""Fail-closed public lead intake for Moj Prop.

This module is deliberately non-financial: it prepares a validated applicant
record for persistence, but never creates an invoice, verifies KYC, enables
checkout, places orders, or authorizes a payout.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Final

CONSENT_VERSION: Final = "2026-11-15/v1"
RISK_DISCLOSURE_VERSION: Final = "2026-11-15/v1"
SUPPORTED_LANGUAGES: Final = frozenset({"fa", "en"})
SUPPORTED_SOURCES: Final = frozenset(
    {"moj_prop_public_page", "mojtaba.bot.ai", "manual_referral"}
)
_EMAIL_RE: Final = re.compile(
    r"(?=.{1,254}$)[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$",
    re.ASCII,
)


@dataclass(frozen=True)
class ApplicantIntakeDecision:
    accepted: bool
    normalized_email: str | None
    preferred_language: str | None
    jurisdiction: str | None
    source: str | None
    blockers: tuple[str, ...]
    persistence_allowed: bool
    checkout_enabled: bool = False
    trading_enabled: bool = False
    payout_enabled: bool = False


def _text(value: object, field: str, *, maximum: int) -> str:
    if type(value) is not str:
        raise ValueError(f"{field} must be text")
    value = value.strip()
    if not value or len(value) > maximum or any(ord(ch) < 32 for ch in value):
        raise ValueError(f"{field} is malformed")
    return value


def normalize_email(value: object) -> str:
    email = _text(value, "email", maximum=254).lower()
    if _EMAIL_RE.fullmatch(email) is None:
        raise ValueError("email is malformed")
    return email


def screen_applicant(
    *,
    email: object,
    preferred_language: object = "fa",
    jurisdiction: object,
    source: object,
    consent_version: object,
    risk_disclosure_version: object,
    risk_acknowledged: object,
) -> ApplicantIntakeDecision:
    """Validate a lead without treating it as a buyer or eligible trader."""
    blockers: list[str] = []
    normalized_email: str | None = None
    language: str | None = None
    jurisdiction_text: str | None = None
    source_text: str | None = None

    try:
        normalized_email = normalize_email(email)
    except ValueError:
        blockers.append("invalid_email")

    try:
        language = _text(preferred_language, "preferred_language", maximum=8).lower()
        if language not in SUPPORTED_LANGUAGES:
            blockers.append("unsupported_language")
    except ValueError:
        blockers.append("invalid_language")

    try:
        jurisdiction_text = _text(jurisdiction, "jurisdiction", maximum=64)
    except ValueError:
        blockers.append("invalid_jurisdiction")

    try:
        source_text = _text(source, "source", maximum=64)
        if source_text not in SUPPORTED_SOURCES:
            blockers.append("unsupported_source")
    except ValueError:
        blockers.append("invalid_source")

    if consent_version != CONSENT_VERSION:
        blockers.append("consent_version_required")
    if risk_disclosure_version != RISK_DISCLOSURE_VERSION:
        blockers.append("risk_disclosure_version_required")
    if risk_acknowledged is not True:
        blockers.append("risk_disclosure_not_acknowledged")

    accepted = not blockers
    return ApplicantIntakeDecision(
        accepted=accepted,
        normalized_email=normalized_email if accepted else None,
        preferred_language=language if accepted else None,
        jurisdiction=jurisdiction_text if accepted else None,
        source=source_text if accepted else None,
        blockers=tuple(dict.fromkeys(blockers)),
        persistence_allowed=accepted,
    )


def model_defaults(decision: ApplicantIntakeDecision) -> dict[str, str]:
    """Return safe fields for PropApplicant after server-side authorization."""
    if decision.accepted is not True or decision.persistence_allowed is not True:
        raise ValueError("only an accepted lead may be persisted")
    assert decision.normalized_email is not None
    assert decision.preferred_language is not None
    assert decision.jurisdiction is not None
    assert decision.source is not None
    return {
        "email": decision.normalized_email,
        "preferred_language": decision.preferred_language,
        "jurisdiction": decision.jurisdiction,
        "source": decision.source,
        "consent_version": CONSENT_VERSION,
        "risk_disclosure_version": RISK_DISCLOSURE_VERSION,
        "status": "new",
    }


def public_result(decision: ApplicantIntakeDecision) -> dict[str, object]:
    """Build a response that never echoes contact data or grants access."""
    return {
        "accepted": decision.accepted,
        "blockers": list(decision.blockers),
        "next_step": "owner_review_pending" if decision.accepted else "correct_input",
        "checkout_enabled": False,
        "trading_enabled": False,
        "payout_enabled": False,
    }
