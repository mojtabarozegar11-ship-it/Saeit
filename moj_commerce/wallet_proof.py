"""Replay-safe proof that a merchant controls an advertised TRON address.

TRON TIP-191/TRON Signed Message V2: the wallet signs a server-generated,
merchant-bound UTF-8 challenge. Only the signature (never a private key or
mnemonic) is accepted by this backend. Cryptocurrency custody is not involved.
"""
from __future__ import annotations

import re
import secrets
import uuid
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from mpw_tron_pro.core import tron_address_hex, CheckoutError

from .models import Merchant, MerchantAddress, WalletOwnershipChallenge
from .services import CommerceRejected, CommerceUnavailable

CHALLENGE_TTL = timedelta(minutes=5)
CHALLENGE_COOLDOWN = timedelta(seconds=60)
SIGNATURE_HEX = re.compile(r'^(?:0x)?([0-9a-fA-F]{130})$')


def recover_signer_tron_hex(message: str, signature: str) -> str:
    """Recover address using vetted secp256k1 and Keccak; no wallet secrets.

    Implements TronWeb's signMessageV2 (not legacy signMessage) according to
    the official TronWeb API. Message is signed verbatim as UTF-8 bytes.
    """
    if not isinstance(message,str) or not 20 <= len(message) <= 550:
        raise CommerceRejected('Invalid wallet challenge')
    m = SIGNATURE_HEX.fullmatch(signature) if isinstance(signature,str) else None
    if not m:
        raise CommerceRejected('Invalid TRON v2 signature encoding')
    raw = bytes.fromhex(m.group(1))
    v = raw[-1]
    if v in (27,28): v -= 27
    if v not in (0,1):
        raise CommerceRejected('Unsupported TRON recovery code')
    try:
        from eth_keys import keys
        from eth_keys.constants import SECPK1_N
        from eth_utils import keccak
    except ImportError as exc:
        raise CommerceUnavailable('Wallet signature verification dependency not available') from exc
    r, s = int.from_bytes(raw[:32],'big'), int.from_bytes(raw[32:64],'big')
    if not (0 < r < SECPK1_N and 0 < s <= SECPK1_N // 2):
        raise CommerceRejected('Invalid or malleable signature')
    msg_bytes = message.encode('utf8')
    digest = keccak(b'\x19TRON Signed Message:\n' + str(len(msg_bytes)).encode('ascii') + msg_bytes)
    try:
        recovered = keys.Signature(vrs=(v,r,s)).recover_public_key_from_msg_hash(digest)
        return '41' + recovered.to_canonical_address().hex().upper()
    except (ValueError, TypeError) as exc:
        raise CommerceRejected('TRON signature recovery failed') from exc


def _authorized_address(merchant_public_id, address_id, owner_id, *, lock):
    queryset = MerchantAddress.objects.select_related('merchant')
    if lock: queryset = queryset.select_for_update()
    try:
        address = queryset.get(pk=address_id, merchant__public_id=merchant_public_id,
                               merchant__owner_id=owner_id)
    except (MerchantAddress.DoesNotExist, ValueError, TypeError) as exc:
        raise CommerceRejected('Wallet address not found for this seller') from exc
    if address.merchant.status == Merchant.Status.SUSPENDED:
        raise CommerceRejected('Suspended merchant cannot verify wallets')
    try:
        tron_address_hex(address.address)
    except CheckoutError as exc:
        raise CommerceRejected('Invalid TRON mainnet wallet address') from exc
    return address


def issue_wallet_challenge(merchant_public_id, address_id, owner_id):
    """One challenge per address, rate-limited by the *locked DB row*."""
    with transaction.atomic():
        address = _authorized_address(merchant_public_id,address_id,owner_id,lock=True)
        now = timezone.now()
        current = WalletOwnershipChallenge.objects.select_for_update().filter(address=address).first()
        if current and current.created_at > now - CHALLENGE_COOLDOWN:
            raise CommerceRejected('Wallet challenge cooldown active')
        nonce = secrets.token_hex(32)
        exp = now + CHALLENGE_TTL
        public_id = uuid.uuid4()
        # Never use a browser-submitted message when verifying. Domain and purpose
        # are bound to what the server stored at issuance.
        message = '\n'.join((
            'MOJ Commerce — verify receiving wallet ownership',
            'Domain: mojplaywin.com',
            'Network: tron-mainnet',
            'Merchant: ' + address.merchant.public_id.hex,
            'Address: ' + address.address,
            'Nonce: ' + nonce,
            'Expires-UTC: ' + exp.isoformat(),
            'No funds transfer or approval is requested.',
        ))
        if current:
            current.public_id=public_id
            current.message=message
            current.created_at=now
            current.expires_at=exp
            current.consumed_at=None
            current.save(update_fields=['public_id','message','created_at','expires_at','consumed_at'])
        else:
            WalletOwnershipChallenge.objects.create(
                address=address, public_id=public_id, message=message,
                created_at=now, expires_at=exp)
        return {'challenge_id': str(public_id), 'message':message,
                'expires_at':exp.isoformat(), 'network':'tron-mainnet'}


def complete_wallet_challenge(merchant_public_id,address_id,owner_id,challenge_id,signature,
                              *, recover=recover_signer_tron_hex):
    """Consume challenge on *every* signature attempt, including failures.

    The transaction is not rolled back on wrong signature. This prevents replay
    and makes guessing require a new challenge after a cooldown.
    """
    verified = False
    with transaction.atomic():
        address = _authorized_address(merchant_public_id,address_id,owner_id,lock=True)
        try:
            chall = WalletOwnershipChallenge.objects.select_for_update().get(address=address,
                   public_id=challenge_id)
        except (WalletOwnershipChallenge.DoesNotExist,TypeError,ValueError) as exc:
            raise CommerceRejected('Unknown or superseded wallet challenge') from exc
        now=timezone.now()
        if chall.consumed_at is not None or now >= chall.expires_at:
            raise CommerceRejected('Wallet challenge expired or already consumed')
        chall.consumed_at=now
        chall.save(update_fields=['consumed_at'])
        try:
            signer_hex = recover(chall.message,signature)
            verified=secrets.compare_digest(signer_hex,tron_address_hex(address.address))
        except (CommerceRejected, CommerceUnavailable):
            verified=False
        if verified:
            address.verified_at=now
            address.verified_via=MerchantAddress.ProofMethod.SIGN_V2
            address.save(update_fields=['verified_at','verified_via'])
    if not verified:
        raise CommerceRejected('Wallet ownership signature did not match')
    return {'status':'verified', 'address':address.address,
            'verified_at':address.verified_at.isoformat(),
            'method':MerchantAddress.ProofMethod.SIGN_V2}