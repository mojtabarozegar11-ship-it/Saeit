"""Opt-in paid Starter30 buyer journal portal; fail-closed until owner release.

No real brokerage execution, prop qualification or performance payout. User
reports are explicitly educational, not proofs for payment obligations.
Transactions, models, mail and sessions are strictly scoped to this product.
"""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
import hmac
from smtplib import SMTPException
from html import escape
import json
import re
import secrets
import uuid

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail
from django.db import DatabaseError, transaction
from django.db.models import Max
from django.http import Http404, HttpResponse
from django.middleware.csrf import get_token, rotate_token
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from config.mojprop_db_router import MOJPROP_DB_ALIAS
from prop_firm.models import (
    PropSimulationAccount,
    PropSimulationEvent,
    PropSimulationIdentity,
    PropSimulationLoginChallenge,
)
from prop_firm.simulation_identity_adapter import (
    IdentityAdapterClosed,
    _identity_keys,
    consume_login_challenge,
    issue_login_challenge,
    normalize_email,
    settled_accounts,
)
from prop_firm.starter30_live import release_is_open
from scripts.mojprop_starter30 import assess_journal, InvalidJournal
from scripts.mojprop_starter30_journal_csv import MAX_BYTES, parse_journal_csv
from scripts.mojprop_starter30_scorecard import render_private_scorecard

ROOT = "/mojprop-buyer-portal/"
_SESSION_ID = "mojprop_buyer_identity_v1"
_SESSION_CHALLENGE = "mojprop_buyer_challenge_v1"
_SESSION_THROTTLE = "mojprop_buyer_request_epoch_v1"
_JOURNAL_SOURCE = "buyer_educational_journal_v1"
_CASE = re.compile(r"MPS30-[A-F0-9]{20}\Z")
_REQUIRED_FLAGS = (
    "MPW_MOJPROP_BUYER_PORTAL_APPROVED",
    "MPW_MOJPROP_BUYER_TRANSACTIONAL_EMAIL_APPROVED",
    "MPW_MOJPROP_BUYER_SHARED_RATE_LIMIT_VERIFIED",
    "MPW_MOJPROP_BUYER_DELIVERY_RECOVERY_VERIFIED",
)


def _require_authorized_release() -> None:
    """No public service or customer email from a source merge alone."""
    if (
        release_is_open() is not True
        or not all(getattr(settings, flag, False) is True for flag in _REQUIRED_FLAGS)
        or getattr(settings, "SESSION_COOKIE_SECURE", False) is not True
        or getattr(settings, "CSRF_COOKIE_SECURE", False) is not True
    ):
        raise Http404


def _secured(response: HttpResponse) -> HttpResponse:
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Pragma"] = "no-cache"
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response["Referrer-Policy"] = "no-referrer"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Frame-Options"] = "DENY"
    response["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
        "base-uri 'none'; frame-ancestors 'none'"
    )
    return response


def _page(request, title: str, content: str, *, status: int = 200) -> HttpResponse:
    csrf = escape(get_token(request), quote=True)
    # User-controlled fields must be HTML escaped by each caller. No JS or
    # third-party images/scripts are allowed on the private account surface.
    body = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta name='robots' content='noindex,nofollow,noarchive'>"
        f"<title>{escape(title)} | Moj Prop private learning</title>"
        "<style>body{font:16px/1.65 system-ui;background:#09121c;color:#f5f1e5;"
        "max-width:800px;margin:3rem auto;padding:0 1.2rem}main{background:#152233;"
        "padding:2rem;border:1px solid #455465;border-radius:18px}"
        "label{display:block;margin:1rem 0}input{max-width:100%;padding:.75rem}"
        "input[type=email],input[type=text],input[type=password]{width:100%;box-sizing:border-box}"
        "button{background:#e8c277;color:#121923;border:0;border-radius:18px;"
        "padding:.75rem 1.25rem;cursor:pointer}a{color:#f3ce82}"
        ".note{color:#c4d1db}.error{color:#ffc6aa}</style></head>"
        "<body><main><p><a href='/moj-prop/starter-30-trx/'>Starter30 rules and offer</a></p>"
        f"<h1>{escape(title)}</h1>"
        + content
        + f"<p class='note'>Simulated learning only. No real broker account, customer "
        "investment deposit, withdrawal of virtual capital, or verified payout "
        "qualification follows from a self-reported journal.</p>"
        "<p><a href='/moj-prop/contact/'>Official customer support</a></p>"
        "</main></body></html>"
    )
    return _secured(HttpResponse(body, status=status))


def _csrf_field(request) -> str:
    return (
        "<input type='hidden' name='csrfmiddlewaretoken' value='"
        + escape(get_token(request), quote=True) + "'>"
    )


def _login_page(request, *, note: str = "") -> HttpResponse:
    text = (
        "<p>Access is available only to customers whose 30 native TRX Starter30 "
        "invoice was independently verified and whose simulation account was activated. "
        "Enter the same email used at checkout to request a one-time login code. "
        "Never send a private key, wallet seed or identification scan.</p>"
        f"<form method='post' action='{ROOT}'>" + _csrf_field(request)
        + "<input type='hidden' name='action' value='request'>"
        "<label>Email address<input type='email' name='email' required autocomplete='email'"
        " maxlength='254'></label><button type='submit'>Request one-time code</button></form>"
    )
    if note:
        text = f"<p class='note'>{escape(note)}</p>" + text
    if request.session.get(_SESSION_CHALLENGE):
        text += (
            f"<form method='post' action='{ROOT}'>" + _csrf_field(request)
            + "<input type='hidden' name='action' value='verify'>"
            "<label>One-time code from email<input type='password' name='code' "
            "required autocomplete='one-time-code' maxlength='128'></label>"
            "<button type='submit'>Open my private learning account</button></form>"
        )
    return _page(request, "Secure Starter30 sign-in", text)


def _request_code(request) -> HttpResponse:
    """Uniform answer prevents account enumeration; buyer-initiated mail only."""
    message = (
        "If a verified Starter30 account exists for that email, a short-lived "
        "code has been sent. Check spam and enter the code in this browser."
    )
    # Always provide a verification form, including for unknown emails, without
    # exposing whether the submitted address had an actual paid account.
    now = timezone.now()
    last = request.session.get(_SESSION_THROTTLE, 0)
    if type(last) is int and now.timestamp() - last < 60:
        # Preserve a legitimate code issued moments ago on accidental retries.
        if not request.session.get(_SESSION_CHALLENGE):
            request.session[_SESSION_CHALLENGE] = secrets.token_urlsafe(24)
        return _login_page(request, note=message)
    request.session[_SESSION_CHALLENGE] = secrets.token_urlsafe(24)
    request.session[_SESSION_THROTTLE] = int(now.timestamp())

    try:
        normalized = normalize_email(request.POST.get("email", ""))
        subject, digest = _identity_keys(normalized)
        identity = (
            PropSimulationIdentity.objects.using(MOJPROP_DB_ALIAS)
            .filter(
                provider="email",
                subject_key=subject,
                email_digest=digest,
                status=PropSimulationIdentity.Status.ACTIVE,
            )
            .first()
        )
        if identity is not None and settled_accounts(identity.pk):
            # Database row lock prevents parallel code requests for an account
            # from defeating the per-identity rolling 15-minute issuance limit.
            with transaction.atomic(using=MOJPROP_DB_ALIAS):
                row = (
                    PropSimulationIdentity.objects.using(MOJPROP_DB_ALIAS)
                    .select_for_update().get(pk=identity.pk)
                )
                since = now - timedelta(minutes=15)
                recent = (
                    PropSimulationLoginChallenge.objects.using(MOJPROP_DB_ALIAS)
                    .filter(
                        identity_id=row.pk,
                        purpose=PropSimulationLoginChallenge.Purpose.LOGIN,
                        created_at__gte=since,
                    ).count()
                )
                if recent >= 3:
                    return _login_page(request, note=message)
                challenge = issue_login_challenge(row.pk)
            # Never disclose a login code in the HTTP response. Transactional
            # delivery occurs ONLY after all independent owner flags pass.
            sent = send_mail(
                subject="Your requested Moj Prop Starter30 access code",
                message=(
                    "A login was requested for your simulated educational account.\n"
                    f"One-time code: {challenge.code}\n"
                    f"Valid until: {challenge.expires_at.isoformat()}\n"
                    f"Open https://mojplaywin.com{ROOT} in the SAME browser "
                    "and enter the code. If you did not request this, ignore it.\n"
                    "This code cannot initiate a payment, withdrawal, trade or payout."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[normalized],
                fail_silently=False,
            )
            if sent == 1:
                request.session[_SESSION_CHALLENGE] = challenge.challenge_ref
    except (IdentityAdapterClosed, ObjectDoesNotExist, DatabaseError,
            SMTPException, OSError, ValueError, TypeError, LookupError):
        pass
    # A transport or DB outage must fail closed (never issue a browser login).
    # Deliberately no email addresses, codes or invoice refs in HTTP errors.
    return _login_page(request, note=message)


def _verify_code(request) -> HttpResponse:
    ref = request.session.get(_SESSION_CHALLENGE)
    code = request.POST.get("code", "")
    if not ref or not isinstance(code, str) or len(code) > 128:
        return _login_page(request, note="Code invalid or expired.")
    try:
        identity_id = consume_login_challenge(ref, code)
        if not settled_accounts(identity_id):
            raise IdentityAdapterClosed("settled entitlement required")
    except (IdentityAdapterClosed, ObjectDoesNotExist, ValueError,
            TypeError, LookupError):
        return _login_page(request, note="Code invalid or expired.")
    request.session.cycle_key()
    request.session.pop(_SESSION_CHALLENGE, None)
    request.session[_SESSION_ID] = identity_id
    request.session.set_expiry(1800)
    rotate_token(request)
    return _dashboard(request)


def _session_identity(request) -> int | None:
    value = request.session.get(_SESSION_ID)
    # bool is not an identity ID despite bool subclassing int.
    return value if type(value) is int and value > 0 else None


def _dashboard(request, *, note: str = "") -> HttpResponse:
    identity_id = _session_identity(request)
    if identity_id is None:
        return _login_page(request)
    accounts = settled_accounts(identity_id)
    if not accounts:
        request.session.pop(_SESSION_ID, None)
        return _login_page(request, note="No active paid simulation entitlement.")
    items = []
    for account in accounts[:25]:
        if account["status"] not in (
            PropSimulationAccount.Status.ACTIVE,
            PropSimulationAccount.Status.PASSED,
            PropSimulationAccount.Status.BREACHED,
            PropSimulationAccount.Status.CLOSED,
        ):
            continue
        account_pk = escape(str(account["id"]), quote=True)
        ref = escape(str(account["account_ref"]))
        status = escape(str(account["status"]))
        starting = escape(str(account["starting_capital_usd"]))
        row_html = (
            f"<li>Simulation account <strong>{ref}</strong>: {status}, virtual "
            f"starting reference USD {starting}."
        )
        if account["status"] == PropSimulationAccount.Status.ACTIVE:
            row_html += (
                f"<form method='post' action='{ROOT}' enctype='multipart/form-data'>"
                + _csrf_field(request)
                + "<input type='hidden' name='action' value='journal'>"
                f"<input type='hidden' name='account_id' value='{account_pk}'>"
                "<label>My educational 10-session CSV journal "
                "<input type='file' name='journal_csv' accept='.csv,text/csv' required></label>"
                "<button type='submit'>Save private journal and produce scorecard</button></form>"
            )
        else:
            row_html += "<p class='note'>This simulation is no longer open for new learning journals.</p>"
        items.append(row_html + "</li>")
    if not items:
        return _login_page(request, note="No accessible settled accounts.")
    text = (
        f"<p class='note'>{escape(note)}</p>" if note else ""
    ) + (
        "<p>These entries are derived exclusively from server-verified, "
        "invoice-owner-matched simulated accounts. User journal entries "
        "produce educational feedback only and are <strong>never</strong> "
        "authoritative evidence of a prop evaluation pass or financial reward.</p>"
        "<p><a href='/moj-prop/starter-30-trx/journal-template.csv'>"
        "Download the blank 10-session CSV journal</a></p>"
        "<ul>" + "".join(items) + "</ul>"
        f"<form method='post' action='{ROOT}'>" + _csrf_field(request)
        + "<input type='hidden' name='action' value='logout'>"
        "<button type='submit'>Sign out</button></form>"
    )
    reports = list(
        PropSimulationEvent.objects.using(MOJPROP_DB_ALIAS)
        .filter(
            account__identity_id=identity_id,
            account__invoice_owner__identity_id=identity_id,
            account__invoice_owner__settlement_verified=True,
            source=_JOURNAL_SOURCE,
        )
        .order_by("-created_at")
        .values_list("event_ref", flat=True)[:15]
    )
    if reports:
        text += "<h2>Previous private educational reports</h2><ul>"
        for ref in reports:
            if isinstance(ref, str) and _CASE.fullmatch(ref):
                safe = escape(ref, quote=True)
                text += f"<li><a href='{ROOT}?case={safe}'>Report {safe}</a></li>"
        text += "</ul>"
    return _page(request, "My simulated Starter30 account", text)


def _journal(request) -> HttpResponse:
    identity_id = _session_identity(request)
    if identity_id is None:
        return _login_page(request)
    raw_id = request.POST.get("account_id", "")
    uploaded = request.FILES.get("journal_csv")
    try:
        account_uuid = uuid.UUID(raw_id)
        if uploaded is None or uploaded.size > MAX_BYTES or uploaded.size < 1:
            raise InvalidJournal("Journal must be a small CSV file")
        rows = parse_journal_csv(uploaded.read(MAX_BYTES + 1))
        assessment = assess_journal(rows)
        now = timezone.now()
        with transaction.atomic(using=MOJPROP_DB_ALIAS):
            account = (
                PropSimulationAccount.objects.using(MOJPROP_DB_ALIAS)
                .select_for_update()
                .get(
                    pk=account_uuid,
                    identity_id=identity_id,
                    invoice_owner__identity_id=identity_id,
                    invoice_owner__settlement_verified=True,
                )
            )
            if (
                account.status != PropSimulationAccount.Status.ACTIVE
                or account.opened_at is None
                or now < account.opened_at
                or now >= account.opened_at + timedelta(days=60)
            ):
                raise InvalidJournal("Challenge not open for journal submissions")
            journals = PropSimulationEvent.objects.using(MOJPROP_DB_ALIAS).filter(
                account=account, source=_JOURNAL_SOURCE
            )
            since = now - timedelta(days=1)
            if journals.filter(created_at__gte=since).count() >= 3:
                raise InvalidJournal("Daily educational journal limit reached")
            # Sequence is unique per account across *all* event sources;
            # journaling must never reuse the numbering of risk/other events.
            seq = (
                PropSimulationEvent.objects.using(MOJPROP_DB_ALIAS)
                .filter(account=account)
                .aggregate(last=Max("sequence_no"))["last"] or 0
            )
            case_ref = "MPS30-" + secrets.token_hex(10).upper()
            payload = {
                "schema": "mojprop.starter30.buyer_education.v1",
                "sessions": rows,
                "assessment": assessment,
                "verified_trade_evidence": False,
                "payout_eligibility": False,
            }
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            PropSimulationEvent.objects.using(MOJPROP_DB_ALIAS).create(
                account=account,
                event_ref=case_ref,
                sequence_no=seq + 1,
                event_type=PropSimulationEvent.EventType.RISK,
                source=_JOURNAL_SOURCE,
                occurred_at=now,
                payload_digest=sha256(canonical.encode()).hexdigest(),
                payload=payload,
            )
    except (InvalidJournal, ObjectDoesNotExist, ValueError, TypeError,
            AttributeError, LookupError):
        return _dashboard(request, note="The journal was not accepted. Check the CSV format, active account and submission limits.")
    return _report(request, case_ref)


def _report(request, case_ref: str) -> HttpResponse:
    identity_id = _session_identity(request)
    if identity_id is None:
        return _login_page(request)
    if not isinstance(case_ref, str) or _CASE.fullmatch(case_ref) is None:
        raise Http404
    try:
        event = (
            PropSimulationEvent.objects.using(MOJPROP_DB_ALIAS)
            .select_related("account")
            .get(
                event_ref=case_ref,
                source=_JOURNAL_SOURCE,
                account__identity_id=identity_id,
                account__invoice_owner__identity_id=identity_id,
                account__invoice_owner__settlement_verified=True,
            )
        )
    except PropSimulationEvent.DoesNotExist:
        raise Http404
    payload = event.payload
    if (
        type(payload) is not dict
        or payload.get("schema") != "mojprop.starter30.buyer_education.v1"
        or payload.get("verified_trade_evidence") is not False
        or payload.get("payout_eligibility") is not False
    ):
        raise Http404
    # Detect accidental payload corruption before presenting a private report.
    # This digest is a consistency check, not a proof of commercial eligibility.
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    observed = sha256(canonical.encode()).hexdigest()
    if not hmac.compare_digest(event.payload_digest, observed):
        raise Http404
    rows = payload.get("sessions")
    try:
        body = render_private_scorecard(rows, case_ref)
    except (ValueError, InvalidJournal):
        raise Http404
    return _secured(HttpResponse(body, content_type="text/html; charset=utf-8"))


@csrf_protect
@require_http_methods(["GET", "POST"])
def buyer_portal(request):
    """Explicitly gated buyer-initiated email access and private journal."""
    _require_authorized_release()
    if request.method == "GET":
        case = request.GET.get("case")
        return _report(request, case) if case else _dashboard(request)
    action = request.POST.get("action", "")
    if action == "request":
        return _request_code(request)
    if action == "verify":
        return _verify_code(request)
    if action == "journal":
        return _journal(request)
    if action == "logout":
        request.session.flush()
        return _login_page(request, note="Signed out.")
    return _page(request, "Unsupported account action", "<p class='error'>Invalid account action.</p>", status=400)
