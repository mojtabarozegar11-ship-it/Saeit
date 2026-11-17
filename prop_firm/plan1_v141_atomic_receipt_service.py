"""Transaction-safe MOJ PROP v1.4.1 DEMO manifest receipt writer.

Requires an EXISTING privately provisioned challenge state. No customer
endpoint, sale, invoice, on-chain transfer, settlement, enrollment, actual
simulator creation, broker operation, or external evidence archive is offered.
The service guards concurrent sequence progression using Django row locks
and DB uniqueness. Only deploy after real MariaDB tests and off-host backup.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import re

from django.db import transaction

from .plan1_v141_persistence_models import (
    PropV141SimState, PropV141SimReceipt,
)
from .plan1_v141_signed_simulator_manifest import (
    LedgerManifestRejected, _no_dupes, _no_float, _no_nonfinite,
    verify_and_replay_signed_simulator_manifest,
)
from .plan1_v14_social_or_50_terms import review_prospective_terms
from .plan1_v141_replay_journal_policy import (
    JournalTransitionRejected, PreviousReplayState,
    decide_next_signed_replay_receipt,
)

_SHA = re.compile(r"[0-9a-f]{64}\Z")
MAX_RAW = 3_000_000


class DurableSimReplayRejected(ValueError):
    """Required trusted DB and signed simulator evidence did not reconcile."""


@dataclass(frozen=True)
class StoredSimReplayResult:
    state_pk: int
    receipt_pk: int
    challenge_ref: str
    sequence: int
    replay_sha256: str
    receipt_sha256: str
    mathematical_state: str
    idempotent_replay: bool
    # A stored row does not prove anything external or authorize cash/trading.
    external_manifest_archive_independently_verified: bool = False
    broker_licensed_and_delegated_orders_authorized: bool = False
    merchant_legality_verified: bool = False
    buyer_contract_legally_signed: bool = False
    paid_checkout_authorized: bool = False
    enrollment_authorized: bool = False
    real_trading_authorized: bool = False
    payout_authorized: bool = False


def _manifest_claims(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_RAW:
        raise DurableSimReplayRejected("bounded manifest bytes required")
    try:
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_dupes,
                         parse_float=_no_float, parse_constant=_no_nonfinite)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise DurableSimReplayRejected("invalid manifest envelope") from exc
    if type(doc) is not dict or type(doc.get("sequence")) is not int:
        raise DurableSimReplayRejected("signed sequence required")
    if type(doc.get("manifest_id")) is not str:
        raise DurableSimReplayRejected("signed manifest ID required")
    return doc["sequence"], doc["manifest_id"]


@transaction.atomic
def store_signed_v141_demo_manifest(*, state_pk: int, raw_manifest: bytes,
                                   hmac_signature: str,
                                   trusted_signer_keys: dict,
                                   server_now: datetime) -> StoredSimReplayResult:
    """Serialize one signed full-snapshot receipt under a DB row lock.

    A separate privileged provisioning service must first create the exact
    immutable challenge/contract/source/key state after a lawful enrollment.
    The client must NEVER choose state_pk or trusted_signer_keys. Historical
    event bytes require a separate, already-operational immutable archive;
    only SHA256 receipts are stored here. It is not an archive substitute.
    """
    if type(state_pk) is not int or state_pk < 1:
        raise DurableSimReplayRejected("trusted internal state PK required")
    if type(trusted_signer_keys) is not dict:
        raise DurableSimReplayRejected("server-owned signer key registry required")
    if type(server_now) is not datetime or server_now.tzinfo is None or server_now.utcoffset() is None:
        raise DurableSimReplayRejected("server-owned timezone-aware timestamp required")
    try:
        state = PropV141SimState.objects.select_for_update().get(pk=state_pk)
    except PropV141SimState.DoesNotExist as exc:
        raise DurableSimReplayRejected("unprovisioned challenge must not be created by an intake") from exc

    terms = review_prospective_terms()
    if state.terms_sha256 != terms.contract_candidate_sha256:
        raise DurableSimReplayRejected("state contract digest mismatch; old buyer terms unchanged")
    if (type(state.last_sequence) is not int or state.last_sequence < 0
            or state.last_sequence > 1_000_000_000):
        raise DurableSimReplayRejected("invalid persisted replay sequence")
    if (state.last_sequence == 0 and
            (state.last_manifest_sha256 or state.last_receipt_sha256 or state.last_as_of)):
        raise DurableSimReplayRejected("initial journal state corrupted")
    if (state.last_sequence > 0 and
            (state.last_as_of is None or _SHA.fullmatch(state.last_receipt_sha256 or "") is None)):
        raise DurableSimReplayRejected("stored journal sequence lacks last durable receipt")
    claimed_sequence, claimed_id = _manifest_claims(raw_manifest)
    if not 1 <= claimed_sequence <= 1_000_000_000:
        raise DurableSimReplayRejected("unsigned sequence out of bounds")
    if claimed_sequence > state.last_sequence + 1:
        raise DurableSimReplayRejected("gap in monotone ledger sequence")
    # Authenticate EVERY duplicate before returning a stable idempotent receipt.
    try:
        signed = verify_and_replay_signed_simulator_manifest(
            raw_manifest=raw_manifest,
            hmac_signature=hmac_signature,
            trusted_signer_keys=trusted_signer_keys,
            expected_source=state.trusted_source,
            expected_key_id=state.trusted_key_id,
            expected_manifest_id=claimed_id,
            expected_challenge_ref=state.challenge_ref,
            expected_sequence=claimed_sequence,
            now=server_now,
        )
    except (LedgerManifestRejected, ValueError, TypeError) as exc:
        raise DurableSimReplayRejected("signed simulator snapshot rejected") from exc
    calc = signed.calculation
    digest = signed.raw_manifest_sha256
    if claimed_sequence <= state.last_sequence:
        try:
            old = PropV141SimReceipt.objects.get(state=state, sequence=claimed_sequence)
        except PropV141SimReceipt.DoesNotExist as exc:
            raise DurableSimReplayRejected("replay sequence has no durable receipt") from exc
        if (old.manifest_id != claimed_id or old.raw_manifest_sha256 != digest
                or old.replay_sha256 != calc.snapshot_sha256):
            raise DurableSimReplayRejected("historical replay does not match stored immutable receipt")
        return StoredSimReplayResult(
            state_pk=state.pk, receipt_pk=old.pk,
            challenge_ref=state.challenge_ref,
            sequence=old.sequence, replay_sha256=old.replay_sha256,
            receipt_sha256=old.receipt_sha256,
            mathematical_state=old.reported_engine_state,
            idempotent_replay=True,
        )
    try:
        next_receipt = decide_next_signed_replay_receipt(
            previous=PreviousReplayState(
                challenge_ref=state.challenge_ref,
                contract_sha256=state.terms_sha256,
                sequence=state.last_sequence,
                engine_state=state.last_engine_state,
                last_assessment_utc=state.last_as_of,
                last_phase_one_accepted_utc=state.last_phase_one_accepted_at,
                last_phase_one_evidence_sha256=state.last_phase_one_evidence_sha256,
                last_phase_two_evidence_sha256=state.last_phase_two_evidence_sha256,
                last_phase_two_started_utc=state.last_phase_two_started_at,
                last_phase_two_completed_utc=state.last_phase_two_completed_at,
                previous_receipt_sha256=state.last_receipt_sha256,
            ),
            calculated=calc,
            manifest_sha256=digest,
            requested_sequence=claimed_sequence,
        )
    except JournalTransitionRejected as exc:
        raise DurableSimReplayRejected("durable state transition rejected") from exc
    stamp = next_receipt.assessment_utc
    receipt_digest = next_receipt.receipt_sha256
    previous = next_receipt.previous_receipt_sha256
    record = PropV141SimReceipt.objects.create(
        state=state, sequence=claimed_sequence, manifest_id=claimed_id,
        raw_manifest_sha256=digest, replay_sha256=calc.snapshot_sha256,
        previous_receipt_sha256=previous, receipt_sha256=receipt_digest,
        reported_engine_state=next_receipt.resulting_engine_state, as_of=stamp,
    )
    state.last_sequence = claimed_sequence
    state.last_manifest_sha256 = digest
    state.last_replay_sha256 = calc.snapshot_sha256
    state.last_as_of = stamp
    state.last_phase_one_accepted_at = next_receipt.phase_one_accepted_utc
    state.last_phase_one_evidence_sha256 = next_receipt.phase_one_evidence_sha256 or ""
    state.last_phase_two_evidence_sha256 = next_receipt.phase_two_evidence_sha256 or ""
    state.last_phase_two_started_at = next_receipt.phase_two_started_utc
    state.last_phase_two_completed_at = next_receipt.phase_two_completed_utc
    state.last_engine_state = next_receipt.resulting_engine_state
    state.last_receipt_sha256 = receipt_digest
    state.save(update_fields=(
        "last_sequence", "last_manifest_sha256", "last_replay_sha256",
        "last_as_of", "last_phase_one_accepted_at",
        "last_phase_one_evidence_sha256", "last_phase_two_evidence_sha256",
        "last_phase_two_started_at", "last_phase_two_completed_at",
        "last_engine_state", "last_receipt_sha256", "updated_at"
    ))
    return StoredSimReplayResult(
        state_pk=state.pk, receipt_pk=record.pk,
        challenge_ref=state.challenge_ref,
        sequence=claimed_sequence, replay_sha256=calc.snapshot_sha256,
        receipt_sha256=receipt_digest,
        mathematical_state=next_receipt.resulting_engine_state, idempotent_replay=False,
    )
