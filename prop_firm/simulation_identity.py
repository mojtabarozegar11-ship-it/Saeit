"""Simulation-only email login; never authenticates existing staff identities."""
import secrets
import uuid
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac, constant_time_compare
from .models import PropSimulationIdentity, PropSimulationLoginChallenge
from core.contact_intake import canonical_contact_email

def is_verified_simulation_user(user):
    return bool(user.is_authenticated and user.is_active and not user.is_staff
                and not user.is_superuser and PropSimulationIdentity.objects.filter(
                    owner_id=user.pk, email=user.email).exists())

def _digest(challenge_id, code):
    return salted_hmac("mojprop.email.v1", str(challenge_id) + ":" + code,
                       algorithm="sha256").hexdigest()

@transaction.atomic
def issue_challenge(email):
    email = canonical_contact_email(email)
    now = timezone.now()
    challenge, created = PropSimulationLoginChallenge.objects.select_for_update().get_or_create(
        email=email, defaults={"code_digest": "", "expires_at": now, "sent_at": now})
    if not created and challenge.sent_at > now - timedelta(minutes=2):
        return None
    code = secrets.token_hex(6).upper()
    challenge.challenge_id = uuid.uuid4()
    challenge.code_digest = _digest(challenge.challenge_id, code)
    challenge.sent_at = now
    challenge.expires_at = now + timedelta(minutes=10)
    challenge.attempts = 0
    challenge.consumed = False
    challenge.save()
    return str(challenge.challenge_id), code

@transaction.atomic
def consume_challenge(challenge_id, code):
    try:
        identifier = uuid.UUID(str(challenge_id))
    except (ValueError, TypeError, AttributeError):
        return None
    row = PropSimulationLoginChallenge.objects.select_for_update().filter(challenge_id=identifier).first()
    now = timezone.now()
    if row is None or row.consumed or row.expires_at <= now or row.attempts >= 5:
        return None
    row.attempts += 1
    if not isinstance(code, str) or len(code) != 12 or not constant_time_compare(
            row.code_digest, _digest(identifier, code.upper())):
        row.save(update_fields=["attempts"])
        return None
    row.consumed = True
    row.code_digest = ""
    row.save(update_fields=["attempts", "consumed", "code_digest"])
    identity = PropSimulationIdentity.objects.select_related("owner").filter(email=row.email).first()
    if identity is None:
        # Never look up an existing account by mutable/nonunique Django email.
        user = get_user_model().objects.create_user(
            username="mojprop-" + uuid.uuid4().hex, email=row.email, password=None)
        identity = PropSimulationIdentity.objects.create(owner=user, email=row.email, verified_at=now)
    elif not is_verified_simulation_user(identity.owner):
        return None
    else:
        identity.verified_at = now
        identity.save(update_fields=["verified_at"])
    return identity.owner
